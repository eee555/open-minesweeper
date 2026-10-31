import json

from django_redis import get_redis_connection

cache = get_redis_connection('saolei_website')


def pipeline():
    return cache.pipeline()


class EfficiencyRankingCache:
    ranking_name: str
    stats: tuple[str, ...]
    record_fields: tuple[str, ...]

    def __init__(self, namespace: str = 'effranking'):
        self.prefix = f'{namespace}:{self.ranking_name}'
        self.detail_key = f'{self.prefix}:records'

    @staticmethod
    def pipeline():
        return pipeline()

    def rank_key(self, stat: str):
        return f'{self.prefix}:{stat}'

    @property
    def keys(self):
        return [self.detail_key, *[self.rank_key(stat) for stat in self.stats]]

    def parse_records(self, player_ids, rows):
        return {player_id: dict.fromkeys(self.record_fields) | (json.loads(raw) if raw else {}) for player_id, raw in zip(player_ids, rows)}

    def read_records(self, player_ids):
        player_ids = list(player_ids)
        return self.parse_records(player_ids, cache.hmget(self.detail_key, player_ids) if player_ids else [])

    def write_record(self, pipe, player_id: int, record: dict):
        if any(part is not None for part in record.values()):
            pipe.hset(self.detail_key, player_id, json.dumps(record, allow_nan=False))
        else:
            pipe.hdel(self.detail_key, player_id)

    def write_score(self, pipe, player_id: int, stat: str, score: int | float | None):
        if score is None:
            pipe.zrem(self.rank_key(stat), player_id)
        else:
            pipe.zadd(self.rank_key(stat), {str(player_id): score})

    def write_changes(self, changes, pipe=None):
        if not changes:
            return
        if pipe is None:
            with self.pipeline() as pipe:
                self.write_changes(changes, pipe)
                pipe.execute()
            return
        for player_id, record, scores in changes:
            self.write_record(pipe, player_id, record)
            for stat, score in scores.items():
                self.write_score(pipe, player_id, stat, score)

    def get_range(self, stat: str, start: int, end: int):
        with self.pipeline() as pipe:
            pipe.zcard(self.rank_key(stat))
            pipe.zrange(self.rank_key(stat), start if end > start else 1, end - 1 if end > start else 0)
            count, members = pipe.execute()
        records = self.read_records(int(member) for member in members)
        return {'count': count, 'players': [{'player_id': player_id, **record} for player_id, record in records.items() if any(part is not None for part in record.values())]}

    def get_player(self, player_id: int):
        with self.pipeline() as pipe:
            pipe.hget(self.detail_key, player_id)
            for stat in self.stats:
                pipe.zrank(self.rank_key(stat), player_id)
            raw, *ranks = pipe.execute()
        return {'player_id': player_id, **self.parse_records([player_id], [raw])[player_id], 'ranks': {stat: rank + 1 if rank is not None else None for stat, rank in zip(self.stats, ranks)}}

    def flush(self):
        cache.delete(*self.keys)

    def publish_to(self, target):
        with self.pipeline() as pipe:
            for source, destination in zip(self.keys, target.keys):
                if cache.exists(source):
                    pipe.rename(source, destination)
                else:
                    pipe.delete(destination)
            pipe.execute()
