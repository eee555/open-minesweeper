from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver

from msuser.models import UserMS
from .models import QQConnectIdentity, UserProfile
from .qqconnect.cache import invalidate_user_flow


@receiver(pre_delete, sender=QQConnectIdentity, dispatch_uid='userprofile.revoke_qq_login')
def revoke_qq_login(sender, instance, using, **kwargs):
    # 与绑定回调锁定同一用户；在提交释放行锁前撤销，不让在途回调重新建回身份。
    UserProfile.objects.using(using).select_for_update().only('pk').get(pk=instance.parent_id)
    invalidate_user_flow(instance.parent_id)


@receiver(post_delete, sender=UserProfile, dispatch_uid='userprofile.delete_user_ms')
def delete_user_ms(sender, instance: UserProfile, using, origin, **kwargs):
    # A UserMS deletion already includes its profile in the same collector.
    if isinstance(origin, UserMS) or getattr(origin, 'model', None) is UserMS:
        return
    if instance.userms_id is not None:
        UserMS.objects.using(using).filter(pk=instance.userms_id).delete()
