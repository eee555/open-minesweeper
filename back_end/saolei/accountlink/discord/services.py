from django.db import transaction

from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from .client import DiscordProfile
from ..models import AccountDiscord, AccountLinkQueue, Platform


@transaction.atomic
def discord_login_user(profile: DiscordProfile):
    parent_id = AccountDiscord.objects.filter(pk=profile.id).values_list('parent_id', flat=True).first()
    if parent_id is None:
        raise ExceptionToResponse('discord', 'not_linked', status_code=403)
    # Keep the same user -> account lock order as linking and unlinking.
    user = UserProfile.objects.select_for_update().filter(pk=parent_id).first()
    account = AccountDiscord.objects.select_for_update().filter(pk=profile.id, parent_id=parent_id).first()
    if account is None or not AccountLinkQueue.objects.filter(
        platform=Platform.DISCORD, identifier=profile.id, userprofile_id=account.parent_id, verified=True,
    ).exists():
        raise ExceptionToResponse('discord', 'not_linked', status_code=403)
    fields = profile.account_fields()
    for field, value in fields.items():
        setattr(account, field, value)
    account.save(update_fields=[*fields, 'update_time'])
    return user
