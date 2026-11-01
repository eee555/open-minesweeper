from datetime import datetime
import errno
from io import BytesIO
import logging
from pathlib import PurePosixPath
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django_apscheduler import util

from config.text_choices import MS_TextChoices
from utils.ranking_lock import ranking_access
from .cache import newest_cache
from .config import TARGET_COMPRESSION_FORMAT
from .files import compress_original, original_file, validate_compression_target
from .models import ExpandVideoModel, VideoModel
from .utils import calculate_original_hash, pack_compression_format, replay_filename

logger = logging.getLogger('videomanager')


@ranking_access(operation='videomanager.freeze_video')
@transaction.atomic
def freeze_video_by_id(video_id: int, freeze_reason: str, *, actor_id: int):
    reason = freeze_reason.strip()
    if not reason:
        raise ValueError('Freeze reason is required.')
    video = VideoModel.objects.select_for_update().get(pk=video_id)
    expansion = ExpandVideoModel.objects.select_for_update().get(pk=video.video_id)
    expansion.freeze_reason = reason
    expansion.save(update_fields=['freeze_reason'])
    previous_state = video.state
    if video.state != MS_TextChoices.State.FROZEN:
        video.state = MS_TextChoices.State.FROZEN
        video.save(update_fields=['state'])
    logger.info('Staff #%s froze video #%s (previous_state=%s)', actor_id, video_id, previous_state)
    return {'id': video.pk, 'state': video.state, 'freeze_reason': expansion.freeze_reason}


@ranking_access(operation='videomanager.delete_video')
@transaction.atomic
def delete_video_by_id(video_id: int, *, actor_id: int):
    video = VideoModel.objects.select_for_update().filter(pk=video_id).first()
    if video is None:
        return {'id': video_id, 'deleted': False, 'affected_tournament_ids': []}
    tournament_ids = list(video.tournaments.order_by('pk').values_list('pk', flat=True))
    if tournament_ids:
        logger.warning('Superuser #%s requested tournament video deletion: video_id=%s tournament_ids=%s; saved results are not recalculated', actor_id, video_id, tournament_ids)
    video.delete()
    logger.info('Superuser #%s deleted video #%s', actor_id, video_id)
    return {'id': video_id, 'deleted': True, 'affected_tournament_ids': tournament_ids}


def find_identical_video(original_hash: str):
    return VideoModel.objects.filter(original_hash=original_hash).first()


def _delete_unreferenced_file(file_name):
    if not VideoModel.objects.filter(file=file_name).exists():
        try:
            default_storage.delete(file_name)
        except OSError:
            logger.exception('Failed to remove unreferenced replay: %s', file_name)


def compress_video_file(video, *, target=TARGET_COMPRESSION_FORMAT, retry_failed=False):
    """转换独立文件，校验后短事务切换；仅更新存储字段。"""
    validate_compression_target(target)
    target_code = pack_compression_format(*target)
    if not retry_failed and (video.compression_failed or video.compression_format == target_code):
        return 'skipped'
    source_name = video.file.name
    current = VideoModel.objects.filter(pk=video.pk, file=source_name, compression_format=video.compression_format)
    archive_name = None
    try:
        with original_file(source_name, video.compression_format, video.original_filename) as source:
            raw = source.read()
        if len(raw) != video.file_size:
            raise ValueError('Original replay size differs from file_size')
        if video.original_hash and calculate_original_hash(BytesIO(raw)) != video.original_hash:
            raise ValueError('Original replay hash differs from original_hash')
        archive, actual_format = compress_original(raw, target)
        archive_name = str(PurePosixPath(source_name).parent / f'{uuid4().hex}.msrc')
        archive_name = default_storage.save(archive_name, ContentFile(archive))  # noqa: DJM100
        with default_storage.open(archive_name, 'rb') as saved:
            if saved.read() != archive:
                raise ValueError('Stored archive differs from validated archive')
    except (OSError, ValueError, EOFError) as error:
        if archive_name:
            _delete_unreferenced_file(archive_name)
        if isinstance(error, OSError) and error.errno in (errno.ENOSPC, errno.EROFS, errno.EACCES):
            raise
        changed = current.update(compression_failed=True)
        logger.warning('Replay compression failed: id=%s source=%s target=%s error=%s', video.pk, source_name, target, error)
        return 'failed' if changed else 'skipped'
    # A database failure can leave the commit result unknown. Keep both files for recovery.
    with transaction.atomic():
        changed = current.update(
            file=archive_name, original_filename=replay_filename(source_name, video.original_filename),
            stored_file_size=len(archive), compression_format=actual_format, compression_failed=False,
        )
        if changed:
            transaction.on_commit(lambda: _delete_unreferenced_file(source_name))
    if not changed:
        _delete_unreferenced_file(archive_name)
        return 'skipped'
    logger.info('Replay compressed: id=%s target=%s original=%s stored=%s', video.pk, target, len(raw), len(archive))
    return 'converted'


def set_import_upload_time(video: VideoModel, upload_time: datetime | None, *, created=False):
    """新录像覆盖 auto_now_add；重复录像只保留更早的时间，并触发保存信号。"""
    if upload_time is not None and (created or upload_time < video.upload_time):
        video.upload_time = upload_time
        video.save(update_fields=['upload_time'])


@util.close_old_connections
def delete_newest_queue():
    return newest_cache.trim()
