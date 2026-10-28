import json

from .utils import empty_record, RANK_STATS
from ..cache import cache, pipeline


class ThrpRankingCache:
    def __init__(self, namespace: str = 'effranking'):
        self.prefix = f'{namespace}:thrp'
        self.detail_key = f'{self.prefix}:records'

    @staticmethod
    def pipeline():
        return pipeline()

    def rank_key(self, stat: str):
        return f'{self.prefix}:{stat}'

    @property
    def keys(self):
        return [self.detail_key, *[self.rank_key(stat) for stat in RANK_STATS]]

    def read_records(self, player_ids):
        """批量读取原始纪录，未命中使用完整空项，不回源数据库。"""
        player_ids = list(player_ids)
        rows = cache.hmget(self.detail_key, player_ids) if player_ids else []
        return {player_id: empty_record() | (json.loads(raw) if raw else {}) for player_id, raw in zip(player_ids, rows)}

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

    def get_range(self, stat: str, start: int, end: int):
        """按索引获取玩家，原样返回其完整 hash 纪录。"""
        with self.pipeline() as pipe:
            pipe.zcard(self.rank_key(stat))
            if end > start:
                pipe.zrange(self.rank_key(stat), start, end - 1)
            else:
                pipe.zrange(self.rank_key(stat), 1, 0)
            count, members = pipe.execute()
        records = self.read_records(int(member) for member in members)
        return {'count': count, 'players': [{'player_id': player_id, **record} for player_id, record in records.items() if any(part is not None for part in record.values())]}

    def get_player(self, player_id: int):
        with self.pipeline() as pipe:
            pipe.hget(self.detail_key, player_id)
            for stat in RANK_STATS:
                pipe.zrank(self.rank_key(stat), player_id)
            raw, *ranks = pipe.execute()
        return {'player_id': player_id, **(empty_record() | (json.loads(raw) if raw else {})), 'ranks': {stat: rank + 1 if rank is not None else None for stat, rank in zip(RANK_STATS, ranks)}}

    def flush(self):
        cache.delete(*self.keys)

    def publish_to(self, target):
        """临时榜构建成功后原子替换，空榜清除旧正式数据。"""
        with self.pipeline() as pipe:
            for source, destination in zip(self.keys, target.keys):
                if cache.exists(source):
                    pipe.rename(source, destination)
                else:
                    pipe.delete(destination)
            pipe.execute()
