from django.db.models import Exists, OuterRef, Q
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from config.text_choices import MS_TextChoices
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
        count, size, tournament = 1, instance.file_size, instance.ongoing_tournament
    elif any(field_changed(instance, field) for field in ('file_size', 'player_id')):
        old_values = instance._old_values
        tournament = VideoModel.objects.using(using).filter(pk=instance.pk).filter(Q(ongoing_tournament=True) | Q(tournaments__isnull=False)).exists()
        old_size = old_values.get('file_size', instance.file_size)
        old_userms_id = userms_id
        if field_changed(instance, 'player_id'):
            old_userms_id = UserMS.objects.using(using).filter(parent__pk=old_values['player_id']).values_list('pk', flat=True).first()
        if old_userms_id != userms_id:
            transfer_video_statistics(old_userms_id, userms_id, tournament=tournament, old_size=old_size, size=instance.file_size, limit=limit, using=using)
            return
        size = instance.file_size - old_size
    update_video_statistics(userms_id, tournament=tournament, count=count, size=size, limit=limit, using=using)


@receiver(pre_delete, sender=VideoModel, dispatch_uid='msuser.update_video_count_on_video_delete')
def update_video_count_on_video_delete(sender, instance: VideoModel, using, **kwargs):
    # Read current membership before cascading deletion removes tournament relations.
    video = (
        VideoModel.objects.using(using).filter(pk=instance.pk)
        .annotate(has_tournament=Exists(VideoModel.tournaments.through.objects.using(using).filter(videomodel_id=OuterRef('pk'))))
        .values('player__userms_id', 'file_size', 'ongoing_tournament', 'has_tournament').first()
    )
    if video is None:
        return
    update_video_statistics(video['player__userms_id'], tournament=video['ongoing_tournament'] or video['has_tournament'], count=-1, size=-video['file_size'], using=using)
