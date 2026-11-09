import re

from django.db import transaction
from django_ratelimit.decorators import ratelimit
import httpx
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError

from userprofile.decorators import login_required_error
from ..models import AccountLinkQueue, AccountSaolei, Platform
from ..utils import link_account

router = Router()

# 扫雷网绑定协议 v2 公开接口（免 key）；测试时 override 此常量。
SAOLEI_PUBLIC_BASE = 'https://saolei.wang'
SAOLEI_BIND_REQUEST_PATH = '/api/public/v1/openms/bind-request'

TOKEN_RE = re.compile(r'[0-9a-f]{48}')


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
        response = httpx.get(f'{SAOLEI_PUBLIC_BASE}{SAOLEI_BIND_REQUEST_PATH}', params={'token': token}, timeout=10)
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

    Verify the token against saolei.wang, then create the binding for the
    logged-in OpenMS user: one AccountSaolei row (id=saolei uid) plus its
    verified AccountLinkQueue row. Idempotent for the same pair; 409 when the
    saolei uid belongs to another OpenMS user or the user already links a
    different saolei account. `sync` decides AccountSaolei.auto_sync.
    """
    if not TOKEN_RE.fullmatch(data.token):
        raise HttpError(404, 'Bind request not found.')
    remote = fetch_remote_bind_request(data.token)
    if remote is None or remote['status'] != 0:
        raise HttpError(404, 'Bind request not found.')
    uid, username = remote['uid'], remote['username']
    with transaction.atomic():
        # 用户已绑定其他扫雷网账户（AccountSaolei.parent 为 OneToOne）→ 冲突
        if AccountSaolei.objects.filter(parent=request.user).exclude(pk=uid).exists():
            raise HttpError(409, 'This OpenMS user already links another saolei account.')
        if AccountLinkQueue.objects.filter(platform=Platform.SAOLEI, identifier=str(uid), verified=True).exclude(userprofile=request.user).exists():
            raise HttpError(409, 'This saolei account is already linked to another OpenMS user.')
        # 幂等：同一对绑定重复确认只刷新姓名与同步开关
        existing = AccountSaolei.objects.select_for_update().filter(pk=uid).first()
        if existing is not None:
            existing.parent = request.user
            existing.name = username
            existing.auto_sync = data.sync
            existing.save(update_fields=['parent', 'name', 'auto_sync'])
        else:
            link_account(Platform.SAOLEI, uid, request.user)
            account = AccountSaolei.objects.get(pk=uid)
            account.name = username
            account.auto_sync = data.sync
            account.save(update_fields=['name', 'auto_sync'])
        queue = AccountLinkQueue.objects.select_for_update().filter(platform=Platform.SAOLEI, identifier=str(uid), userprofile=request.user).first()
        if queue is None:
            AccountLinkQueue.objects.create(platform=Platform.SAOLEI, identifier=str(uid), userprofile=request.user, verified=True)
        elif not queue.verified:
            queue.verified = True
            queue.save(update_fields=['verified'])
    return {'status': 'confirmed', 'uid': uid, 'sync': data.sync}


@router.get('/status', response=SaoleiBindStatusOut)
@decorate_view(ratelimit(key='ip', rate='30/m', block=True))
def bind_status(request, token: str):
    """- ratelimit(key='ip', rate='30/m', block=True)

    Settlement endpoint for saolei.wang: resolve the token to a saolei uid,
    then report confirmed once the local AccountSaolei row exists. No request
    table is needed because the token state always lives on saolei.wang.
    """
    if not TOKEN_RE.fullmatch(token):
        raise HttpError(404, 'Bind request not found.')
    remote = fetch_remote_bind_request(token)
    if remote is None:
        raise HttpError(404, 'Bind request not found.')
    account = AccountSaolei.objects.filter(pk=remote['uid']).first()
    if account is None:
        return {'profile': None, 'status': 'pending'}
    return {'profile': account.parent_id, 'status': 'confirmed'}
