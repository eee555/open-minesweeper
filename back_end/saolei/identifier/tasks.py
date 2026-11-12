import logging

from django.db import transaction
from django.tasks import task

from config.text_choices import MS_TextChoices
from customranking.services import add_videos_to_custom_pluck_ranks, remove_videos_from_custom_pluck_ranks
from effranking.services import add_videos_to_eff_ranks, remove_videos_from_eff_ranks
from msuser.services import update_video_count_limit_from_videos
from speedranking.services import add_videos_to_speed_ranks, remove_videos_from_speed_ranks
from userprofile.models import UserProfile
from utils.ranking_lock import ranking_access
from videomanager.cache import newest_cache
from videomanager.events import videos_bulk_changed
from videomanager.models import VideoModel
from .models import Identifier

logger = logging.getLogger(__name__)


@task(priority=1)
@ranking_access(operation='identifier.sync_videos')
def task_sync_identifier_videos(identifier_text: str, player_id: int):
    """按标识执行时的绑定状态，批量同步录像状态及排行、缓存补偿。"""
    profile = UserProfile.objects.select_related('userms').filter(pk=player_id).first()
    if profile is None or profile.userms is None:
        logger.info('Identifier %r video sync skipped: player #%s is gone', identifier_text, player_id)
        return 0

    # 以当前绑定关系为准，连续绑定/解绑留下的多条任务最终收敛到同一状态；重复执行无副作用。
    bound = Identifier.objects.filter(identifier=identifier_text, userms_id=profile.userms_id).exists()
    source_state = MS_TextChoices.State.IDENTIFIER if bound else MS_TextChoices.State.OFFICIAL
    target_state = MS_TextChoices.State.OFFICIAL if bound else MS_TextChoices.State.IDENTIFIER

    with transaction.atomic():
        videoquery = VideoModel.objects.filter(
            player_id=player_id,
            video__identifier=identifier_text,
            state=source_state,
        )
        videos = list(videoquery)
        if not videos:
            return 0
        video_ids = {video.id for video in videos}

        videoquery.update(state=target_state)
        videos_bulk_changed.send(sender=VideoModel, player_ids=[player_id])

        if bound:
            refreshed_videos = VideoModel.objects.filter(id__in=video_ids)
            newest_cache.update_bulk(refreshed_videos)
            update_video_count_limit_from_videos(profile.userms, refreshed_videos)
            add_videos_to_speed_ranks(refreshed_videos)
            add_videos_to_custom_pluck_ranks(refreshed_videos)
            add_videos_to_eff_ranks(refreshed_videos)
        else:
            for video in videos:
                video.state = target_state
            newest_cache.update_bulk(videos)
            remove_videos_from_custom_pluck_ranks(video_ids)
            remove_videos_from_speed_ranks(VideoModel.objects.filter(id__in=video_ids))
            remove_videos_from_eff_ranks(VideoModel.objects.filter(id__in=video_ids))

    logger.info('Identifier %r video sync done: player=#%s bound=%s videos=%s', identifier_text, player_id, bound, len(video_ids))
    return len(video_ids)
