"""作品页 Redis 排行：四个 zset 与统一热度基准；见 MEDIA_PLAN.md 第 5.2、6 节。"""

from contextlib import contextmanager
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
MEDIA_CACHE_LOCK = 'media:cache:lock'
MEDIA_LOCK_TIMEOUT = 300
MEDIA_LOCK_BLOCKING_TIMEOUT = 60
MEDIA_RANK_KEYS = (MEDIA_RANK_HOT, MEDIA_RANK_LIKES, MEDIA_RANK_USER_HOT, MEDIA_RANK_USER_LIKES)
MEDIA_CACHE_KEYS = (*MEDIA_RANK_KEYS, MEDIA_HOT_ANCHOR)


class MediaCacheLockError(RuntimeError):
    """重建期间缓存锁过期；应暂停写入后重跑重建命令。"""


@contextmanager
def media_cache_lock():
    """跨进程串行化 zset / anchor 写入、投稿基准读取与月度刷新。

    锁的顺序统一为「先 Redis 锁、后 DB 事务」，避免持 DB 行锁等待 Redis 锁形成死锁。
    """
    lock = cache.lock(MEDIA_CACHE_LOCK, timeout=MEDIA_LOCK_TIMEOUT, blocking_timeout=MEDIA_LOCK_BLOCKING_TIMEOUT)
    with lock:
        yield lock


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


def _to_anchor_score(hot_value, base, anchor):
    """把以 base 为基准的 DB 热度换算成以 anchor 为基准的 zset 分数。"""
    return hot_value * decay(base, anchor)


def set_media_scores(media_id, author_id, media_hot, media_likes, user_hot, user_likes, has_works):
    """一次 MULTI/EXEC 写入四个 zset 的绝对分数；调用方须持有 media_cache_lock。

    media_hot=None 表示作品已不在榜。作者分数直接写绝对值，不存在「扣减到 0 后
    再在事务外 ZREM」的竞争窗口，期间的新投喂不会被清掉；has_works 与重建命令
    的 ZINCRBY 语义一致，保证 0 分作品仍能让作者出现在聚合榜。
    """
    with cache.pipeline() as pipe:
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


def sync_media_scores(media_id, author_id):
    """按回调执行时刻的 DB 重算并覆盖四个 zset 的绝对分数。

    不看回调发起时的快照：硬删除后的迟到投喂回调查不到作品行，只会移除而不会重新
    入榜；重建期间提交的投喂则在锁释放后按 DB 绝对值补齐，既不丢也不重复。
    """
    with media_cache_lock():
        anchor = get_hot_reference()
        rows = Media.objects.filter(user_id=author_id, status=MediaStatus.VERIFIED).values_list(
            'pk', 'hot_value', 'likes', 'hot_value_updated_at',
        )
        user_hot = 0.0
        user_likes = 0
        has_works = False
        media_hot = None
        media_likes = 0
        for pk, hot_value, likes, base in rows:
            has_works = True
            score = _to_anchor_score(hot_value, base, anchor)
            user_hot += score
            user_likes += likes
            if pk == media_id:
                media_hot, media_likes = score, likes
        set_media_scores(media_id, author_id, media_hot, media_likes, user_hot, user_likes, has_works)


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


def refresh_hot_reference(at_time=None):
    """锁内 WATCH anchor，按同一系数整体缩放两个 hot zset，写新锚点；幂等。"""
    with media_cache_lock():
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
    """锁内从 DB 只取 verified 全量重建四个 zset 与 anchor；临时 key + rename 原子发布。

    锁覆盖快照与发布全过程：期间提交的 DB 写入，其 on_commit 回调必须等锁释放后
    才按 DB 绝对值重算，因此不会「先写正式榜、后被旧快照 rename 覆盖」。
    """
    if batch_size <= 0:
        raise ValueError('batch_size must be positive')
    prefix = MEDIA_REBUILD_PREFIX + uuid4().hex
    temporary = {key: f'{prefix}:{key}' for key in MEDIA_RANK_KEYS}
    with media_cache_lock() as lock:
        earliest = Media.objects.order_by('hot_value_updated_at').values_list('hot_value_updated_at', flat=True).first()
        reference = earliest or media_hot_reference_time()
        try:
            count = 0
            with cache.pipeline() as pipe:
                queryset = Media.objects.filter(status=MediaStatus.VERIFIED).only(
                    'id', 'user_id', 'likes', 'hot_value', 'hot_value_updated_at',
                )
                for media in queryset.iterator(chunk_size=batch_size):
                    hot = _to_anchor_score(media.hot_value, media.hot_value_updated_at, reference)
                    pipe.zadd(temporary[MEDIA_RANK_HOT], {media.pk: hot})
                    pipe.zadd(temporary[MEDIA_RANK_LIKES], {media.pk: media.likes})
                    pipe.zincrby(temporary[MEDIA_RANK_USER_HOT], hot, media.user_id)
                    pipe.zincrby(temporary[MEDIA_RANK_USER_LIKES], media.likes, media.user_id)
                    count += 1
                    if count % batch_size == 0:
                        pipe.execute()
                if count % batch_size:
                    pipe.execute()
            if not lock.owned():
                raise MediaCacheLockError('media cache lock expired during rebuild; pause writes and retry')
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
    cache.delete(*MEDIA_CACHE_KEYS, MEDIA_CACHE_LOCK)
