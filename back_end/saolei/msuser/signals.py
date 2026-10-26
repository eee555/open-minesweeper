from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from config.text_choices import MS_TextChoices
from videomanager.models import VideoModel
from .services import decrement_video_count, increment_video_count
from .utils import get_video_num_limit


@receiver(post_save, sender=VideoModel, dispatch_uid='msuser.update_video_count_on_video_save')
def update_video_count_on_video_save(sender, instance: VideoModel, created: bool, update_fields=None, **kwargs):
    if created and not instance.ongoing_tournament and (userms := instance.player.userms) is not None:
        increment_video_count(userms)


@receiver(post_save, sender=VideoModel, dispatch_uid='msuser.update_video_count_limit_on_video_save')
def update_video_count_limit_on_video_save(sender, instance: VideoModel, created: bool, update_fields=None, **kwargs):
    if instance.mode == MS_TextChoices.Mode.STD and instance.level == MS_TextChoices.Level.EXPERT and instance.state == MS_TextChoices.State.OFFICIAL:
        userms = instance.player.userms
        video_num_limit = get_video_num_limit(instance.timems)
        if video_num_limit > userms.video_num_limit:
            userms.video_num_limit = video_num_limit
            userms.save(update_fields=['video_num_limit'])


@receiver(pre_delete, sender=VideoModel, dispatch_uid='msuser.update_video_count_on_video_delete')
def update_video_count_on_video_delete(sender, instance: VideoModel, **kwargs):
    # Check before cascading deletion removes the tournament-video relations.
    if instance.ongoing_tournament or instance.tournaments.exists():
        return
    if (userms := instance.player.userms) is not None:
        decrement_video_count(userms)
