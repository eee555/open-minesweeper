import logging

from django.db import transaction
from django.utils import timezone
from redis.exceptions import RedisError

from .archive import pack_replay
from .cache import MiniGameRankingCache, score_detail
from .models import MiniGameBestScore
from .utils import GAME_RANKINGS, MiniGameError, RANKINGS

logger = logging.getLogger(__name__)


def update_cached_score(record):
    try:
        MiniGameRankingCache().update(record)
    except RedisError:
        logger.exception('Failed to update minigame score cache')


def remove_cached_score(ranking_key, player_id):
    try:
        MiniGameRankingCache().remove(ranking_key, player_id)
    except RedisError:
        logger.exception('Failed to remove minigame score cache')


def submit_score(player, ranking_key, score, replay):
    config = RANKINGS[ranking_key]
    if not config.accept_submissions:
        raise MiniGameError(409, 'ranking_closed', 'This ranking no longer accepts scores')
    if type(score) is not int or not config.min_score <= score <= config.max_score:
        raise MiniGameError(422, 'invalid_score', 'Score must be an integer within the ranking limits')
    record, created = MiniGameBestScore.objects.defer('replay_archive').get_or_create(player=player, ranking_key=ranking_key, defaults={'score': score, 'replay_archive': lambda: pack_replay(replay)})
    improved = created or config.is_better(score, record.score)
    if improved:
        if not created:
            record.score = score
            record.achieved_at = timezone.now()
            record.replay_archive = pack_replay(replay)
            record.save(update_fields=['score', 'achieved_at', 'replay_archive'])
        transaction.on_commit(lambda: update_cached_score(record))
    return {'improved': improved, 'record': record}


def get_replay(ranking_key, player_id):
    record = MiniGameBestScore.objects.filter(ranking_key=ranking_key, player_id=player_id).values_list('score', 'replay_archive').first()
    if record is None or not record[1]:
        raise MiniGameError(404, 'replay_not_found', 'Replay not found')
    return record[0], bytes(record[1])


def delete_score(ranking_key, player_id):
    deleted, _ = MiniGameBestScore.objects.filter(ranking_key=ranking_key, player_id=player_id).defer('replay_archive').delete()
    if not deleted:
        raise MiniGameError(404, 'record_not_found', 'Score record not found')


def get_ranking(game, sort, start, end, rankings=None):
    rankings = GAME_RANKINGS[game] if rankings is None else rankings
    try:
        return MiniGameRankingCache().get_range(rankings, sort, start, end)
    except RedisError:
        logger.exception('Falling back to database for minigame ranking')
    ranking = MiniGameBestScore.objects.filter(ranking_key=sort)
    order = 'score' if RANKINGS[sort].order == 'asc' else '-score'
    player_ids = list(ranking.order_by(order, 'id').values_list('player_id', flat=True)[start:end])
    records = {player_id: dict.fromkeys(ranking.key for ranking in rankings) for player_id in player_ids}
    if player_ids:
        for record in MiniGameBestScore.objects.filter(player_id__in=player_ids, ranking_key__in=records[player_ids[0]]).defer('replay_archive'):
            records[record.player_id][record.ranking_key] = score_detail(record)
    players = [
        {'player_id': player_id, 'rank': start + index + 1, 'records': records[player_id]}
        for index, player_id in enumerate(player_ids)
    ]
    return {'count': ranking.count(), 'players': players}


def get_player_scores(game, player_id, rankings=None):
    rankings = GAME_RANKINGS[game] if rankings is None else rankings
    try:
        return MiniGameRankingCache().get_player(rankings, player_id)
    except RedisError:
        logger.exception('Falling back to database for minigame player scores')
    records = dict.fromkeys(ranking.key for ranking in rankings)
    for record in MiniGameBestScore.objects.filter(player_id=player_id, ranking_key__in=records).defer('replay_archive'):
        records[record.ranking_key] = {**score_detail(record), 'rank': None}
    return {'player_id': player_id, 'records': records}


def get_ranking_summary(ranking_key, player_id=None):
    ranking = RANKINGS[ranking_key]
    rankings = (ranking,)
    result = get_ranking(ranking.game, ranking_key, 0, 20, rankings)
    result['player'] = get_player_scores(ranking.game, player_id, rankings) if player_id is not None else None
    return result
