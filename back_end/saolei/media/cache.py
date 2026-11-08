"""作品页 Redis 排行：四个 zset 与统一热度基准；见 MEDIA_PLAN.md 第 5.2、6 节。"""

from datetime import datetime, timezone as datetime_timezone
from uuid import uuid4

from django.utils import timezone
from django_redis import get_redis_connection

from utils.cache import maybe_bytes_to_str
from .models import Media
from .utils import decay, MediaStatus

cache = get_redis_connection('saolei_website')

MEDIA_RANK_HOT = 'media:rank:hot'
MEDIA_RANK_LIKES = 'media:rank:likes'
MEDIA_RANK_USER_HOT = 'media:rank:user:hot'
MEDIA_RANK_USER_LIKES = 'media:rank:user:likes'
MEDIA_HOT_ANCHOR = 'media:hot:anchor'
MEDIA_REBUILD_PREFIX = 'media:rebuild:'
MEDIA_RANK_KEYS = (MEDIA_RANK_HOT, MEDIA_RANK_LIKES, MEDIA_RANK_USER_HOT, MEDIA_RANK_USER_LIKES)
MEDIA_CACHE_KEYS = (*MEDIA_RANK_KEYS, MEDIA_HOT_ANCHOR)


def media_hot_reference_time(at_time=None):
    """当月 1 日 00:00 UTC；月度刷新的目标基准。"""
    now = at_time or timezone.now()
    return datetime(now.year, now.month, 1, tzinfo=datetime_timezone.utc)


def get_hot_reference():
    """读 anchor；缺失时以 DB 最早基准或当月 1 日 UTC 初始化（SET NX 避免并发覆盖）。"""
    value = cache.get(MEDIA_HOT_ANCHOR)
    if value is not None:
        return datetime.fromisoformat(maybe_bytes_to_str(value))
    earliest = Media.objects.order_by('hot_value_updated_at').values_list('hot_value_updated_at', flat=True).first()
    reference = earliest or media_hot_reference_time()
    cache.set(MEDIA_HOT_ANCHOR, reference.isoformat(), nx=True)
    value = cache.get(MEDIA_HOT_ANCHOR)
    return datetime.fromisoformat(maybe_bytes_to_str(value)) if value is not None else reference


def set_hot_reference(reference):
    cache.set(MEDIA_HOT_ANCHOR, reference.isoformat())


def add_media_scores(media_id, author_id, delta_hot, delta_likes):
    """审核通过补齐或投喂增量：四个 zset 用 ZINCRBY 原子累加，避免读-改-写丢更新。"""
    with cache.pipeline() as pipe:
        pipe.zincrby(MEDIA_RANK_HOT, delta_hot, media_id)
        pipe.zincrby(MEDIA_RANK_LIKES, delta_likes, media_id)
        pipe.zincrby(MEDIA_RANK_USER_HOT, delta_hot, author_id)
        pipe.zincrby(MEDIA_RANK_USER_LIKES, delta_likes, author_id)
        pipe.execute()


def remove_media_scores(media_id, author_id, hot_value, likes):
    """站长硬删除回退：移除作品榜并按等值扣减作者榜，结果 <= 0 时改为 ZREM。"""
    cache.zrem(MEDIA_RANK_HOT, media_id)
    cache.zrem(MEDIA_RANK_LIKES, media_id)
    for key, delta in ((MEDIA_RANK_USER_HOT, hot_value), (MEDIA_RANK_USER_LIKES, likes)):
        score = cache.zincrby(key, -delta, author_id)
        if score is not None and score <= 0:
            cache.zrem(key, author_id)


def get_ranking(key, start=0, count=50):
    """zset 分页：返回 (member id 列表, 总数)；同分按 Redis member 字典序，不二次排序。"""
    total = cache.zcard(key)
    raw = cache.zrevrange(key, start, start + count - 1)
    return [int(maybe_bytes_to_str(member)) for member in raw], total


def refresh_hot_reference(at_time=None):
    """月度刷新 Redis：WATCH anchor，按同一系数整体缩放两个 hot zset，写新锚点；幂等。"""
    get_hot_reference()
    score_time = media_hot_reference_time(at_time)

    def refresh(pipe):
        raw = pipe.get(MEDIA_HOT_ANCHOR)
        previous = datetime.fromisoformat(maybe_bytes_to_str(raw))
        pipe.multi()
        if previous == score_time:
            return False
        factor = decay(previous, score_time)
        for key in (MEDIA_RANK_HOT, MEDIA_RANK_USER_HOT):
            pipe.zunionstore(key, {key: factor})
        pipe.set(MEDIA_HOT_ANCHOR, score_time.isoformat())
        return True

    return cache.transaction(refresh, MEDIA_HOT_ANCHOR, value_from_callable=True)


def rebuild_rankings(batch_size=1000):
    """从 DB 只取 verified 全量重建四个 zset 与 anchor；临时 key + rename 原子发布，失败保留旧榜。"""
    if batch_size <= 0:
        raise ValueError('batch_size must be positive')
    prefix = MEDIA_REBUILD_PREFIX + uuid4().hex
    temporary = {key: f'{prefix}:{key}' for key in MEDIA_RANK_KEYS}
    try:
        count = 0
        with cache.pipeline() as pipe:
            queryset = Media.objects.filter(status=MediaStatus.VERIFIED).only('id', 'user_id', 'likes', 'hot_value')
            for media in queryset.iterator(chunk_size=batch_size):
                pipe.zadd(temporary[MEDIA_RANK_HOT], {media.pk: media.hot_value})
                pipe.zadd(temporary[MEDIA_RANK_LIKES], {media.pk: media.likes})
                pipe.zincrby(temporary[MEDIA_RANK_USER_HOT], media.hot_value, media.user_id)
                pipe.zincrby(temporary[MEDIA_RANK_USER_LIKES], media.likes, media.user_id)
                count += 1
                if count % batch_size == 0:
                    pipe.execute()
            if count % batch_size:
                pipe.execute()
        earliest = Media.objects.order_by('hot_value_updated_at').values_list('hot_value_updated_at', flat=True).first()
        reference = earliest or media_hot_reference_time()
        with cache.pipeline() as pipe:
            for key, temp_key in temporary.items():
                if cache.exists(temp_key):
                    pipe.rename(temp_key, key)
                else:
                    pipe.delete(key)
            pipe.set(MEDIA_HOT_ANCHOR, reference.isoformat())
            pipe.execute()
        return count
    finally:
        cache.delete(*temporary.values())


def clear_rankings():
    cache.delete(*MEDIA_CACHE_KEYS)
