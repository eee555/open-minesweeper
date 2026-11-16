from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from tournament.cache import TournamentCache
from tournament.models import TournamentUser, WeeklyEffParticipant
from .services import calculate_weekly_eff_best, update_weekly_eff_best
from .utils import WEEKLY_EFF_BEST_FIELDS

cache = TournamentCache()


@receiver(post_save, sender=WeeklyEffParticipant)
def update_best_score_on_weekly_eff_participant_save(sender, instance, created, update_fields=None, **kwargs):
    if instance.user_id is None or (update_fields is not None and 'score' not in update_fields):
        return
    user, _ = TournamentUser.objects.get_or_create(user_id=instance.user_id)
    if update_weekly_eff_best(user, instance.tournament.weeklyefftournament, instance):
        user.save(update_fields=WEEKLY_EFF_BEST_FIELDS)
        transaction.on_commit(lambda: cache.update_tournament_user(user, fields=WEEKLY_EFF_BEST_FIELDS))


@receiver(post_delete, sender=WeeklyEffParticipant)
def update_best_score_on_weekly_eff_participant_delete(sender, instance, **kwargs):
    if instance.user_id is None:
        return
    user = TournamentUser.objects.get(user_id=instance.user_id)
    for field, value in zip(WEEKLY_EFF_BEST_FIELDS, calculate_weekly_eff_best(instance.user_id)):
        setattr(user, field, value)
    user.save(update_fields=WEEKLY_EFF_BEST_FIELDS)
    transaction.on_commit(lambda: cache.update_tournament_user(user, fields=WEEKLY_EFF_BEST_FIELDS))
