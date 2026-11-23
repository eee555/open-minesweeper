from django.db.models.signals import post_save
from django.dispatch import receiver

from accountlink.models import AccountLinkQueue
from config.text_choices import MS_TextChoices
from identifier.models import Identifier
from media.models import Media
from media.utils import MediaStatus
from userprofile.utils import EmailNotificationType
from videomanager.models import VideoModel
from videomanager.signals import field_changed
from .tasks import enqueue_notification


@receiver(post_save, sender=Media, dispatch_uid='common.email_media_review')
def notify_media_review(sender, instance, created, raw=False, using='default', **kwargs):
    if not raw and created and instance.status == MediaStatus.PENDING:
        enqueue_notification(EmailNotificationType.STAFF_MEDIA_REVIEW, instance.pk, using=using)


@receiver(post_save, sender=VideoModel, dispatch_uid='common.email_video_state')
def notify_video_state(sender, instance, created, raw=False, using='default', **kwargs):
    if raw or not (created or field_changed(instance, 'state')):
        return
    notification_type = {
        MS_TextChoices.State.FROZEN: EmailNotificationType.STAFF_VIDEO_FROZEN,
        MS_TextChoices.State.PLAIN: EmailNotificationType.STAFF_VIDEO_PLAIN,
    }.get(instance.state)
    if notification_type is not None:
        enqueue_notification(notification_type, instance.pk, using=using)


@receiver(post_save, sender=AccountLinkQueue, dispatch_uid='common.email_account_link_review')
def notify_account_link_review(sender, instance, created, raw=False, using='default', **kwargs):
    if not raw and created and not instance.verified:
        enqueue_notification(EmailNotificationType.STAFF_ACCOUNT_LINK_REVIEW, instance.pk, using=using)


@receiver(post_save, sender=Identifier, dispatch_uid='common.email_identifier_unsafe')
def notify_identifier_unsafe(sender, instance, created, raw=False, using='default', **kwargs):
    if not raw and created and not instance.safe:
        enqueue_notification(EmailNotificationType.STAFF_IDENTIFIER_UNSAFE, instance.pk, using=using)
