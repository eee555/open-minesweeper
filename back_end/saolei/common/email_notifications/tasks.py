from functools import partial
import logging

from django.conf import settings
from django.db import transaction
from django.tasks import task

from accountlink.models import AccountLinkQueue
from config.text_choices import MS_TextChoices
from identifier.models import Identifier
from media.models import Media
from media.utils import MediaStatus
from userprofile.mail import send_budgeted_email
from userprofile.models import UserProfile
from userprofile.utils import EMAIL_NOTIFICATION_FLAGS, EmailNotificationType
from videomanager.models import VideoModel
from .mail import MultilingualNotificationEmail

logger = logging.getLogger(__name__)

SOURCES = {
    EmailNotificationType.STAFF_MEDIA_REVIEW: (Media, {'status': MediaStatus.PENDING}, '/staff/media'),
    EmailNotificationType.STAFF_VIDEO_FROZEN: (VideoModel, {'state': MS_TextChoices.State.FROZEN}, '/staff/videomodel'),
    EmailNotificationType.STAFF_VIDEO_PLAIN: (VideoModel, {'state': MS_TextChoices.State.PLAIN}, '/staff/videomodel'),
    EmailNotificationType.STAFF_ACCOUNT_LINK_REVIEW: (AccountLinkQueue, {'verified': False}, '/staff/accountlink'),
    EmailNotificationType.STAFF_IDENTIFIER_UNSAFE: (Identifier, {'safe': False}, '/staff/identifier'),
}


def notifications_enabled() -> bool:
    return not settings.EMAIL_SKIP and not settings.E2E_TEST


def enqueue_notification(notification_type: EmailNotificationType, object_id: int, *, using: str = 'default'):
    """The request only registers one guarded enqueue, never executes the task."""
    try:
        if notifications_enabled():
            transaction.on_commit(
                partial(task_send_staff_notification.enqueue, notification_type.value, [object_id]),
                using=using, robust=True,
            )
    except Exception:
        logger.exception('Notification enqueue registration failed: type=%s object_id=%s', notification_type, object_id)


@task(priority=-1)
def task_send_staff_notification(notification_type: str, object_ids: list[int]) -> int:
    if not notifications_enabled():
        return 0
    try:
        kind = EmailNotificationType(notification_type)
        model, filters, review_path = SOURCES[kind]
        pending_ids = list(model.objects.filter(pk__in=object_ids, **filters).order_by('pk').values_list('pk', flat=True))
        if not pending_ids:
            return 0
        recipients = list(UserProfile.objects.filter(
            is_active=True, is_staff=True, is_memorial=False,
        ).exclude(email='').exclude(email__iendswith='@accounts.invalid').only('pk', 'email', 'email_notification_mask').order_by('pk'))
    except Exception:
        logger.exception('Notification preparation failed: type=%s object_ids=%s', notification_type, object_ids)
        return 0
    sent = 0
    for recipient in recipients:
        if not recipient.email_notification_mask & EMAIL_NOTIFICATION_FLAGS[kind]:
            continue
        try:
            # No retry: a timeout can mean the provider already accepted it.
            message = MultilingualNotificationEmail(kind, pending_ids, review_path, recipient)
            accepted = send_budgeted_email(message)
            sent += accepted
            logger.info('Notification send result: type=%s objects=%s recipient_id=%s accepted=%s', kind, pending_ids, recipient.pk, accepted)
        except Exception:
            logger.exception('Notification send failed: type=%s objects=%s recipient_id=%s', kind, pending_ids, recipient.pk)
    return sent
