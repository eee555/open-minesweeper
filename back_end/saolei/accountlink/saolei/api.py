from contextlib import contextmanager
from datetime import datetime
import logging
from typing import Literal

from django.db.models import Count, Q
from django_ratelimit.decorators import ratelimit
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.orm import create_schema
from pydantic import Field
from saolei_api import RateLimitError, SaoleiError

from userprofile.decorators import admin_csrf_required, login_required_error
from utils.exceptions import ExceptionToResponse
from .client import saolei_client
from .services import check_binding, import_saolei_video, pending_saolei_videos, sync_saolei_page, update_saolei_account_info
from ..models import AccountSaolei, SaoleiApiVideo

router = Router()
logger = logging.getLogger('accountlink')
SaoleiVideoOut = create_schema(SaoleiApiVideo, exclude=['user', 'file_url'])
SaoleiAccountOut = create_schema(AccountSaolei)


class SummaryOut(Schema):
    total: int
    imported: int
    rejected: int
    pending: int
    skipped: int
    auto_sync: bool
    video_sync_cursor: int
    video_update_time: datetime | None


class VideoPageOut(Schema):
    items: list[SaoleiVideoOut]
    next_after: int | None


class SyncStartIn(Schema):
    full: bool = False


class SyncStartOut(Schema):
    cursor: int
    upper_bound: int


class SyncPageIn(Schema):
    cursor: int = Field(ge=0)
    upper_bound: int = Field(ge=0)


class SyncPageOut(Schema):
    cursor: int
    has_more: bool


class SyncSettingsIn(Schema):
    auto_sync: bool


class ImportOut(Schema):
    status: Literal['imported', 'existing', 'skipped']
    import_video: int | None


def account_for_request(request, account_id, *, owner=False):
    account = AccountSaolei.objects.filter(pk=account_id).first()
    if account is None:
        raise HttpError(404, 'Saolei account not found.')
    if owner:
        if not request.user.is_authenticated:
            raise HttpError(403, 'Only the linked account owner can synchronize videos.')
        # 纪念账号无法登录，改由管理员（站长或具备管理员权限的账号）代为同步与导入其扫雷网录像。
        if request.user.pk != account.parent_id and not ((request.user.is_staff or request.user.is_superuser) and account.parent.is_memorial):
            raise HttpError(403, 'Only the linked account owner can synchronize videos.')
    check_binding(account, account.parent_id)
    return account


def memorial_admin_only(account, user) -> bool:
    """纪念账号无法登录，其资料与自动同步设置只能由站长代为修改。"""
    return account.parent.is_memorial and user.pk != account.parent_id


@contextmanager
def upstream_client():
    try:
        with saolei_client() as client:
            yield client
    except RateLimitError as exc:
        raise ExceptionToResponse('saolei', 'rate_limit', 429) from exc
    except SaoleiError as exc:
        logger.warning('扫雷网 API 请求失败：%s: %s', type(exc).__name__, exc)
        raise ExceptionToResponse('saolei', 'upstream', 502) from exc
    except (FileNotFoundError, KeyError) as exc:
        logger.error('扫雷网 API 配置错误：%s', type(exc).__name__)
        raise ExceptionToResponse('saolei', 'configuration', 503) from exc


@router.get('/{account_id}/summary', response=SummaryOut)
@decorate_view(ratelimit(key='ip', rate='5/s', block=True))
def summary(request, account_id: int):
    """- ratelimit(key='ip', rate='5/s', block=True)"""
    account = account_for_request(request, account_id)
    counts = account.videos.aggregate(
        total=Count('id'), imported=Count('id', filter=Q(import_video__isnull=False)),
        rejected=Count('id', filter=Q(import_video__isnull=True, import_rejected=True)),
    )
    pending = pending_saolei_videos(account).count()
    return {
        **counts, 'pending': pending, 'skipped': counts['total'] - counts['imported'] - counts['rejected'] - pending,
        'auto_sync': account.auto_sync, 'video_sync_cursor': account.video_sync_cursor, 'video_update_time': account.video_update_time,
    }


@router.get('/{account_id}/videos', response=VideoPageOut)
@decorate_view(ratelimit(key='ip', rate='5/s', block=True))
def videos(request, account_id: int, after: int = 0, pending: bool = False):
    """- ratelimit(key='ip', rate='5/s', block=True)

    Read at most 200 local source rows; never fetch the upstream catalogue here.
    """
    account = account_for_request(request, account_id)
    rows = pending_saolei_videos(account) if pending else account.videos.all()
    items = list(rows.filter(pk__gt=max(0, after)).order_by('pk')[:201])
    return {'items': items[:200], 'next_after': items[199].pk if len(items) > 200 else None}


@router.post('/{account_id}/settings', response=SaoleiAccountOut)
@decorate_view(login_required_error, admin_csrf_required, ratelimit(key='user', rate='30/m', block=True))
def settings(request, account_id: int, data: SyncSettingsIn):
    """- login_required_error
    - admin_csrf_required
    - ratelimit(key='user', rate='30/m', block=True)
    """
    account = account_for_request(request, account_id, owner=True)
    if memorial_admin_only(account, request.user) and not request.user.is_superuser:
        raise HttpError(403, 'Only a superuser can change a memorial account profile or auto-sync setting.')
    account.auto_sync = data.auto_sync
    account.save(update_fields=['auto_sync'])
    return account


@router.post('/{account_id}/profile', response=SaoleiAccountOut)
@decorate_view(login_required_error, admin_csrf_required, ratelimit(key='user', rate='6/h', block=True))
def profile(request, account_id: int):
    """- login_required_error
    - admin_csrf_required
    - ratelimit(key='user', rate='6/h', block=True)
    """
    account = account_for_request(request, account_id, owner=True)
    if memorial_admin_only(account, request.user) and not request.user.is_superuser:
        raise HttpError(403, 'Only a superuser can change a memorial account profile or auto-sync setting.')
    with upstream_client() as client:
        update_saolei_account_info(account, client)
    account.refresh_from_db()
    return account


@router.post('/{account_id}/sync/start', response=SyncStartOut)
@decorate_view(login_required_error, admin_csrf_required, ratelimit(key='user', rate='6/h', block=True))
def start_sync(request, account_id: int, data: SyncStartIn):
    """- login_required_error
    - admin_csrf_required
    - ratelimit(key='user', rate='6/h', block=True)
    """
    account = account_for_request(request, account_id, owner=True)
    with upstream_client() as client:
        upper_bound = client.stats().max_video_id
    return {'cursor': 0 if data.full else account.video_sync_cursor, 'upper_bound': upper_bound}


@router.post('/{account_id}/sync/page', response=SyncPageOut)
@decorate_view(login_required_error, admin_csrf_required, ratelimit(key='user', rate='30/m', block=True))
def sync_page(request, account_id: int, data: SyncPageIn):
    """- login_required_error
    - admin_csrf_required
    - ratelimit(key='user', rate='30/m', block=True)
    """
    account = account_for_request(request, account_id, owner=True)
    with upstream_client() as client:
        cursor, has_more = sync_saolei_page(account, client, cursor=data.cursor, upper_bound=data.upper_bound)
    return {'cursor': cursor, 'has_more': has_more}


@router.post('/videos/{source_id}/import', response=ImportOut)
@decorate_view(login_required_error, admin_csrf_required, ratelimit(key='user', rate='30/m', block=True))
def import_video(request, source_id: int):
    """- login_required_error
    - admin_csrf_required
    - ratelimit(key='user', rate='30/m', block=True)
    """
    source = SaoleiApiVideo.objects.filter(pk=source_id).first()
    if source is None:
        raise HttpError(404, 'Saolei video not found.')
    source.user = account_for_request(request, source.user_id, owner=True)
    try:
        with upstream_client() as client:
            result = import_saolei_video(source, client)
    except ExceptionToResponse as exc:
        raise ExceptionToResponse(exc.obj, exc.category, exc.status_code if exc.status_code >= 400 else 400) from exc
    source.refresh_from_db()
    return {'status': result, 'import_video': source.import_video_id}
