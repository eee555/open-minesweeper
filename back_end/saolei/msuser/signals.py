from django.db.models import Exists, OuterRef, Q
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from config.text_choices import MS_TextChoices
from videomanager.events import video_storage_changed
from videomanager.models import VideoModel
from videomanager.signals import field_changed
from .models import UserMS
from .services import transfer_video_statistics, update_video_statistics
from .utils import get_video_num_limit


@receiver(post_save, sender=VideoModel, dispatch_uid='msuser.update_video_count_on_video_save')
def update_video_count_on_video_save(sender, instance: VideoModel, created: bool, using, raw=False, update_fields=None, **kwargs):
    if raw:
        return
    userms_id = instance.player.userms_id
    limit = None
    if instance.mode == MS_TextChoices.Mode.STD and instance.level == MS_TextChoices.Level.EXPERT and instance.state == MS_TextChoices.State.OFFICIAL:
        userms = instance.player.userms
        video_num_limit = get_video_num_limit(instance.timems)
        if userms is not None and video_num_limit > userms.video_num_limit:
            limit = video_num_limit
            userms.video_num_limit = video_num_limit
    count, size, tournament = 0, 0, False
    if created:
        size = instance.stored_file_size if instance.stored_file_size is not None else instance.file_size
        count, tournament = 1, instance.ongoing_tournament
    elif any(field_changed(instance, field) for field in ('file_size', 'stored_file_size', 'player_id')):
        old_values = instance._old_values
        tournament = VideoModel.objects.using(using).filter(pk=instance.pk).filter(Q(ongoing_tournament=True) | Q(tournaments__isnull=False)).exists()
        old_size = old_values['stored_file_size'] if old_values['stored_file_size'] is not None else old_values['file_size']
        current_sizes = {field: getattr(instance, field) for field in ('stored_file_size', 'file_size')}
        if update_fields is not None:
            current_sizes.update({field: old_values[field] for field in current_sizes if field not in update_fields})
        size = current_sizes['stored_file_size'] if current_sizes['stored_file_size'] is not None else current_sizes['file_size']
        old_userms_id = userms_id
        if field_changed(instance, 'player_id'):
            old_userms_id = UserMS.objects.using(using).filter(parent__pk=old_values['player_id']).values_list('pk', flat=True).first()
        if old_userms_id != userms_id:
            transfer_video_statistics(old_userms_id, userms_id, tournament=tournament, old_size=old_size, size=size, limit=limit, using=using)
            return
        size -= old_size
    update_video_statistics(userms_id, tournament=tournament, count=count, size=size, limit=limit, using=using)


def _get_video_statistics(video_id, using):
    return (
        VideoModel.objects.using(using).filter(pk=video_id)
        .annotate(has_tournament=Exists(VideoModel.tournaments.through.objects.using(using).filter(videomodel_id=OuterRef('pk'))))
        .annotate(storage_size=Coalesce('stored_file_size', 'file_size'))
        .values('player__userms_id', 'storage_size', 'ongoing_tournament', 'has_tournament').first()
    )


@receiver(video_storage_changed, sender=VideoModel, dispatch_uid='msuser.update_video_size_on_storage_change')
def update_video_size_on_storage_change(sender, video_id, size_delta, using, **kwargs):
    if size_delta == 0:
        return
    video = _get_video_statistics(video_id, using)
    if video is not None:
        update_video_statistics(video['player__userms_id'], tournament=video['ongoing_tournament'] or video['has_tournament'], count=0, size=size_delta, using=using)


@receiver(pre_delete, sender=VideoModel, dispatch_uid='msuser.update_video_count_on_video_delete')
def update_video_count_on_video_delete(sender, instance: VideoModel, using, **kwargs):
    # Read current membership before cascading deletion removes tournament relations.
    video = _get_video_statistics(instance.pk, using)
    if video is None:
        return
    update_video_statistics(video['player__userms_id'], tournament=video['ongoing_tournament'] or video['has_tournament'], count=-1, size=-video['storage_size'], using=using)
