from django.db import transaction

from userprofile.models import UserProfile
from .cache import invalidate_flow
from ..models import AccountGitHub, AccountLinkQueue, Platform


@transaction.atomic
def unlink_github_account(user_id):
    UserProfile.objects.select_for_update().get(pk=user_id)
    AccountGitHub.objects.filter(parent_id=user_id).delete()
    AccountLinkQueue.objects.filter(userprofile_id=user_id, platform=Platform.GITHUB).delete()
    invalidate_flow(user_id)
