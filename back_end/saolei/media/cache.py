"""作品页 Redis 排行：四个 zset 与双基准（DB T_db / Redis T_r）；见 MEDIA_PLAN.md 附录 A。"""

from datetime import datetime, timezone as datetime_timezone
import logging
from uuid import uuid4

from django.conf import settings
from django.utils import timezone
from django_redis import get_redis_connection
from redis import Redis

from utils.cache import maybe_bytes_to_str
from .models import Media
from .utils import decay, MediaStatus

logger = logging.getLogger('media')

# 现网 CACHES 的 SOCKET_TIMEOUT 是 5s，而普通 API 只有 2s 网关预算；请求路径的 Redis
# 读写统一走这个短超时客户端，连的是同一个 DB，超时异常由调用方吞掉并只记日志。
MEDIA_SOCKET_TIMEOUT = 1
_location = settings.CACHES['saolei_website']['LOCATION']
cache = (
    Redis.from_url(
        _location, socket_timeout=MEDIA_SOCKET_TIMEOUT, socket_connect_timeout=MEDIA_SOCKET_TIMEOUT,
    )
    if isinstance(_location, str)
    else get_redis_connection('saolei_website')
)

MEDIA_RANK_HOT = 'media:rank:hot'
MEDIA_RANK_LIKES = 'media:rank:likes'
MEDIA_RANK_USER_HOT = 'media:rank:user:hot'
MEDIA_RANK_USER_LIKES = 'media:rank:user:likes'
MEDIA_HOT_ANCHOR = 'media:hot:anchor'
MEDIA_REBUILD_PREFIX = 'media:rebuild:'
MEDIA_RANK_KEYS = (MEDIA_RANK_HOT, MEDIA_RANK_LIKES, MEDIA_RANK_USER_HOT, MEDIA_RANK_USER_LIKES)
MEDIA_CACHE_KEYS = (*MEDIA_RANK_KEYS, MEDIA_HOT_ANCHOR)


def default_hot_reference(at_time=None):
    """空表时 T_db 的兜底初值：当月 1 日 00:00 UTC。"""
    now = at_time or timezone.now()
    return datetime(now.year, now.month, 1, tzinfo=datetime_timezone.utc)


def read_db_hot_reference():
    """T_db：所有作品行统一的 hot_value_updated_at；空表时用兜底初值。

    稳态下全表该字段一致，不再按行独立基准换算；低频管理命令推进 T 时全表一起更新。
    """
    return Media.objects.order_by('pk').values_list('hot_value_updated_at', flat=True).first() or default_hot_reference()


def read_hot_reference():
    """只读 T_r；缺失返回 None。"""
    value = cache.get(MEDIA_HOT_ANCHOR)
    return datetime.fromisoformat(maybe_bytes_to_str(value)) if value is not None else None


def get_hot_reference():
    """读 T_r；缺失时以 T_db 初始化（SET NX 避免并发覆盖）。"""
    existing = read_hot_reference()
    if existing is not None:
        return existing
    reference = read_db_hot_reference()
    cache.set(MEDIA_HOT_ANCHOR, reference.isoformat(), nx=True)
    logger.info('Initialized media hot reference T_r from T_db: %s', reference.isoformat())
    return read_hot_reference() or reference


def set_hot_reference(reference):
    cache.set(MEDIA_HOT_ANCHOR, reference.isoformat())


def reference_factor(target=None):
    """把以 T_db 为基准的 DB 热度折算成以 T_r（或 target）为基准的 zset 分数。"""
    return decay(read_db_hot_reference(), target or get_hot_reference())


def set_media_scores(media_id, author_id, media_hot, media_likes, user_hot, user_likes, has_works):
    """一个显式 MULTI/EXEC 写四个 zset 的绝对分数；调用方负责吞掉 Redis 异常。

    一律写绝对值，不用 ZINCRBY：EXEC 已执行但响应丢失、或只生效一部分时都不会重复累加，
    下一次写入或管理命令全量重建即可覆盖收敛。MULTI/EXEC 没有回滚，所以绝不把抛异常
    当作「未写入」，也不重试、不补偿。
    """
    with cache.pipeline(transaction=True) as pipe:
        if media_hot is None:
            pipe.zrem(MEDIA_RANK_HOT, media_id)
            pipe.zrem(MEDIA_RANK_LIKES, media_id)
        else:
            pipe.zadd(MEDIA_RANK_HOT, {media_id: media_hot})
            pipe.zadd(MEDIA_RANK_LIKES, {media_id: media_likes})
        for key, score in ((MEDIA_RANK_USER_HOT, user_hot), (MEDIA_RANK_USER_LIKES, user_likes)):
            if has_works:
                pipe.zadd(key, {author_id: score})
            else:
                pipe.zrem(key, author_id)
        pipe.execute()


def get_ranking(key, start=0, count=50):
    """zset 分页：返回 (member id 列表, 总数)；同分按 Redis member 字典序，不二次排序。"""
    total = cache.zcard(key)
    raw = cache.zrevrange(key, start, start + count - 1)
    return [int(maybe_bytes_to_str(member)) for member in raw], total


def get_user_ranking(sort_key, start=0, count=50):
    """作者聚合榜分页：返回 [(user_id, hot, likes)] 与总数，主榜按 sort_key 倒序。"""
    if sort_key not in ('hot', 'likes'):
        raise ValueError('Unknown media ranking sort')
    primary = MEDIA_RANK_USER_HOT if sort_key == 'hot' else MEDIA_RANK_USER_LIKES
    secondary = MEDIA_RANK_USER_LIKES if sort_key == 'hot' else MEDIA_RANK_USER_HOT
    total = cache.zcard(primary)
    raw = cache.zrevrange(primary, start, start + count - 1, withscores=True)
    rows = []
    for member, score in raw:
        user_id = int(maybe_bytes_to_str(member))
        other = cache.zscore(secondary, user_id)
        hot, likes = (float(score), float(other or 0)) if sort_key == 'hot' else (float(other or 0), float(score))
        rows.append((user_id, hot, likes))
    return rows, total


def rebuild_rankings(batch_size=1000, reference=None):
    """从 DB 全量重算四个 zset 到临时 key，再与 T_r 一起原子发布；不持锁、不阻塞请求写。

    reference 是发布后的 T_r（低频管理命令推进 T 时传新基准）；不传则沿用当前 T_r，
    只做纠偏。分数统一乘 decay(T_db, T_r)：推进后两者相等，因子为 1。likes 榜不缩放。
    """
    if batch_size <= 0:
        raise ValueError('batch_size must be positive')
    target = reference or get_hot_reference()
    factor = decay(read_db_hot_reference(), target)
    prefix = MEDIA_REBUILD_PREFIX + uuid4().hex
    temporary = {key: f'{prefix}:{key}' for key in MEDIA_RANK_KEYS}
    try:
        count = 0
        with cache.pipeline() as pipe:
            queryset = Media.objects.filter(status=MediaStatus.VERIFIED).only('id', 'user_id', 'likes', 'hot_value')
            for media in queryset.iterator(chunk_size=batch_size):
                hot = media.hot_value * factor
                pipe.zadd(temporary[MEDIA_RANK_HOT], {media.pk: hot})
                pipe.zadd(temporary[MEDIA_RANK_LIKES], {media.pk: media.likes})
                pipe.zincrby(temporary[MEDIA_RANK_USER_HOT], hot, media.user_id)
                pipe.zincrby(temporary[MEDIA_RANK_USER_LIKES], media.likes, media.user_id)
                count += 1
                if count % batch_size == 0:
                    pipe.execute()
            if count % batch_size:
                pipe.execute()
        with cache.pipeline(transaction=True) as pipe:
            for key, temp_key in temporary.items():
                if cache.exists(temp_key):
                    pipe.rename(temp_key, key)
                else:
                    pipe.delete(key)
            pipe.set(MEDIA_HOT_ANCHOR, target.isoformat())
            pipe.execute()
        return count
    finally:
        cache.delete(*temporary.values())


def clear_rankings():
    cache.delete(*MEDIA_CACHE_KEYS)
