from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import re

from django_ratelimit.decorators import ratelimit
import httpx
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError

from userprofile.decorators import login_required_error
from utils.exceptions import ExceptionToResponse
from .cache import load_bind_evidence, save_bind_evidence
from .services import confirm_saolei_account_link
from ..models import AccountSaolei

router = Router()

# 扫雷网绑定协议 v2 公开接口（免 key）；测试时 override 此常量。
SAOLEI_PUBLIC_BASE = 'https://saolei.wang'
SAOLEI_BIND_REQUEST_PATH = '/api/public/v1/openms/bind-request'

# 48 位 hex 一次性令牌
TOKEN_RE = re.compile(r'[0-9a-f]{48}')

# HTTPX 分别限制连接、读写等阶段；额外用 future 的总等待上限保证不会超过
# 网关 5s 读取预算，并为数据库、缓存和响应序列化预留约 1s。
SAOLEI_PUBLIC_TIMEOUT = 3.0
SAOLEI_PUBLIC_TOTAL_TIMEOUT = 4.0
_UPSTREAM_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix='saolei-bind')


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


def _request_remote_bind(token: str):
    return httpx.get(
        f'{SAOLEI_PUBLIC_BASE}{SAOLEI_BIND_REQUEST_PATH}',
        params={'token': token},
        timeout=SAOLEI_PUBLIC_TIMEOUT,
    )


def fetch_remote_bind_request(token: str) -> dict | None:
    """调扫雷网公开接口；无效令牌返回 None，网络失败或超过总预算抛 502。"""
    future = _UPSTREAM_EXECUTOR.submit(_request_remote_bind, token)
    try:
        response = future.result(timeout=SAOLEI_PUBLIC_TOTAL_TIMEOUT)
    except (FutureTimeoutError, httpx.HTTPError):
        future.cancel()
        raise HttpError(502, 'Saolei bind-request upstream unavailable.') from None
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise HttpError(502, 'Saolei bind-request upstream error.')
    try:
        data = response.json()
        remote = {'status': int(data['status']), 'uid': int(data['uid']), 'username': str(data['username'])}
    except (KeyError, TypeError, ValueError):
        raise HttpError(502, 'Saolei bind-request upstream returned an unexpected payload.') from None
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

    Verify the token, then save the binding, display name and sync preference
    in one business transaction. Confirmation evidence records both the token
    and the confirming OpenMS user so a later rebind cannot reuse it.
    """
    if not TOKEN_RE.fullmatch(data.token):
        raise HttpError(404, 'Bind request not found.')
    remote = fetch_remote_bind_request(data.token)
    if remote is None or remote['status'] != 0:
        raise HttpError(404, 'Bind request not found.')
    uid, username = remote['uid'], remote['username']
    try:
        confirm_saolei_account_link(request.user, uid, username, data.sync)
    except ExceptionToResponse as exc:
        if exc.obj == 'accountlink' and exc.category == 'collision':
            raise HttpError(409, 'This saolei account is already linked to another OpenMS user.') from exc
        raise
    save_bind_evidence(data.token, confirmer_id=request.user.pk, uid=uid, username=username, sync=data.sync)
    return {'status': 'confirmed', 'uid': uid, 'sync': data.sync}


@router.get('/status', response=SaoleiBindStatusOut)
@decorate_view(ratelimit(key='ip', rate='30/m', block=True))
def bind_status(request, token: str):
    """- ratelimit(key='ip', rate='30/m', block=True)

    Settlement endpoint for saolei.wang. Only this token's own evidence can
    confirm it, and only while the binding still belongs to that confirmer.
    Cancellation is checked first; historical or settled bindings without
    evidence never vouch for a new token.
    """
    if not TOKEN_RE.fullmatch(token):
        raise HttpError(404, 'Bind request not found.')
    remote = fetch_remote_bind_request(token)
    if remote is None:
        raise HttpError(404, 'Bind request not found.')
    if remote['status'] == 2:
        return {'profile': None, 'status': 'pending'}
    evidence = load_bind_evidence(token)
    if evidence is not None and evidence.get('uid') == remote['uid']:
        account = AccountSaolei.objects.filter(
            pk=remote['uid'], parent_id=evidence.get('confirmer_id'),
        ).first()
        if account is not None:
            return {'profile': account.parent_id, 'status': 'confirmed'}
    return {'profile': None, 'status': 'pending'}
