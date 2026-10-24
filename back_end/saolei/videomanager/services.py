from datetime import datetime
import logging

from django.db import transaction
from django_apscheduler import util

from utils.ranking_lock import ranking_access
from .cache import newest_cache
from .models import VideoModel

logger = logging.getLogger('videomanager')


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


def find_identical_video(file, **filters):
    candidates = VideoModel.objects.filter(file_size=file.size, **filters).order_by('pk')
    data = file.read()
    file.seek(0)
    for candidate in candidates:
        with candidate.file.open('rb') as existing:
            if existing.read() == data:
                return candidate
    return None


def set_import_upload_time(video: VideoModel, upload_time: datetime | None, *, created=False):
    """新录像覆盖 auto_now_add；重复录像只保留更早的时间，并触发保存信号。"""
    if upload_time is not None and (created or upload_time < video.upload_time):
        video.upload_time = upload_time
        video.save(update_fields=['upload_time'])


@util.close_old_connections
def delete_newest_queue():
    return newest_cache.trim()
