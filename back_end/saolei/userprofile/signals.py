from django.db.models.signals import post_delete
from django.dispatch import receiver

from msuser.models import UserMS
from .models import UserProfile


@receiver(post_delete, sender=UserProfile, dispatch_uid='userprofile.delete_user_ms')
def delete_user_ms(sender, instance: UserProfile, using, origin, **kwargs):
    # A UserMS deletion already includes its profile in the same collector.
    if isinstance(origin, UserMS) or getattr(origin, 'model', None) is UserMS:
        return
    if instance.userms_id is not None:
        UserMS.objects.using(using).filter(pk=instance.userms_id).delete()
