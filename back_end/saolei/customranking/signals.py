from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from config.customranking import CUSTOM_PLUCK_LEVELS
from videomanager.models import VideoModel
from videomanager.signals import field_changed
from .services import sync_video

CUSTOM_PLUCK_RANK_RELATED_VIDEO_FIELDS = {
    'player_id', 'level', 'mode', 'state', 'ongoing_tournament', 'pluck', 'timems', 'upload_time',
}


@receiver(post_save, sender=VideoModel, dispatch_uid='customranking.refresh_custom_pluck_rank_on_video_save')
def refresh_custom_pluck_rank_on_video_save(sender, instance: VideoModel, created, raw=False, using=None, **kwargs):
    if raw or not (created or any(field_changed(instance, field) for field in CUSTOM_PLUCK_RANK_RELATED_VIDEO_FIELDS)):
        return
    old_values = getattr(instance, '_old_values', {})
    previous = (old_values.get('player_id', instance.player_id), old_values.get('level', instance.level))
    if previous[1] in CUSTOM_PLUCK_LEVELS or instance.level in CUSTOM_PLUCK_LEVELS:
        sync_video(instance.pk, previous, using=using)


@receiver(post_delete, sender=VideoModel, dispatch_uid='customranking.refresh_custom_pluck_rank_on_video_delete')
def refresh_custom_pluck_rank_on_video_delete(sender, instance: VideoModel, using, **kwargs):
    if instance.level in CUSTOM_PLUCK_LEVELS:
        sync_video(instance.pk, (instance.player_id, instance.level), using=using)
