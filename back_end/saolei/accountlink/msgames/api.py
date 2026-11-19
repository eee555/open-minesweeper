from datetime import datetime
from typing import Literal
from uuid import UUID

from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.tasks import TaskResultStatus
from django_ratelimit.decorators import ratelimit
from django_tasks_db.models import DBTaskResult
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.orm import create_schema

from accountlink.models import AccountLinkQueue, AccountMinesweeperGames, Platform, VideoMSGames
from accountlink.msgames.tasks import task_sync_msgames
from accountlink.services import msgames_video_import_one
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


class MSGamesTaskErrorOut(Schema):
    type: Literal['error']
    object: str
    category: str


MSGamesTaskOut = create_schema(
    DBTaskResult, fields=['id', 'status', 'return_value'],
    custom_fields=[('return_value', MSGamesSyncOut | MSGamesTaskErrorOut | None, None)],
)


def _enqueue_msgames_task(account):
    with transaction.atomic():
        # Serialize repeated submissions, and do not enqueue for a replaced binding.
        get_object_or_404(AccountMinesweeperGames.objects.select_for_update(), pk=account.pk, parent_id=account.parent_id)
        args = [account.pk, account.parent_id]
        existing = DBTaskResult.objects.filter(
            task_path=task_sync_msgames.module_path, args_kwargs={'args': args, 'kwargs': {}},
            status__in=[TaskResultStatus.READY, TaskResultStatus.RUNNING],
        ).first()
        return existing if existing is not None else task_sync_msgames.enqueue(*args).db_result


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


@router.post('/{msgames_id}/sync', response={202: MSGamesTaskOut})
@decorate_view(login_required_error, admin_csrf_required, ratelimit(key='user', rate='6/h'))
def sync_msgames_videos(request, msgames_id: int):
    """
    - login_required_error
    - admin_csrf_required
    - ratelimit(key='user', rate='6/h')

    Enqueue all five score histories without importing their replays.
    """
    account = _msgames_account(request, msgames_id, owner=True)
    return 202, _enqueue_msgames_task(account)


@router.post('/videos/{video_id}/import', response=MSGamesImportOut)
@decorate_view(login_required_error, admin_csrf_required, ratelimit(key='user', rate='60/m', block=True))
def import_msgames_video(request, video_id: int):
    """
    - login_required_error
    - admin_csrf_required
    - ratelimit(key='user', rate='60/m', block=True)

    Import one replay synchronously; the browser waits for this response before importing another.
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


@router.get('/tasks/{task_id}', response=MSGamesTaskOut)
@decorate_view(login_required_error, ratelimit(key='user', rate='60/m', block=True))
def get_msgames_task(request, task_id: UUID):
    """
    - login_required_error
    - ratelimit(key='user', rate='60/m', block=True)

    Return only this binding's task status and business result, without internal tracebacks.
    """
    result = get_object_or_404(DBTaskResult, pk=task_id, task_path=task_sync_msgames.module_path)
    account_id, parent_id = result.args_kwargs['args']
    account = _msgames_account(request, account_id, owner=True)
    if account.parent_id != parent_id:
        raise HttpError(404, 'MSGames task not found.')
    return result
