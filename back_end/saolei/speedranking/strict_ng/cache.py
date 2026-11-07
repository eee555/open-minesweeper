import json

from .utils import public_record
from ..cache import cache


class SpeedRankingCache:
    def __init__(self, ranking_name: str, *, stats: tuple[str, ...] = (), namespace: str = 'speedranking'):
        self.prefix = f'{namespace}:{ranking_name}'
        self.detail_key = f'{self.prefix}:records'
        self.stats = stats

    @staticmethod
    def pipeline():
        return cache.pipeline()

    def rank_key(self, stat: str):
        return f'{self.prefix}:{stat}'

    @property
    def keys(self):
        return [self.detail_key, *[self.rank_key(stat) for stat in self.stats]]

    def get_record(self, player_id: int):
        raw = cache.hget(self.detail_key, player_id)
        return json.loads(raw) if raw else None

    def read_records(self, pipe, player_ids):
        """将批量读取加入调用方的 pipeline，不自行执行。"""
        pipe.hmget(self.detail_key, player_ids)

    def write_record(self, pipe, player_id: int, record: dict | None):
        """将个人纪录写入或删除加入调用方的 pipeline。"""
        if record is None:
            pipe.hdel(self.detail_key, player_id)
        else:
            pipe.hset(self.detail_key, player_id, json.dumps(record, allow_nan=False))

    def write_score(self, pipe, player_id: int, stat: str, score: int | float | None):
        """将已由业务层编码的 score 写入或移除，不进行规则判断。"""
        if score is None:
            pipe.zrem(self.rank_key(stat), player_id)
        else:
            pipe.zadd(self.rank_key(stat), {str(player_id): score})

    def read_rank(self, pipe, player_id: int, stat: str):
        pipe.zrank(self.rank_key(stat), player_id)

    def get_range(self, stat: str, start: int, end: int):
        """只读 Redis，允许并发更新造成短暂不一致，跳过已缺失的纪录。"""
        count = cache.zcard(self.rank_key(stat))
        members = cache.zrange(self.rank_key(stat), start, end - 1) if end > start else []
        player_ids = [int(member) for member in members]
        records = cache.hmget(self.detail_key, player_ids) if player_ids else []
        return {'count': count, 'players': [public_record(player_id, json.loads(raw)) for player_id, raw in zip(player_ids, records) if raw]}

    def flush(self):
        cache.delete(*self.keys)

    def publish_to(self, target):
        """将临时榜原子替换为正式榜，空的小榜也会清除旧数据。"""
        with self.pipeline() as pipe:
            for source, destination in zip(self.keys, target.keys):
                if cache.exists(source):
                    pipe.rename(source, destination)
                else:
                    pipe.delete(destination)
            pipe.execute()
