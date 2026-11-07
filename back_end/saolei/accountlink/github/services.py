from django.db import transaction

from userprofile.models import UserProfile
from .cache import invalidate_flow
from ..models import AccountGitHub, AccountLinkQueue, Platform


@transaction.atomic
def unlink_github_account(user_id, identifier=None):
    UserProfile.objects.select_for_update().get(pk=user_id)
    accounts = AccountGitHub.objects.filter(parent_id=user_id)
    if identifier is None:
        account = accounts.first()
        if account is None:
            # 此时无数据库关联可删除，仅取消未完成授权，立即阻止在途回调。
            invalidate_flow(user_id)
            return
        identifier = str(account.pk)
        delete_account = True
    else:
        delete_account = AccountLinkQueue.objects.filter(
            userprofile_id=user_id, platform=Platform.GITHUB, identifier=identifier, verified=True,
        ).exists()
    if delete_account:
        accounts.filter(pk=identifier).delete()
    AccountLinkQueue.objects.filter(userprofile_id=user_id, platform=Platform.GITHUB, identifier=identifier).delete()
