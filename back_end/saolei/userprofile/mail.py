from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from .models import EmailSentQuota


def reserve_email_quota() -> bool:
    """Commit the reservation before SMTP, independently of business writes."""
    quota_zone = ZoneInfo(settings.EMAIL_QUOTA_TIME_ZONE)
    # Finish competing unique-key inserts before any sender upgrades to a row lock.
    # Otherwise MySQL can deadlock on the losing insert's shared duplicate-key lock.
    with transaction.atomic(durable=True):
        EmailSentQuota.objects.get_or_create(
            pk=1, defaults={'quota_date': timezone.localdate(timezone.now(), quota_zone)},
        )
    with transaction.atomic(durable=True):
        quota = EmailSentQuota.objects.select_for_update().get(pk=1)
        # A request waiting for the row lock must not reset to yesterday.
        today = timezone.localdate(timezone.now(), quota_zone)
        if quota.quota_date > today:
            return False
        if quota.quota_date < today:
            quota.quota_date = today
            quota.count = 0
        if quota.count >= settings.EMAIL_DAILY_LIMIT:
            return False
        quota.count += 1
        quota.save(update_fields=['quota_date', 'count'])
    return True


def send_budgeted_email(message: EmailMessage) -> int:
    if settings.EMAIL_SKIP or settings.E2E_TEST:
        return 0
    recipients = message.recipients()
    if len(recipients) != 1:
        raise ValueError('Budgeted email must have exactly one recipient.')
    if not recipients[0] or recipients[0].lower().endswith('@accounts.invalid'):
        return 0
    if not reserve_email_quota():
        return 0
    # Failed or uncertain sends keep their reservation.
    return message.send()
