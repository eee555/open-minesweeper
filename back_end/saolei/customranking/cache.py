from datetime import datetime
import json
from typing import Iterable

from django_redis import get_redis_connection
from redis.client import Pipeline, Redis

from videomanager.models import MAX_TIMEMS, VideoModel

cache = get_redis_connection('saolei_website')


class PLuckRankingCache:
    level: str
    rank_key: str
    detail_key: str

    def __init__(self, level: str):
        self.level = level
        self.rank_key = get_custom_pluck_rank_key(level)
        self.detail_key = get_custom_pluck_detail_key(level)

    @property
    def client(self) -> Redis:
        return cache

    @staticmethod
    def pipeline():
        return cache.pipeline()

    def __len__(self):
        return cache.zcard(self.rank_key)

    def range(self, start: int, end: int, withscores: bool = False):
        return cache.zrange(self.rank_key, start, end, withscores=withscores)

    def details(self, members: Iterable[str]):
        return cache.hmget(self.detail_key, members)

    def get_rank_range(self, start: int, end: int):
        """读取缓存内的左闭右开排行区间。"""
        members_with_scores = self.range(start, end - 1, withscores=True)
        if not members_with_scores:
            return []

        members = [
            member
            for member, _ in members_with_scores
        ]
        details = self.details(members)
        players = []
        for member, (_, score), detail in zip(members, members_with_scores, details):
            if detail is None:
                continue
            players.append(cache_to_dict(member, score, json.loads(detail)))
        return players

    def remove_record(self, player_id: int, *, pipe: Pipeline):
        member = str(player_id)
        pipe.zrem(self.rank_key, member)
        pipe.hdel(self.detail_key, member)

    def add_record_batch(self, videos: Iterable[VideoModel], *, pipe: Pipeline | None = None):
        if pipe is None:
            with self.pipeline() as pipe:
                self.add_record_batch(videos, pipe=pipe)
                pipe.execute()
            return
        rank_mapping = {}
        detail_mapping = {}
        for video in videos:
            member = str(video.player_id)
            rank_mapping[member] = video_to_score(video)
            detail_mapping[member] = json.dumps(video_to_detail(video))

        if rank_mapping:
            pipe.zadd(self.rank_key, rank_mapping)
            pipe.hset(self.detail_key, mapping=detail_mapping)

    def flush(self):
        self.client.delete(
            self.rank_key,
            self.detail_key,
            get_legacy_custom_pluck_player_key(self.level),
        )


##############
# Cache Keys #
##############

def get_custom_pluck_rank_key(level: str) -> str:
    """
    有序集zset，排序键`score`通常是`pluck`；当`pluck == 0`时使用`timems - MAX_TIMEMS`降低 0 碰撞风险。`member`是`player_id`。
    """
    return f'customranking:pluck:{level}:rank'


def get_custom_pluck_detail_key(level: str) -> str:
    """
    查找表hset，主键是RANK的`member`，存储 API 展示需要的录像信息。
    """
    return f'customranking:pluck:{level}:detail'


def get_legacy_custom_pluck_player_key(level: str) -> str:
    """旧缓存结构中的玩家索引，flush时顺便清理。"""
    return f'customranking:pluck:{level}:player'


###################
# Data Conversion #
###################

def video_to_score(video: VideoModel):
    if video.pluck > 0:
        return video.pluck
    return video.timems - MAX_TIMEMS


def video_to_detail(video: VideoModel):
    return {
        'video_id': video.pk,
        'timems': video.timems,
        'upload_time': video.upload_time.isoformat(),
    }


def cache_to_dict(member: str, score: float, detail: dict):
    """将 Redis 排行缓存中的数据转换为字典。"""
    return {
        **detail,
        'player_id': int(member),
        'pluck': max(0, score),
        'upload_time': datetime.fromisoformat(detail['upload_time']),
    }


def get_player_pluck_records(player_id: int, levels: Iterable[str]):
    """用 Redis pipeline 批量读取玩家在多个配置下的当前纪录。"""
    ranking_caches = [
        PLuckRankingCache(level)
        for level in levels
    ]
    if not ranking_caches:
        return {}

    member = str(player_id)
    pipe = cache.pipeline()
    for ranking_cache in ranking_caches:
        pipe.zscore(ranking_cache.rank_key, member)
        pipe.hget(ranking_cache.detail_key, member)

    results = pipe.execute()
    records_by_level = {}
    for index, ranking_cache in enumerate(ranking_caches):
        score = results[index * 2]
        detail = results[index * 2 + 1]
        if score is None or detail is None:
            continue
        records_by_level[ranking_cache.level] = cache_to_dict(
            member,
            score,
            json.loads(detail),
        )
    return records_by_level


def read_records(categories: Iterable[tuple[int, str]]):
    """供更新使用；只有两侧均缺失才表示无纪录，半缺失需管理员修复。"""
    categories = list(categories)
    if not categories:
        return {}
    with PLuckRankingCache.pipeline() as pipe:
        for player_id, level in categories:
            ranking = PLuckRankingCache(level)
            pipe.zscore(ranking.rank_key, player_id)
            pipe.hget(ranking.detail_key, player_id)
        results = pipe.execute()
    records = {}
    for index, category in enumerate(categories):
        score, detail = results[index * 2:index * 2 + 2]
        if (score is None) != (detail is None):
            raise ValueError(f'Incomplete Pluck record: {category}')
        records[category] = None if score is None else cache_to_dict(str(category[0]), score, json.loads(detail))
    return records
