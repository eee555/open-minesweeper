from django.db.models.signals import pre_delete
from django.dispatch import receiver

from userprofile.models import UserProfile
from .github.cache import invalidate_flow
from .models import AccountGitHub


@receiver(pre_delete, sender=AccountGitHub)
def invalidate_github_authorizations_on_delete(sender, instance, using, **kwargs):
    """兼容本人旧解绑入口、管理员解绑、QuerySet 删除及用户级联删除。"""
    # 与 OAuth 提交锁定同一用户；此串行化保证依赖生产 MySQL 的行锁，SQLite 不提供。
    user = UserProfile.objects.using(using).select_for_update().only('pk').get(pk=instance.parent_id)
    # 必须在释放行锁前撤销，阻止在途回调恢复关联；删除回滚也不恢复授权。
    invalidate_flow(user.pk)
