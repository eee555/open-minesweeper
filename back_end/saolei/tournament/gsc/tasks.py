import logging

from django.tasks import task, TaskResultStatus
from django.utils import timezone

from config.text_choices import Tournament_TextChoices
from tournament.models import GSCTournament
from tournament.services import delete_participants_without_videos, ensure_tournament_users, reveal_videos_for_tournament
from tournament.tasks import task_award_tournament
from tournament.utils import TOURNAMENT_FINISH_DELAY
from .services import refresh_gsc_best_scores, refresh_gsc_scores_and_ranks

logger = logging.getLogger('tournament')


def helper_gsc_finish_tournament(tournament: GSCTournament):
    existing_task = tournament.task
    if existing_task:
        if existing_task.status == TaskResultStatus.SUCCESSFUL:
            logger.info(
                f'GSC#{tournament.order} 删除已完成的旧结算任务，'
                f'任务#{tournament.task_id}',
            )
            existing_task.delete()
        elif existing_task.status in [TaskResultStatus.READY, TaskResultStatus.RUNNING]:
            logger.info(
                f'GSC#{tournament.order} 复用进行中的结算任务，'
                f'任务#{tournament.task_id}，状态 {existing_task.status}',
            )
            return existing_task

    run_after = max(timezone.now(), tournament.end_time + TOURNAMENT_FINISH_DELAY)
    tournament.task = task_gsc_finish.using(run_after=run_after).enqueue(tournament.order).db_result
    tournament.save(update_fields=['task'])
    logger.info(
        f'GSC#{tournament.order} 创建结算任务完成，任务#{tournament.task_id}，'
        f'状态 {tournament.task.status}',
    )
    return tournament.task


def _task_gsc_finish_impl(gsc_order: int):
    logger.info(f'GSC#{gsc_order} 结算任务开始')
    tournament = GSCTournament.objects.get(order=gsc_order)
    try:
        logger.info(
            f'GSC#{tournament.order} 结算开始，比赛#{tournament.id}，'
            f'当前状态 {tournament.state}',
        )
        ensure_tournament_users(tournament)
        deleted_participants = delete_participants_without_videos(tournament)
        logger.info(f'GSC#{tournament.order} 删除无录像参赛者完成，数量 {deleted_participants}')
        tournament_user_count = tournament.participants.filter(user_id__isnull=False).count()
        logger.info(f'GSC#{tournament.order} TournamentUser 可用数量 {tournament_user_count}')
        result = refresh_gsc_scores_and_ranks(tournament)
        result['tournament_users'] = tournament_user_count
        result['deleted_participants'] = deleted_participants
        if tournament.state != Tournament_TextChoices.State.AWARDED:
            tournament.state = Tournament_TextChoices.State.AWARDED
            tournament.save(update_fields=['state'])
            logger.info(f'GSC#{tournament.order} 状态已切换为 AWARDED')
        else:
            logger.info(f'GSC#{tournament.order} 状态已是 AWARDED，跳过状态切换')
        result['revealed_videos'] = reveal_videos_for_tournament(tournament)
        logger.info(f'GSC#{tournament.order} 录像公开完成，数量 {result["revealed_videos"]}')
        logger.info(f'GSC#{tournament.order} 结算完成，结果 {result}')
    except Exception as e:
        logger.exception(f'GSC#{gsc_order} 结算任务失败')
        raise e
    logger.info(f'GSC#{gsc_order} 结算任务完成，结果 {result}')
    task_award_tournament.enqueue(tournament.id)
    task_gsc_refresh_best.enqueue(gsc_order)
    return result


@task
def task_gsc_finish(gsc_order: int):
    return _task_gsc_finish_impl(gsc_order)


def _task_gsc_refresh_best_impl(order: int):
    tournament = GSCTournament.objects.get(order=order)
    ensure_tournament_users(tournament)
    return refresh_gsc_best_scores(tournament)


@task
def task_gsc_refresh_best(order: int):
    return _task_gsc_refresh_best_impl(order)
