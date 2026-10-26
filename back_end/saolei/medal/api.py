from datetime import datetime, time

from django.db import transaction
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from ninja import Router
from ninja.decorators import decorate_view
from ninja.errors import HttpError

from userprofile.decorators import login_required_error, staff_required
from userprofile.models import UserProfile
from .schema import CatalogItemOut, EnqueuedOut, GrantIdOut, GrantPageOut, PinsIn, PinsOut, PlayerMedalOut, PlayerStateOut, RebuildIn, RefreshStatusOut, RevokeIn, StaffCatalogItemOut, StaffGrantIn, StaffOverrideIn, StaffOverrideOut, StaffPlayerMedalsOut
from .services import catalog_for, grant_manual, list_grants, MedalError, player_states, player_summary, replace_pins, revoke_manual, set_player_override
from .staff_services import staff_catalog, staff_player_state
from .tasks import enqueue_player_backfill, enqueue_player_refresh, player_refresh_pending
from .utils import GRANT_PAGE_SIZE, GRANT_PAGE_SIZE_MAX, STATE_ID_LIMIT

router = Router()


@router.get('/refresh-status', response=RefreshStatusOut)
@decorate_view(login_required_error)
@decorate_view(ratelimit(key='user', rate='30/m', block=True))
def get_refresh_status(request):
    """
    - login_required_error
    - ratelimit(key='user', rate='30/m', block=True)

    上传后检查本人的刷新/补发任务是否仍在排队或运行；只读一次 EXISTS，不扫描录像。
    """
    return {'user_id': request.user.id, 'pending': player_refresh_pending(request.user.id)}


def _http_error(exc: MedalError):
    if exc.code in {'user', 'definition', 'missing'}:
        raise HttpError(404, 'Not found')
    if exc.code == 'actor':
        raise HttpError(403, 'Staff access required')
    raise HttpError(400, 'Invalid medal request')


def _parse_state_ids(raw):
    if raw is None or raw == '':
        return []
    parts = [item.strip() for item in str(raw).split(',')]
    if any(not item or not item.isdigit() for item in parts):
        raise HttpError(400, 'Invalid medal request')
    parsed = []
    seen = set()
    for item in parts:
        value = int(item)
        if value <= 0:
            raise HttpError(400, 'Invalid medal request')
        if value in seen:
            continue
        seen.add(value)
        parsed.append(value)
    if len(parsed) > STATE_ID_LIMIT:
        raise HttpError(400, 'Invalid medal request')
    return parsed


@router.get('/catalog', response=list[CatalogItemOut])
@decorate_view(ratelimit(key='ip', rate='5/s'))
def get_catalog(request):
    """
    - ratelimit(key='ip', rate='5/s')

    已启用的图鉴。未解锁的隐藏定义不出现。
    """
    return catalog_for(request.user)


@router.get('/players/state', response=list[PlayerStateOut])
@decorate_view(ratelimit(key='ip', rate='5/s'))
def get_player_states(request, ids: str = ''):
    """
    - ratelimit(key='ip', rate='5/s')

    批量返回已入档且未锁定的勋章。ids 最多 100 个。命中 Redis 时不查 MySQL，缺键批量读取摘要，不扫描录像。
    """
    return player_states(_parse_state_ids(ids))


@router.get('/players/{user_id}', response=PlayerMedalOut)
@decorate_view(ratelimit(key='ip', rate='5/s'))
def get_player_medals(request, user_id: int):
    """
    - ratelimit(key='ip', rate='5/s')

    该玩家的勋章摘要、总分和佩戴。尚未做过历史扫描时只入队，不在这次请求里计算。
    """
    try:
        summary = player_summary(user_id)
        if summary['scan_pending']:
            enqueue_player_backfill(user_id)
        return summary
    except MedalError as exc:
        _http_error(exc)


@router.get('/players/{user_id}/grants', response=GrantPageOut)
@decorate_view(ratelimit(key='ip', rate='5/s'))
def get_player_grants(request, user_id: int, page: int = 1, page_size: int = GRANT_PAGE_SIZE):
    """
    - ratelimit(key='ip', rate='5/s')

    未撤销授予的分页。
    """
    page = max(1, page)
    page_size = min(max(1, page_size), GRANT_PAGE_SIZE_MAX)
    try:
        return list_grants(user_id, page, page_size)
    except MedalError as exc:
        _http_error(exc)


@router.put('/pins', response=PinsOut)
@decorate_view(login_required_error)
@decorate_view(ratelimit(key='user', rate='30/m', block=True))
def update_pins(request, payload: PinsIn):
    """
    - login_required_error
    - ratelimit(key='user', rate='30/m', block=True)

    替换本人的佩戴顺序，最多 6 个授予。
    """
    try:
        pin_ids = replace_pins(request.user, payload.grant_ids)
    except MedalError as exc:
        _http_error(exc)
    return {'pin_ids': pin_ids}


@router.post('/refresh', response=EnqueuedOut)
@decorate_view(login_required_error)
@decorate_view(ratelimit(key='user', rate='1/m', block=True))
def refresh_medals(request):
    """
    - login_required_error
    - ratelimit(key='user', rate='1/m', block=True)

    只入队当前用户的重算。
    """
    enqueue_player_refresh(request.user.id)
    return {'enqueued': True}


@router.post('/staff/grants', response=GrantIdOut)
@decorate_view(staff_required)
def staff_grant(request, payload: StaffGrantIn):
    """
    - staff_required

    人工发放并锁定指定档位，优先于后续自动评估。
    """
    granted_at = timezone.make_aware(datetime.combine(payload.granted_on, time.min), timezone.get_current_timezone())
    try:
        grant = grant_manual(request.user, payload.code, payload.user_id, payload.reason, granted_at, stage=payload.stage, scope_key=payload.scope_key)
    except MedalError as exc:
        _http_error(exc)
    return {'id': grant.id}


@router.post('/staff/grants/{grant_id}/revoke', response=GrantIdOut)
@decorate_view(staff_required)
def staff_revoke(request, grant_id: int, payload: RevokeIn):
    """
    - staff_required

    人工撤销并持续禁止自动发放，必须写原因。
    """
    try:
        grant = revoke_manual(request.user, grant_id, payload.reason)
    except MedalError as exc:
        _http_error(exc)
    return {'id': grant.id}


@router.post('/staff/rebuild', response=EnqueuedOut)
@decorate_view(staff_required)
def staff_rebuild(request, payload: RebuildIn):
    """
    - staff_required

    入队指定玩家的低优先级补发。请求里不重算。
    """
    if not UserProfile.objects.filter(pk=payload.user_id).exists():
        raise HttpError(404, 'Not found')
    enqueue_player_backfill(payload.user_id)
    return {'enqueued': True}


@router.get('/staff/catalog', response=list[StaffCatalogItemOut])
@decorate_view(staff_required)
def get_staff_catalog(request):
    """
    - staff_required

    管理员选择勋章的完整目录，包含停用和隐藏定义。
    """
    return staff_catalog()


@router.get('/staff/players/{user_id}', response=StaffPlayerMedalsOut)
@decorate_view(staff_required)
def get_staff_player_medals(request, user_id: int):
    """
    - staff_required

    该玩家的授予、人工决定和最近 50 条操作记录。
    """
    try:
        return staff_player_state(user_id)
    except MedalError as exc:
        _http_error(exc)


@router.post('/staff/overrides', response=StaffOverrideOut)
@decorate_view(staff_required)
def update_staff_override(request, payload: StaffOverrideIn):
    """
    - staff_required

    强制发放、禁止发放或恢复自动判定。恢复后提交时入队，后台重算真实结果。
    """
    if payload.mode == 'grant' and payload.granted_on is None:
        raise HttpError(400, 'Grant date required')
    granted_at = None
    if payload.granted_on is not None:
        granted_at = timezone.make_aware(datetime.combine(payload.granted_on, time.min), timezone.get_current_timezone())
    try:
        with transaction.atomic():
            grant = set_player_override(
                request.user, payload.user_id, payload.code, payload.scope_key, payload.mode, payload.reason,
                stage=payload.stage, granted_at=granted_at,
            )
            if payload.mode == 'auto':
                transaction.on_commit(lambda: enqueue_player_refresh(payload.user_id))
    except MedalError as exc:
        _http_error(exc)
    return {'grant_id': None if grant is None else grant.id, 'mode': payload.mode, 'enqueued': payload.mode == 'auto'}
