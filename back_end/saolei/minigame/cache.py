import json

from django_redis import get_redis_connection

from .models import MiniGameBestScore
from .utils import GAME_RANKINGS, RANKINGS


def score_detail(record):
    return {'score': record.score, 'achieved_at': record.achieved_at.isoformat()}


class MiniGameRankingCache:
    prefix = 'minigame'

    def __init__(self):
        self.client = get_redis_connection('saolei_website')

    def rank_key(self, ranking_key):
        return f'{self.prefix}:rank:v1:{ranking_key}'

    def detail_key(self, ranking_key):
        return f'{self.prefix}:detail:v1:{ranking_key}'

    def ready_key(self, ranking_key):
        return f'{self.prefix}:ready:v1:{ranking_key}'

    def ranking_keys(self, ranking_key):
        return (self.rank_key(ranking_key), self.detail_key(ranking_key), self.ready_key(ranking_key))

    @property
    def keys(self):
        return [key for ranking_key in RANKINGS for key in self.ranking_keys(ranking_key)]

    def update(self, record):
        with self.client.pipeline() as pipe:
            pipe.zadd(self.rank_key(record.ranking_key), {str(record.player_id): record.score})
            pipe.hset(self.detail_key(record.ranking_key), str(record.player_id), json.dumps(score_detail(record)))
            pipe.execute()

    def remove(self, ranking_key, player_id):
        with self.client.pipeline() as pipe:
            pipe.zrem(self.rank_key(ranking_key), str(player_id))
            pipe.hdel(self.detail_key(ranking_key), str(player_id))
            pipe.execute()

    def rebuild(self, ranking_key):
        records = list(MiniGameBestScore.objects.filter(ranking_key=ranking_key).defer('replay_archive'))
        with self.client.pipeline() as pipe:
            pipe.delete(*self.ranking_keys(ranking_key))
            if records:
                pipe.zadd(self.rank_key(ranking_key), {str(record.player_id): record.score for record in records})
                pipe.hset(self.detail_key(ranking_key), mapping={str(record.player_id): json.dumps(score_detail(record)) for record in records})
            # Empty rankings are initialized too. A single upload never sets this key.
            pipe.set(self.ready_key(ranking_key), '1')
            pipe.execute()
        return len(records)

    def get_range(self, game, sort, start, end):
        rankings = GAME_RANKINGS[game]
        with self.client.pipeline(transaction=False) as pipe:
            for ranking in rankings:
                pipe.get(self.ready_key(ranking.key))
            pipe.zcard(self.rank_key(sort))
            if end > start:
                pipe.zrange(self.rank_key(sort), start, end - 1, desc=RANKINGS[sort].order == 'desc')
            result = pipe.execute()
        missing = [ranking.key for ranking, ready in zip(rankings, result[:len(rankings)]) if ready is None]
        if missing:
            for key in missing:
                self.rebuild(key)
            return self.get_range(game, sort, start, end)
        count = result[len(rankings)]
        members = result[-1] if end > start else []
        if not members:
            return {'count': count, 'players': []}
        with self.client.pipeline(transaction=False) as pipe:
            for ranking in rankings:
                pipe.hmget(self.detail_key(ranking.key), members)
            details = pipe.execute()
        players = []
        for index, member in enumerate(members):
            records = {ranking.key: json.loads(values[index]) if values[index] else None for ranking, values in zip(rankings, details)}
            players.append({'player_id': int(member), 'rank': start + index + 1, 'records': records})
        return {'count': count, 'players': players}

    def get_player(self, game, player_id):
        rankings = GAME_RANKINGS[game]
        with self.client.pipeline(transaction=False) as pipe:
            for ranking in rankings:
                pipe.get(self.ready_key(ranking.key))
            ready = pipe.execute()
        for ranking, initialized in zip(rankings, ready):
            if initialized is None:
                self.rebuild(ranking.key)
        with self.client.pipeline(transaction=False) as pipe:
            for ranking in rankings:
                pipe.hget(self.detail_key(ranking.key), str(player_id))
                if ranking.order == 'asc':
                    pipe.zrank(self.rank_key(ranking.key), str(player_id))
                else:
                    pipe.zrevrank(self.rank_key(ranking.key), str(player_id))
            values = pipe.execute()
        records = {}
        for index, ranking in enumerate(rankings):
            detail, rank = values[2 * index:2 * index + 2]
            records[ranking.key] = {**json.loads(detail), 'rank': rank + 1 if rank is not None else None} if detail else None
        return {'player_id': player_id, 'records': records}
