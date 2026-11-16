from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from config.text_choices import MS_TextChoices, Tournament_TextChoices
from videomanager.models import VideoModel
from .cache import TournamentCache
from .models import GSCParticipant, GSCTournament, Tournament, TournamentParticipant, TournamentUser, WeeklyEffParticipant, WeeklyEffTournament, WeeklyParticipant, WeeklyTournament
from .services import (
    add_existing_videos_to_participant_tournament,
    checkin_with_arbiter,
    checkin_with_token,
)

cache = TournamentCache()
PARTICIPANT_CACHE_FIELDS = {
    'token',
    'arbiter_identifier',
    'arbiter_identifier_id',
    'tournament',
    'tournament_id',
    'user',
    'user_id',
    'start_time',
    'end_time',
}


def participant_cache_fields_changed(update_fields):
    return update_fields is None or bool(PARTICIPANT_CACHE_FIELDS.intersection(update_fields))


@receiver(pre_save, sender=VideoModel, dispatch_uid='tournament.checkin_video_before_create')
def checkin_video_before_create(sender, instance: VideoModel, **kwargs):
    if instance.pk is not None:
        return
    if instance.upload_time is None:  # pre_save阶段这个字段尚未创建
        instance.upload_time = timezone.now()

    checked_in_tournaments = []
    if instance.software == MS_TextChoices.Software.AVF:
        checked_in_tournaments.extend(checkin_with_arbiter(instance, instance.video.identifier))
    else:
        checked_in_tournaments.extend(checkin_with_token(instance, instance.video.tournament_identifier))
    instance._checked_in_tournaments = checked_in_tournaments


@receiver(post_save, sender=VideoModel, dispatch_uid='tournament.add_created_video_to_checked_tournaments')
def add_created_video_to_checked_tournaments(sender, instance: VideoModel, created: bool, **kwargs):
    if not created:
        return
    for tournament in getattr(instance, '_checked_in_tournaments', []):
        tournament.videos.add(instance)


@receiver(post_delete, sender=Tournament, dispatch_uid='tournament.update_cache_on_tournament_delete')
def update_cache_on_tournament_delete(sender, instance: Tournament, **kwargs):
    tournament_id = instance.id
    transaction.on_commit(lambda: cache.remove_tournament(tournament_id))


@receiver(post_save, sender=GSCTournament, dispatch_uid='tournament.update_cache_on_gsc_save')
@receiver(post_save, sender=WeeklyEffTournament, dispatch_uid='tournament.update_cache_on_weekly_eff_save')
@receiver(post_save, sender=WeeklyTournament, dispatch_uid='tournament.update_cache_on_weekly_save')
@receiver(post_save, sender=Tournament, dispatch_uid='tournament.update_cache_on_tournament_save')
def update_cache_on_tournament_save(sender, instance: Tournament, **kwargs):
    transaction.on_commit(lambda: cache.update_tournament(instance))


@receiver(post_save, sender=GSCParticipant, dispatch_uid='tournament.update_cache_on_gsc_participant_save')
@receiver(post_save, sender=WeeklyEffParticipant, dispatch_uid='tournament.update_cache_on_weekly_eff_participant_save')
@receiver(post_save, sender=WeeklyParticipant, dispatch_uid='tournament.update_cache_on_weekly_participant_save')
@receiver(post_save, sender=TournamentParticipant, dispatch_uid='tournament.update_cache_on_participant_save')
def update_cache_on_participant_save(sender, instance, created: bool, update_fields=None, **kwargs):
    if not participant_cache_fields_changed(update_fields):
        return
    if instance.user_id is not None:
        transaction.on_commit(lambda: cache.update_participant(instance))
    if created:
        add_existing_videos_to_participant_tournament(instance)


@receiver(post_save, sender=GSCParticipant, dispatch_uid='tournament.ensure_tournament_user_on_gsc_participant_create')
@receiver(post_save, sender=WeeklyEffParticipant, dispatch_uid='tournament.ensure_tournament_user_on_weekly_eff_participant_create')
@receiver(post_save, sender=WeeklyParticipant, dispatch_uid='tournament.ensure_tournament_user_on_weekly_participant_create')
@receiver(post_save, sender=TournamentParticipant, dispatch_uid='tournament.ensure_tournament_user_on_participant_create')
def ensure_tournament_user_on_participant_create(sender, instance: TournamentParticipant, created: bool, **kwargs):
    if not created or instance.user_id is None:
        return
    TournamentUser.objects.get_or_create(user_id=instance.user_id)


@receiver(post_delete, sender=TournamentParticipant, dispatch_uid='tournament.remove_participant_cache_on_delete')
def remove_participant_cache_on_delete(sender, instance: TournamentParticipant, **kwargs):
    user_id = instance.user_id
    if user_id is None:
        return
    tournament_id = instance.tournament_id
    participant_id = instance.id
    transaction.on_commit(lambda: cache.remove_participant(user_id, tournament_id, participant_id=participant_id))


@receiver(post_delete, sender=TournamentParticipant, dispatch_uid='tournament.revoke_rank_score_on_participant_delete')
def revoke_rank_score_on_participant_delete(sender, instance: TournamentParticipant, **kwargs):
    if instance.user_id is None or instance.rank_score == 0:
        return
    tournament = instance.tournament
    fields = ['score_current', 'last_updated', 'score_total']
    if tournament.subclass == Tournament_TextChoices.Subclass.GSC:
        category = 'gsc'
        fields.append('gsc_total')
    elif tournament.subclass == Tournament_TextChoices.Subclass.WEEKLY_EFF:
        category = 'weekly_eff'
        fields.append('weekly_eff_total')
    else:
        category = 'weekly_classic'
        fields.extend(['weekly_total', 'weekly_classic_total'])

    tournament_user = TournamentUser.objects.select_for_update().get(user_id=instance.user_id)
    # 以原比赛结束时间撤回积分，由 add_score 将负差额衰减到用户现有时间基准。
    tournament_user.add_score(-instance.rank_score, tournament.end_time, category=category)
    tournament_user.save(update_fields=fields)
    transaction.on_commit(lambda: cache.update_tournament_user(tournament_user, fields=fields))
