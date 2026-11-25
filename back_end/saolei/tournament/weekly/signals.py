from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from config.text_choices import Tournament_TextChoices
from tournament.cache import TournamentCache
from .services import calculate_weekly_best, update_weekly_best
from .utils import WEEKLY_SCORE_CATEGORIES
from ..models import TournamentParticipant, TournamentUser, WeeklyParticipant

tournament_cache = TournamentCache()

WEEKLY_BEST_SCORE_FIELDS = {
    'classic_score',
}


def weekly_best_score_fields_changed(update_fields):
    return update_fields is None or bool(WEEKLY_BEST_SCORE_FIELDS.intersection(update_fields))


@receiver(pre_delete, sender=WeeklyParticipant, dispatch_uid='tournament.select_weekly_before_participant_delete')
@receiver(pre_delete, sender=TournamentParticipant, dispatch_uid='tournament.select_weekly_before_parent_participant_delete')
def select_weekly_tournament_before_participant_delete(sender, instance: TournamentParticipant, **kwargs):
    if instance.user_id is None or (sender is TournamentParticipant and instance.rank_score == 0):
        return
    if instance.tournament.subclass == Tournament_TextChoices.Subclass.WEEKLY:
        # 级联删除时周赛子表可能先被删除；两个 post_delete 接收器各自需要赛制。
        instance.tournament = instance.tournament.select_subclass()


@receiver(post_save, sender=WeeklyParticipant, dispatch_uid='tournament.update_best_score_on_weekly_participant_save')
def update_best_score_on_weekly_participant_save(sender, instance: WeeklyParticipant, created: bool, update_fields=None, **kwargs):
    if instance.user_id is None or not weekly_best_score_fields_changed(update_fields):
        return
    if instance.tournament.state != Tournament_TextChoices.State.AWARDED:
        return
    tournament = instance.tournament.select_subclass()
    best_field = f'{WEEKLY_SCORE_CATEGORIES[tournament.tournament_format]}_best'
    tournament_user, _ = TournamentUser.objects.get_or_create(user_id=instance.user_id)
    if update_weekly_best(tournament_user, tournament, instance):
        tournament_user.save(update_fields=[best_field])
        tournament_cache.update_tournament_user(tournament_user, fields=[best_field])


@receiver(post_delete, sender=WeeklyParticipant, dispatch_uid='tournament.update_best_score_on_weekly_participant_delete')
def update_best_score_on_weekly_participant_delete(sender, instance: WeeklyParticipant, **kwargs):
    if instance.user_id is None:
        return
    tournament = instance.tournament.select_subclass()
    best_field = f'{WEEKLY_SCORE_CATEGORIES[tournament.tournament_format]}_best'
    tournament_user, _ = TournamentUser.objects.get_or_create(user_id=instance.user_id)
    setattr(tournament_user, best_field, calculate_weekly_best(instance.user_id, tournament.tournament_format))
    tournament_user.save(update_fields=[best_field])
    tournament_cache.update_tournament_user(tournament_user, fields=[best_field])
