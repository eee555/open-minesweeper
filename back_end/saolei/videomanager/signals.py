import logging

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from config.text_choices import MS_TextChoices
from .cache import newest_cache
from .models import ExpandVideoModel, VideoModel

logger = logging.getLogger('videomanager')

STATE_QUEUE_NAMES = {
    MS_TextChoices.State.IDENTIFIER: newest_cache,
    MS_TextChoices.State.OFFICIAL: newest_cache,
}

CAPTURE_FIELDS = {
    'state',
    'file_size',
    'ongoing_tournament',
    'pluck',
    'timems',
    'upload_time',
    'software',
    'player_id',
    'level',
    'mode',
    'bv',
    'left_ce',
    'right_ce',
    'double_ce',
    'left',
    'right',
    'double',
    'path',
}

QUEUE_PAYLOAD_FIELDS = {
    'upload_time',
    'player_id',
}


def get_old_value(instance: VideoModel, field: str):
    return getattr(instance, '_old_values', {}).get(field)


def field_changed(instance: VideoModel, field: str) -> bool:
    old_values = getattr(instance, '_old_values', {})
    return field in old_values and old_values[field] != getattr(instance, field)


def remove_from_state_queue(video: VideoModel, state: str):
    queue_cache = STATE_QUEUE_NAMES.get(state)
    if queue_cache is not None:
        queue_cache.remove(video)


def add_to_state_queue(video: VideoModel):
    queue_cache = STATE_QUEUE_NAMES.get(video.state)
    if queue_cache is not None:
        queue_cache.add(video)


@receiver(pre_save, sender=VideoModel, dispatch_uid='videomanager.capture_previous_video_state')
def capture_video_update(sender, instance: VideoModel, update_fields=None, **kwargs):
    if instance.pk is None:
        instance._old_values = {}
        return
    if update_fields is None:
        fields = CAPTURE_FIELDS
    else:
        normalized_update_fields = {'player_id' if field == 'player' else field for field in update_fields}
        fields = normalized_update_fields & CAPTURE_FIELDS

    if not fields:
        instance._old_values = {}
        return

    instance._old_values = VideoModel.objects.filter(pk=instance.pk).values(*fields).first() or {}


@receiver(post_save, sender=VideoModel, dispatch_uid='videomanager.refresh_state_queue_on_video_save')
def refresh_state_queue_on_video_save(sender, instance: VideoModel, created, update_fields=None, **kwargs):
    if created:
        add_to_state_queue(instance)
        logger.info(f'录像#{instance.id} 状态 初始化为 {instance.state}')
        return

    if field_changed(instance, 'state'):
        old_state = get_old_value(instance, 'state')
        remove_from_state_queue(instance, old_state)
        add_to_state_queue(instance)
        logger.info(f'录像#{instance.id} 状态 从 {old_state} 到 {instance.state}')
        return

    if field_changed(instance, 'ongoing_tournament'):
        if instance.ongoing_tournament:
            remove_from_state_queue(instance, instance.state)
            logger.info(f'录像#{instance.id} 进入比赛，已从普通队列移除')
        else:
            add_to_state_queue(instance)
            logger.info(f'录像#{instance.id} 离开比赛，已按状态恢复队列')
        return

    if any(field_changed(instance, field) for field in QUEUE_PAYLOAD_FIELDS):
        remove_from_state_queue(instance, instance.state)
        add_to_state_queue(instance)


@receiver(post_delete, sender=VideoModel, dispatch_uid='videomanager.delete_video_expansion')
def delete_video_expansion(sender, instance: VideoModel, using, origin, **kwargs):
    # Deleting an expansion already cascades to its video in the same collector.
    if isinstance(origin, ExpandVideoModel) or getattr(origin, 'model', None) is ExpandVideoModel:
        return
    ExpandVideoModel.objects.using(using).filter(pk=instance.video_id).delete()
