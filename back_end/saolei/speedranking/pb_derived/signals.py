from functools import partial

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from userprofile.models import UserProfile
from .services import remove_player


@receiver(post_delete, sender=UserProfile, dispatch_uid='speedranking.pb_derived.delete_player')
def delete_derived_records(sender, instance: UserProfile, **kwargs):
    transaction.on_commit(partial(remove_player, instance.pk))
