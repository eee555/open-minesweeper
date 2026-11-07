from django.db.models.signals import pre_delete
from django.dispatch import receiver

from userprofile.models import UserProfile
from .github.cache import invalidate_flow
from .models import AccountGitHub


@receiver(pre_delete, sender=AccountGitHub)
def invalidate_github_authorizations_on_delete(sender, instance, **kwargs):
    """兼容本人旧解绑入口、管理员解绑、QuerySet 删除及用户级联删除。"""
    UserProfile.objects.select_for_update().filter(pk=instance.parent_id).exists()
    invalidate_flow(instance.parent_id)
