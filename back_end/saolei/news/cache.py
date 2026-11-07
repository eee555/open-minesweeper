import json
import time
import uuid

from django_redis import get_redis_connection


cache = get_redis_connection('saolei_website')

EVENTS_KEY = 'news:events:v1'
ALL_KEY = 'news:idx:all:v1'
CATEGORY_KEY = 'news:idx:cat:{category}:v1'
CATEGORIES = ('pb', 'lsf', 'eff')
TTL_SECONDS = 7 * 24 * 3600
# 至少保留最新的这么多条；7 天内的记录同样全部保留。二者取并集，
# 因此只有「超出该窗口 且 早于 TTL」的记录才会被删除。
KEEP_LATEST_EVENTS = 200


def _decode(value):
    return value.decode() if isinstance(value, bytes) else value


def index_key(category=None):
    return ALL_KEY if category is None else CATEGORY_KEY.format(category=category)


def publish(category: str, player_id: int, payload: dict) -> dict:
    """写入一条事件；hash 的 field 没有 TTL，过期与超量条目必须在此显式回收。"""
    now = time.time()
    score = now * 1000
    event = {'id': uuid.uuid4().hex, 'category': category, 'occurred_at': int(score), 'player_id': player_id, 'payload': payload}
    raw = json.dumps(event, ensure_ascii=False, allow_nan=False)
    cutoff = (now - TTL_SECONDS) * 1000
    with cache.pipeline() as pipe:
        pipe.zrevrange(ALL_KEY, KEEP_LATEST_EVENTS - 1, -1)  # 超出保留窗口的候选
        pipe.zrangebyscore(ALL_KEY, '-inf', cutoff)          # 早于 TTL 的候选
        overflow, expired = pipe.execute()
    # 只删除「既超出保留窗口、又早于 TTL」的记录：
    # 7 天内的全部保留（即使超出窗口），最新的 N 条也全部保留（即使早于 TTL）。
    stale = {_decode(value) for value in overflow} & {_decode(value) for value in expired}
    with cache.pipeline() as pipe:
        if stale:
            pipe.hdel(EVENTS_KEY, *stale)
            pipe.zrem(ALL_KEY, *stale)
            for name in CATEGORIES:
                pipe.zrem(index_key(name), *stale)
        pipe.hset(EVENTS_KEY, event['id'], raw)
        pipe.zadd(ALL_KEY, {event['id']: score})
        pipe.zadd(index_key(category), {event['id']: score})
        for key in (EVENTS_KEY, ALL_KEY, *[index_key(name) for name in CATEGORIES]):
            pipe.expire(key, TTL_SECONDS)
        pipe.execute()
    return event


def read_events(category=None, limit=50) -> list[dict]:
    ids = [_decode(value) for value in cache.zrevrange(index_key(category), 0, max(0, limit - 1))]
    if not ids:
        return []
    events = []
    for raw in cache.hmget(EVENTS_KEY, ids):
        if raw is None:
            continue
        try:
            events.append(json.loads(raw))
        except (TypeError, ValueError):
            continue
    return events


def flush():
    cache.delete(EVENTS_KEY, ALL_KEY, *[index_key(name) for name in CATEGORIES])
