import logging

from django.tasks import task

from config.text_choices import Tournament_TextChoices
from tournament.models import WeeklyTournament
from tournament.services import delete_participants_without_videos, ensure_tournament_users, refresh_tournament_ranks, reveal_videos_for_tournament
from tournament.tasks import task_award_tournament
from .services import refresh_weekly_best_scores, refresh_weekly_scores

logger = logging.getLogger('tournament')


def _task_weekly_finish_impl(tournament_id: int):
    logger.info(f'周赛#{tournament_id} 结算任务开始')
    tournament = WeeklyTournament.objects.get(id=tournament_id)
    try:
        logger.info(
            f'周赛#{tournament.id} 结算开始，{tournament.year}W{tournament.week}，'
            f'当前状态 {tournament.state}',
        )
        ensure_tournament_users(tournament)
        deleted_participants = delete_participants_without_videos(tournament)
        logger.info(f'周赛#{tournament.id} 删除无录像参赛者完成，数量 {deleted_participants}')
        tournament_user_count = tournament.participants.filter(user_id__isnull=False).count()
        logger.info(f'周赛#{tournament.id} TournamentUser 可用数量 {tournament_user_count}')
        score_count = refresh_weekly_scores(tournament)
        logger.info(f'周赛#{tournament.id} 成绩刷新完成，数量 {score_count}')
        rank_count = refresh_tournament_ranks(tournament)
        logger.info(f'周赛#{tournament.id} 排名刷新完成，数量 {rank_count}')
        if tournament.state != Tournament_TextChoices.State.AWARDED:
            tournament.state = Tournament_TextChoices.State.AWARDED
            tournament.save(update_fields=['state'])
            logger.info(f'周赛#{tournament.id} 状态已切换为 AWARDED')
        else:
            logger.info(f'周赛#{tournament.id} 状态已是 AWARDED，跳过状态切换')
        video_count = reveal_videos_for_tournament(tournament)
        logger.info(f'周赛#{tournament.id} 录像公开完成，数量 {video_count}')
        result = {
            'tournament_users': tournament_user_count,
            'deleted_participants': deleted_participants,
            'score_count': score_count,
            'rank_count': rank_count,
            'video_count': video_count,
        }
        logger.info(f'周赛#{tournament.id} 结算完成，结果 {result}')
    except Exception:
        logger.exception(f'周赛#{tournament_id} 结算任务失败')
        raise
    logger.info(f'周赛#{tournament_id} 结算任务完成，结果 {result}')
    task_award_tournament.enqueue(tournament.id)
    task_weekly_refresh_best.enqueue(tournament_id)
    return result


@task
def task_weekly_finish(tournament_id: int):
    return _task_weekly_finish_impl(tournament_id)


def _task_weekly_refresh_best_impl(tournament_id: int):
    tournament = WeeklyTournament.objects.get(id=tournament_id)
    ensure_tournament_users(tournament)
    return refresh_weekly_best_scores(tournament)


@task
def task_weekly_refresh_best(tournament_id: int):
    return _task_weekly_refresh_best_impl(tournament_id)
