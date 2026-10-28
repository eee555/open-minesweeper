from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from videomanager.models import VideoModel
from videomanager.signals import field_changed
from .services import sync_video

RANKING_FIELDS = {'player_id', 'level', 'mode', 'state', 'ongoing_tournament', 'bv', 'left_ce', 'right_ce', 'double_ce', 'upload_time'}
NF_CATEGORY_FIELDS = ('player_id', 'level', 'mode', 'state', 'ongoing_tournament', 'right_ce')


@receiver(post_save, sender=VideoModel, dispatch_uid='effranking.video_saved')
def refresh_ranks_on_video_save(sender, instance: VideoModel, created, raw=False, **kwargs):
    if raw:
        return
    if not created and not any(field_changed(instance, field) for field in RANKING_FIELDS):
        return
    previous = {field: getattr(instance, '_old_values', {}).get(field, getattr(instance, field)) for field in NF_CATEGORY_FIELDS}
    sync_video(instance.pk, previous)


@receiver(post_delete, sender=VideoModel, dispatch_uid='effranking.video_deleted')
def refresh_ranks_on_video_delete(sender, instance: VideoModel, **kwargs):
    sync_video(instance.pk, {field: getattr(instance, field) for field in NF_CATEGORY_FIELDS})
