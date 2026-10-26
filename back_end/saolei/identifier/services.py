from django.db import transaction

from config.text_choices import MS_TextChoices
from customranking.services import add_videos_to_custom_pluck_ranks, remove_videos_from_custom_pluck_ranks
from effranking.services import add_videos_to_eff_ranks, remove_videos_from_eff_ranks
from msuser.models import UserMS
from msuser.services import update_video_count_limit_from_videos
from speedranking.services import add_videos_to_speed_ranks, remove_videos_from_speed_ranks
from utils.exceptions import ExceptionToResponse
from utils.ranking_lock import ranking_access
from videomanager.cache import newest_cache
from videomanager.events import videos_bulk_changed
from videomanager.models import VideoModel
from .models import Identifier


@ranking_access(operation='identifier.bind')
def bind_identifier(identifier: Identifier, userms: UserMS):
    """绑定标识，并批量吸收因此转为 OFFICIAL 的录像。"""
    if not identifier.safe:
        raise ExceptionToResponse('identifier', 'invalid')
    if identifier.userms_id is not None and identifier.userms_id != userms.id:
        raise ExceptionToResponse('identifier', 'collision')

    with transaction.atomic():
        if identifier.identifier not in userms.identifiers:
            userms.identifiers.append(identifier.identifier)
            userms.save(update_fields=['identifiers'])

        if identifier.userms_id != userms.id:
            identifier.userms = userms
            identifier.save(update_fields=['userms'])

        videoquery = VideoModel.objects.filter(
            player=userms.parent,
            video__identifier=identifier.identifier,
            state=MS_TextChoices.State.IDENTIFIER,
        )
        video_ids = list(videoquery.values_list('id', flat=True))
        if not video_ids:
            return 0
        videoquery.update(state=MS_TextChoices.State.OFFICIAL)
        videos_bulk_changed.send(sender=VideoModel, player_ids=[userms.parent.pk])

        refreshed_videos = VideoModel.objects.filter(id__in=video_ids)
        newest_cache.update_bulk(refreshed_videos)
        update_video_count_limit_from_videos(userms, refreshed_videos)
        add_videos_to_speed_ranks(refreshed_videos)
        add_videos_to_custom_pluck_ranks(refreshed_videos)
        add_videos_to_eff_ranks(refreshed_videos)

    return len(video_ids)


@ranking_access(operation='identifier.unbind')
def unbind_identifier(identifier: Identifier, userms: UserMS | None = None):
    """解绑标识，并批量移除因此失去 OFFICIAL 状态的录像影响。"""
    if userms is None:
        userms = identifier.userms
    if userms is None:
        raise ValueError('Identifier is not bound')
    if identifier.userms_id is not None and identifier.userms_id != userms.id:
        raise ValueError('Identifier is bound to another user')

    with transaction.atomic():
        videoquery = VideoModel.objects.filter(
            player=userms.parent,
            video__identifier=identifier.identifier,
            state=MS_TextChoices.State.OFFICIAL,
        )
        videos = list(videoquery.select_related('video'))
        video_ids = {video.id for video in videos}

        if identifier.identifier in userms.identifiers:
            userms.identifiers.remove(identifier.identifier)
            userms.save(update_fields=['identifiers'])

        if identifier.userms_id is not None:
            identifier.userms = None
            identifier.save(update_fields=['userms'])

        if videos:
            for video in videos:
                video.state = MS_TextChoices.State.IDENTIFIER
            videoquery.update(state=MS_TextChoices.State.IDENTIFIER)
            videos_bulk_changed.send(sender=VideoModel, player_ids=[userms.parent.pk])
            newest_cache.update_bulk(videos)
            remove_videos_from_custom_pluck_ranks(video_ids)

            remove_videos_from_speed_ranks(VideoModel.objects.filter(id__in=video_ids))
            remove_videos_from_eff_ranks(VideoModel.objects.filter(id__in=video_ids))

    return len(video_ids)


def set_safe(identifier: Identifier, safe: bool):
    """设置标识安全状态；标识绑定用户时不能设为不安全。"""
    if not safe and identifier.userms_id is not None:
        raise ValueError('Bound identifier cannot be marked unsafe')
    if identifier.safe == safe:
        return

    identifier.safe = safe
    identifier.save(update_fields=['safe'])
