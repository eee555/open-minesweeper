import logging

from django.core.cache import caches
from redis.exceptions import RedisError

from .utils import CATALOG_CACHE_KEY, CATALOG_CACHE_SECONDS, STATE_CACHE_KEY, STATE_CACHE_SECONDS

logger = logging.getLogger(__name__)


def _cache():
    return caches['default']


def _call(method, *args, default=None, **kwargs):
    try:
        return getattr(_cache(), method)(*args, **kwargs)
    except (OSError, RedisError):
        logger.warning('Medal display cache %s failed', method, exc_info=True)
        return default


def read_catalog():
    return _call('get', CATALOG_CACHE_KEY)


def write_catalog(payload):
    _call('set', CATALOG_CACHE_KEY, payload, CATALOG_CACHE_SECONDS)


def invalidate_catalog():
    _call('delete', CATALOG_CACHE_KEY)


def player_state_key(user_id):
    return STATE_CACHE_KEY.format(user_id=user_id)


def read_player_state(user_id):
    return _call('get', player_state_key(user_id))


def read_player_states(user_ids):
    mapping = {player_state_key(user_id): user_id for user_id in user_ids}
    if not mapping:
        return {}
    found = _call('get_many', list(mapping), default={})
    return {mapping[key]: value for key, value in found.items()}


def write_player_state(user_id, payload):
    write_player_states({user_id: payload})


def write_player_states(payloads):
    if not payloads:
        return
    mapping = {player_state_key(user_id): payload for user_id, payload in payloads.items()}
    failed = _call('set_many', mapping, timeout=STATE_CACHE_SECONDS, default=list(mapping))
    if failed:
        # 发布失败时优先清掉旧值；Redis 完全不可用时由 TTL 限定旧展示的寿命。
        _call('delete_many', list(mapping))


def delete_player_states(user_ids):
    if not user_ids:
        return
    _call('delete_many', [player_state_key(user_id) for user_id in user_ids])
