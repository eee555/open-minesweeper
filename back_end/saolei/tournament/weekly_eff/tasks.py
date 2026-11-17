import logging

from django.tasks import task

from config.text_choices import Tournament_TextChoices
from tournament.models import WeeklyEffTournament
from tournament.services import delete_participants_without_videos, ensure_tournament_users, refresh_tournament_ranks, reveal_videos_for_tournament
from tournament.tasks import task_award_tournament
from .services import refresh_weekly_eff_best_scores, refresh_weekly_eff_scores

logger = logging.getLogger('tournament')


@task
def task_weekly_eff_finish(tournament_id: int):
    tournament = WeeklyEffTournament.objects.get(id=tournament_id)
    logger.info(f'效率打卡赛#{tournament_id} 结算开始')
    try:
        ensure_tournament_users(tournament)
        deleted = delete_participants_without_videos(tournament)
        scores = refresh_weekly_eff_scores(tournament)
        ranks = refresh_tournament_ranks(tournament)
        tournament.state = Tournament_TextChoices.State.AWARDED
        tournament.save(update_fields=['state'])
        revealed = reveal_videos_for_tournament(tournament)
        task_award_tournament.enqueue(tournament_id)
        task_weekly_eff_refresh_best.enqueue(tournament_id)
    except Exception:
        logger.exception(f'效率打卡赛#{tournament_id} 结算失败')
        raise
    result = {'deleted_participants': deleted, 'score_count': scores, 'rank_count': ranks, 'video_count': revealed}
    logger.info(f'效率打卡赛#{tournament_id} 结算完成，{result}')
    return result


@task
def task_weekly_eff_refresh_best(tournament_id: int):
    tournament = WeeklyEffTournament.objects.get(id=tournament_id)
    ensure_tournament_users(tournament)
    return refresh_weekly_eff_best_scores(tournament)
