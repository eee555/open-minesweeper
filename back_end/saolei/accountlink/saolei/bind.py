import re

from django.core.cache import cache
from django_ratelimit.decorators import ratelimit
import httpx
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError

from userprofile.decorators import login_required_error
from utils.exceptions import ExceptionToResponse
from ..models import AccountSaolei, Platform
from ..services import save_verified_account_link

router = Router()

# 扫雷网绑定协议 v2 公开接口（免 key）；测试时 override 此常量。
SAOLEI_PUBLIC_BASE = 'https://saolei.wang'
SAOLEI_BIND_REQUEST_PATH = '/api/public/v1/openms/bind-request'

# 48 位 hex 一次性令牌
TOKEN_RE = re.compile(r'[0-9a-f]{48}')
# 确认凭据的 Redis key（TTL 24h，够扫雷网授权页轮询窗口使用）
SAOLEI_BIND_EVIDENCE_KEY = 'accountlink:saolei:bind:{token}'
SAOLEI_BIND_EVIDENCE_TTL = 24 * 3600

# 上游调用必须在网关 5s 读取预算内完成（default.conf: /api/accountlink/saolei/ → 5s），
# 否则浏览器先超时而后端继续完成绑定，页面报错但绑定成功。
SAOLEI_PUBLIC_TIMEOUT = 4.0


class SaoleiBindConfirmIn(Schema):
    token: str
    sync: bool = True


class SaoleiBindRequestOut(Schema):
    # 0=待确认 1=已核销 2=已取消（扫雷网侧语义，透传给授权页判断）
    status: int
    uid: int
    username: str


class SaoleiBindStatusOut(Schema):
    profile: int | None
    status: str


def fetch_remote_bind_request(token: str) -> dict | None:
    """调扫雷网公开接口 bind-request 核验令牌；令牌无效返回 None，网络失败抛 HttpError(502)。"""
    try:
        response = httpx.get(f'{SAOLEI_PUBLIC_BASE}{SAOLEI_BIND_REQUEST_PATH}', params={'token': token}, timeout=SAOLEI_PUBLIC_TIMEOUT)
    except httpx.HTTPError:
        raise HttpError(502, 'Saolei bind-request upstream unavailable.')
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise HttpError(502, 'Saolei bind-request upstream error.')
    try:
        data = response.json()
        remote = {'status': int(data['status']), 'uid': int(data['uid']), 'username': str(data['username'])}
    except (KeyError, TypeError, ValueError):
        raise HttpError(502, 'Saolei bind-request upstream returned an unexpected payload.')
    if remote['uid'] <= 0:
        raise HttpError(502, 'Saolei bind-request upstream returned an invalid uid.')
    return remote


def _bind_evidence_key(token: str) -> str:
    return SAOLEI_BIND_EVIDENCE_KEY.format(token=token)


def _save_bind_evidence(token: str, uid: int, username: str, sync: bool):
    """记录本次令牌的确认凭据；/status 只认凭据或扫雷网侧的已核销状态。"""
    cache.set(_bind_evidence_key(token), {'uid': uid, 'username': username, 'sync': sync}, SAOLEI_BIND_EVIDENCE_TTL)


def _load_bind_evidence(token: str) -> dict | None:
    return cache.get(_bind_evidence_key(token))


@router.get('/request', response=SaoleiBindRequestOut)
@decorate_view(ratelimit(key='ip', rate='30/m', block=True))
def bind_request(request, token: str):
    """- ratelimit(key='ip', rate='30/m', block=True)

    Proxy the saolei.wang public bind-request endpoint so the authorization
    page can show who is requesting the link (Saolei.wang-initiated flow).
    """
    if not TOKEN_RE.fullmatch(token):
        raise HttpError(404, 'Bind request not found.')
    remote = fetch_remote_bind_request(token)
    if remote is None:
        raise HttpError(404, 'Bind request not found.')
    return remote


@router.post('/confirm')
@decorate_view(login_required_error, ratelimit(key='user', rate='6/h', block=True))
def bind_confirm(request, data: SaoleiBindConfirmIn):
    """- login_required_error
    - ratelimit(key='user', rate='6/h', block=True)

    Verify the token against saolei.wang, then commit the binding for the
    logged-in OpenMS user via save_verified_account_link: it re-checks all
    ownership conflicts under locks (so a concurrent confirm can never
    reassign an existing binding), updates the per-user AccountLinkQueue row
    in place, and maps every conflict to 409. The confirmation evidence is
    stored in Redis (24h TTL) keyed by token so /status can vouch for this
    specific token.
    """
    if not TOKEN_RE.fullmatch(data.token):
        raise HttpError(404, 'Bind request not found.')
    remote = fetch_remote_bind_request(data.token)
    if remote is None or remote['status'] != 0:
        raise HttpError(404, 'Bind request not found.')
    uid, username = remote['uid'], remote['username']
    try:
        account = save_verified_account_link(request.user, Platform.SAOLEI, uid)
    except ExceptionToResponse as exc:
        if exc.obj == 'accountlink' and exc.category == 'collision':
            raise HttpError(409, 'This saolei account is already linked to another OpenMS user.') from exc
        raise
    # save_verified_account_link 建行后补写本次确认才知道的字段
    account.name = username
    account.auto_sync = data.sync
    account.save(update_fields=['name', 'auto_sync'])
    _save_bind_evidence(data.token, uid, username, data.sync)
    return {'status': 'confirmed', 'uid': uid, 'sync': data.sync}


@router.get('/status', response=SaoleiBindStatusOut)
@decorate_view(ratelimit(key='ip', rate='30/m', block=True))
def bind_status(request, token: str):
    """- ratelimit(key='ip', rate='30/m', block=True)

    Settlement endpoint for saolei.wang. A token counts as confirmed only
    when its own confirmation evidence exists (this token was confirmed and
    the binding still points at the same user), or when saolei.wang itself
    reports the request as settled (status 1 = 已核销). Historical bindings
    never vouch for a new token, and a cancelled request stays pending.
    """
    if not TOKEN_RE.fullmatch(token):
        raise HttpError(404, 'Bind request not found.')
    remote = fetch_remote_bind_request(token)
    if remote is None:
        raise HttpError(404, 'Bind request not found.')
    # 本次令牌的确认凭据：确凿核销依据（且归属未变）
    evidence = _load_bind_evidence(token)
    if evidence is not None:
        account = AccountSaolei.objects.filter(pk=evidence['uid']).first()
        if account is not None and evidence['uid'] == remote['uid']:
            return {'profile': account.parent_id, 'status': 'confirmed'}
    # 无凭据：仅当扫雷网侧已核销（status=1，说明雷网已消费本次申请）才视为确认
    if remote['status'] == 1:
        account = AccountSaolei.objects.filter(pk=remote['uid']).first()
        if account is not None:
            return {'profile': account.parent_id, 'status': 'confirmed'}
    return {'profile': None, 'status': 'pending'}
