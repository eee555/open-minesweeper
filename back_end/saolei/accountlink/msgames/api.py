from datetime import datetime
from typing import Literal

from django.db.models import Count, Q
from django_ratelimit.decorators import ratelimit
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.orm import create_schema

from accountlink.models import AccountLinkQueue, AccountMinesweeperGames, Platform, VideoMSGames
from accountlink.services import msgames_video_import_one, update_msgames_video_list
from accountlink.utils import is_memorial_admin
from userprofile.decorators import admin_csrf_required, login_required_error
from utils.exceptions import ExceptionToResponse

router = Router()


MSGamesVideoOut = create_schema(VideoMSGames, exclude=['source_key', 'density_levels'])


class MSGamesImportSummaryOut(Schema):
    total: int
    imported: int
    video_update_time: datetime | None = None


class MSGamesImportOut(Schema):
    status: Literal['IMPORTED', 'ALREADY_IMPORTED']
    import_video_id: int
    video_state: str


class MSGamesSyncOut(Schema):
    status: Literal['SYNCED']
    count: int
    video_update_time: datetime


def _msgames_account(request, msgames_id: int, *, owner: bool = False):
    account = AccountMinesweeperGames.objects.filter(pk=msgames_id).first()
    if account is None:
        raise HttpError(404, 'MSGames account not found.')
    own_account = request.user.is_authenticated and request.user.id == account.parent_id
    memorial_admin = is_memorial_admin(request.user, account.parent)
    if owner and not (own_account or memorial_admin):
        raise HttpError(403, 'Only the linked account owner can import videos.')
    verified = AccountLinkQueue.objects.filter(userprofile_id=account.parent_id, platform=Platform.MSGAMES, verified=True).exists()
    if owner and not verified:
        raise HttpError(403, 'The MSGames account must be verified.')
    if not own_account and not memorial_admin and not request.user.is_staff and not verified:
        raise HttpError(404, 'MSGames account not found.')
    return account


@router.get('/videos', response=list[MSGamesVideoOut])
@decorate_view(ratelimit(key='ip', rate='2/s'))
def get_msgames_videos(request, msgames_id: int):
    """
    - ratelimit(key='ip', rate='2/s')

    Return all stored replay links and display strings without fetching MSGames.
    """
    account = _msgames_account(request, msgames_id)
    return account.videos.all()


@router.get('/summary', response=MSGamesImportSummaryOut)
@decorate_view(ratelimit(key='ip', rate='2/s'))
def get_msgames_import_summary(request, msgames_id: int):
    """
    - ratelimit(key='ip', rate='2/s')

    Return catalogue freshness and completed import counts.
    """
    account = _msgames_account(request, msgames_id)
    result = account.videos.aggregate(
        total=Count('id'), imported=Count('id', filter=Q(import_video__isnull=False)),
    )
    return {
        **result, 'video_update_time': account.video_update_time,
    }


@router.post('/{msgames_id}/sync', response=MSGamesSyncOut)
@decorate_view(login_required_error, admin_csrf_required, ratelimit(key='user', rate='6/h'))
def sync_msgames_videos(request, msgames_id: int):
    """
    - login_required_error
    - admin_csrf_required
    - ratelimit(key='user', rate='6/h')

    Refresh all five score histories synchronously without importing their replays.
    """
    account = _msgames_account(request, msgames_id, owner=True)
    try:
        update_msgames_video_list(account)
    except ExceptionToResponse as exc:
        raise ExceptionToResponse(exc.obj, exc.category, status_code=502) from exc
    account.refresh_from_db(fields=['video_update_time'])
    return {'status': 'SYNCED', 'count': account.videos.count(), 'video_update_time': account.video_update_time}


@router.post('/videos/{video_id}/import', response=MSGamesImportOut)
@decorate_view(login_required_error, admin_csrf_required, ratelimit(key='user', rate='60/m', block=True))
def import_msgames_video(request, video_id: int):
    """
    - login_required_error
    - admin_csrf_required
    - ratelimit(key='user', rate='60/m', block=True)

    Import an original file synchronously and return its local video ID and review state.
    """
    source = VideoMSGames.objects.filter(pk=video_id).first()
    if source is None:
        raise HttpError(404, 'MSGames video not found.')
    _msgames_account(request, source.user_id, owner=True)
    already_imported = bool(source.import_video_id)
    try:
        video = msgames_video_import_one(source)
    except ExceptionToResponse as exc:
        status = exc.status_code if exc.status_code >= 400 else (502 if exc.obj == 'import' else 400)
        raise ExceptionToResponse(exc.obj, exc.category, status_code=status) from exc
    return {
        'status': 'ALREADY_IMPORTED' if already_imported else 'IMPORTED',
        'import_video_id': video.id, 'video_state': video.state,
    }
