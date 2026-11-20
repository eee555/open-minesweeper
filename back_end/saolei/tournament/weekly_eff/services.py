import logging

from django.db import transaction
from django.db.models import ExpressionWrapper, F, FloatField, Value, Window
from django.db.models.functions import Cast, RowNumber

from config.text_choices import MS_TextChoices, Tournament_TextChoices
from tournament.cache import TournamentCache
from tournament.models import TournamentUser, WeeklyEffParticipant, WeeklyEffTournament
from .utils import default_weekly_eff_et, default_weekly_eff_it, WEEKLY_EFF_BEST_FIELDS, WEEKLY_EFF_DEFAULT_SCORE

logger = logging.getLogger('tournament')
cache = TournamentCache()


def refresh_weekly_eff_scores(tournament: WeeklyEffTournament, *, batch_size=1000):
    logger.info(f'效率打卡赛#{tournament.id} 成绩刷新开始')
    participants = list(WeeklyEffParticipant.objects.filter(tournament=tournament))
    by_user = {participant.user_id: participant for participant in participants if participant.user_id is not None}
    for participant in participants:
        participant.et = default_weekly_eff_et()
        participant.it = default_weekly_eff_it()
        participant.score = WEEKLY_EFF_DEFAULT_SCORE

    videos = tournament.videos.filter(
        state=MS_TextChoices.State.OFFICIAL, mode=MS_TextChoices.Mode.STD,
        timems__gt=0, cl__gt=0, bv__gt=0,
    ).annotate(eff_score=ExpressionWrapper(
        Cast(F('timems'), FloatField()) * F('cl') ** 2
        / (Value(1000.0) * F('bv') ** 2),
        output_field=FloatField(),
    ))
    # 两个级别独立选取；直接使用原始浮点比值，不用显示精度量化成绩。
    for level, count, limit, field in [('e', 2, 240.0, 'et'), ('i', 5, 60.0, 'it')]:
        selected = videos.filter(level=level, eff_score__lt=limit).annotate(
            position=Window(expression=RowNumber(), partition_by=[F('player_id')], order_by=F('eff_score').asc()),
        ).filter(position__lte=count).values_list('id', 'player_id', 'eff_score', 'position')
        for video_id, user_id, score, position in selected.iterator(chunk_size=batch_size):
            if user_id in by_user:
                getattr(by_user[user_id], field)[position - 1] = (video_id, float(score))

    for participant in participants:
        participant.score = sum(score for _, score in participant.et) + sum(score for _, score in participant.it)
    WeeklyEffParticipant.objects.bulk_update(participants, ['et', 'it', 'score'], batch_size=batch_size)
    logger.info(f'效率打卡赛#{tournament.id} 成绩刷新完成，人数 {len(participants)}')
    return len(participants)


def update_weekly_eff_best(tournament_user: TournamentUser, tournament: WeeklyEffTournament, participant: WeeklyEffParticipant):
    if participant.user_id is None or tournament.state != Tournament_TextChoices.State.AWARDED:
        return False
    if tournament_user.weekly_eff_best is not None and tournament_user.weekly_eff_best <= participant.score:
        return False
    tournament_user.weekly_eff_best = participant.score
    tournament_user.weekly_eff_best_year = tournament.year
    tournament_user.weekly_eff_best_week = tournament.week
    return True


def calculate_weekly_eff_best(user_id: int):
    participant = (
        WeeklyEffParticipant.objects
        .filter(user_id=user_id, tournament__state=Tournament_TextChoices.State.AWARDED)
        .select_related('tournament__weeklyefftournament').order_by('score').first()
    )
    if participant is None:
        return None, None, None
    tournament = participant.tournament.weeklyefftournament
    return participant.score, tournament.year, tournament.week


def refresh_weekly_eff_best_scores(tournament: WeeklyEffTournament, *, batch_size=1000, rebuild=False):
    logger.info(f'效率打卡赛#{tournament.id} best 刷新开始')
    participants = WeeklyEffParticipant.objects.filter(tournament=tournament, user_id__isnull=False).select_related('user__tournamentuser')
    users = []
    updated = 0
    for participant in participants:
        user = participant.user.tournamentuser
        if rebuild:
            best = calculate_weekly_eff_best(participant.user_id)
            updated += tuple(getattr(user, field) for field in WEEKLY_EFF_BEST_FIELDS) != best
            for field, value in zip(WEEKLY_EFF_BEST_FIELDS, best):
                setattr(user, field, value)
        else:
            updated += update_weekly_eff_best(user, tournament, participant)
        users.append(user)
    TournamentUser.objects.bulk_update(users, WEEKLY_EFF_BEST_FIELDS, batch_size=batch_size)
    transaction.on_commit(lambda: cache.update_tournament_users(users, fields=WEEKLY_EFF_BEST_FIELDS))
    logger.info(f'效率打卡赛#{tournament.id} best 刷新完成，人数 {updated}')
    return updated
