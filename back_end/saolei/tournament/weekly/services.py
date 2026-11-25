import logging

from django.db.models import F, Window
from django.db.models.functions import RowNumber

from config.text_choices import MS_TextChoices, Tournament_TextChoices
from tournament.cache import TournamentCache
from tournament.models import TournamentUser, WeeklyParticipant, WeeklyTournament
from tournament.utils import default_weekly_classic_et, default_weekly_classic_it, MAX_TOURNAMENT_BEST
from .utils import weekly_encode_best, WEEKLY_SCORE_CATEGORIES, weekly_video_filters

logger = logging.getLogger('tournament')
tournament_cache = TournamentCache()


def refresh_weekly_scores(tournament: WeeklyTournament, *, batch_size=1000):
    """
    批量刷新 周赛-2高5中 成绩。
    """
    score_videos = tournament.videos.filter(state=MS_TextChoices.State.OFFICIAL, **weekly_video_filters(tournament.tournament_format))
    logger.info(f'周赛#{tournament.id} 赛制 {tournament.tournament_format} 成绩刷新开始，{tournament.year}W{tournament.week}')
    participants = list(WeeklyParticipant.objects.filter(tournament=tournament))
    if not participants:
        logger.info(f'周赛#{tournament.id} 成绩刷新跳过，没有参赛者')
        return 0
    logger.info(f'周赛#{tournament.id} 成绩刷新参赛者读取完成，数量 {len(participants)}')

    for participant in participants:
        participant.classic_et = default_weekly_classic_et()
        participant.classic_it = default_weekly_classic_it()
        participant.classic_score = 780000

    participants_by_user_id = {
        participant.user_id: participant
        for participant in participants
        if participant.user_id is not None
    }

    ranked_exp = score_videos.filter(level=MS_TextChoices.Level.EXPERT, timems__lt=240000).annotate(
        row_number=Window(
            expression=RowNumber(),
            partition_by=[F('player_id')],
            order_by='timems',
        ),
    ).filter(row_number__lte=2).values_list('id', 'player_id', 'timems')
    expert_video_count = 0
    for video_id, player_id, timems in ranked_exp.iterator(chunk_size=batch_size):
        if player_id not in participants_by_user_id:
            continue
        participants_by_user_id[player_id].classic_add_e(video_id, timems)
        expert_video_count += 1
    logger.info(f'周赛#{tournament.id} 高级录像读取完成，匹配录像 {expert_video_count} 条')

    ranked_int = score_videos.filter(level=MS_TextChoices.Level.INTERMEDIATE, timems__lt=60000).annotate(
        row_number=Window(
            expression=RowNumber(),
            partition_by=[F('player_id')],
            order_by='timems',
        ),
    ).filter(row_number__lte=5).values_list('id', 'player_id', 'timems')
    intermediate_video_count = 0
    for video_id, player_id, timems in ranked_int.iterator(chunk_size=batch_size):
        if player_id not in participants_by_user_id:
            continue
        participants_by_user_id[player_id].classic_add_i(video_id, timems)
        intermediate_video_count += 1
    logger.info(f'周赛#{tournament.id} 中级录像读取完成，匹配录像 {intermediate_video_count} 条')

    WeeklyParticipant.objects.bulk_update(participants, ['classic_et', 'classic_it', 'classic_score'], batch_size=batch_size)

    logger.info(f'周赛#{tournament.id} 成绩刷新完成，更新参赛者 {len(participants)} 个')
    return len(participants)


def update_weekly_best(tournament_user: TournamentUser, tournament: WeeklyTournament, participant: WeeklyParticipant):
    if participant.user_id is None or tournament.state != Tournament_TextChoices.State.AWARDED:
        return False

    new_best = weekly_encode_best(participant.classic_score, tournament.year, tournament.week)
    best_field = f'{WEEKLY_SCORE_CATEGORIES[tournament.tournament_format]}_best'
    if getattr(tournament_user, best_field) <= new_best:
        return False

    setattr(tournament_user, best_field, new_best)
    return True


def calculate_weekly_best(user_id: int, tournament_format):
    tournament_format = Tournament_TextChoices.WeeklyFormat(tournament_format)
    best_participant = (
        WeeklyParticipant.objects
        .filter(user_id=user_id, tournament__state=Tournament_TextChoices.State.AWARDED, tournament__weeklytournament__tournament_format=tournament_format)
        .select_related('tournament__weeklytournament')
        .order_by('classic_score', 'tournament__weeklytournament__year', 'tournament__weeklytournament__week')
        .first()
    )
    if best_participant is None:
        return MAX_TOURNAMENT_BEST
    tournament = best_participant.tournament.weeklytournament
    return weekly_encode_best(best_participant.classic_score, tournament.year, tournament.week)


def refresh_weekly_best_scores(tournament: WeeklyTournament, *, batch_size=1000, rebuild=False):
    """默认只更新更好的纪录；rebuild=True 时重新查询历史最佳，允许纪录回退。"""
    best_field = f'{WEEKLY_SCORE_CATEGORIES[tournament.tournament_format]}_best'
    logger.info(f'周赛#{tournament.id} 个人纪录刷新 开始 类型{tournament.subclass}')
    logger.info(f'周赛#{tournament.id} 个人纪录刷新 获取选手列表')
    participants = list(
        WeeklyParticipant.objects
        .filter(tournament_id=tournament.id, user_id__isnull=False)
        .select_related('user__tournamentuser'),
    )
    logger.info(f'周赛#{tournament.id} 个人纪录刷新 人数 {len(participants)}')
    if not participants:
        logger.info(f'周赛#{tournament.id} 个人纪录刷新 结束')
        return 0

    tournament_users = []
    updated_count = 0
    for participant in participants:
        tournament_user = participant.user.tournamentuser
        if rebuild:
            best = calculate_weekly_best(participant.user_id, tournament.tournament_format)
            updated_count += getattr(tournament_user, best_field) != best
            setattr(tournament_user, best_field, best)
        else:
            updated_count += update_weekly_best(tournament_user, tournament, participant)
        tournament_users.append(tournament_user)

    TournamentUser.objects.bulk_update(tournament_users, [best_field], batch_size=batch_size)
    tournament_cache.update_tournament_users(tournament_users, fields=[best_field])
    logger.info(f'周赛#{tournament.id} 个人纪录刷新 完成 人数{updated_count}')
    return updated_count
