import logging

from django.tasks import task

from .cache import release_share_preview_cleanup, reserve_share_preview_cleanup, set_share_preview_count
from .files import original_file
from .models import VideoModel
from .share_preview import prune_previews
from .utils import calculate_pluck, is_custom_pluck_video, normalize_pluck

logger = logging.getLogger('videomanager')


def enqueue_share_preview_cleanup(*, created=False):
    token = reserve_share_preview_cleanup(created=created)
    if token is not None:
        try:
            task_cleanup_share_previews.enqueue(token=token)
        except Exception:
            release_share_preview_cleanup(token)
            logger.exception('Failed to enqueue share preview cleanup')


@task(priority=-1)
def task_cleanup_share_previews(*, count_only=False, token=None):
    """The existing single DB worker serializes every cleanup and count-only run."""
    try:
        result = prune_previews(count_only=count_only)
        set_share_preview_count(result['remaining'])
        logger.info('Share preview cleanup: count_only=%s result=%s', count_only, result)
        return result
    finally:
        release_share_preview_cleanup(token)


def helper_video_pluck(video: VideoModel):
    if is_custom_pluck_video(video):
        task_video_pluck.enqueue(video.id)


@task(priority=-1)
def task_video_pluck(video_id: int):
    video = VideoModel.objects.get(id=video_id)
    with original_file(video.file.name, video.compression_format, video.original_filename) as replay:
        pluck = normalize_pluck(calculate_pluck(replay.name, replay.read()))
    video.pluck = pluck
    video.save(update_fields=['pluck'])
