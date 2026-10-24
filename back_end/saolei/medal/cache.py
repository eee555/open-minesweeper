from django.core.cache import caches

from .utils import CATALOG_CACHE_KEY, CATALOG_CACHE_SECONDS, STATE_CACHE_KEY


def _cache():
    return caches['default']


def read_catalog():
    return _cache().get(CATALOG_CACHE_KEY)


def write_catalog(payload):
    _cache().set(CATALOG_CACHE_KEY, payload, CATALOG_CACHE_SECONDS)


def invalidate_catalog():
    _cache().delete(CATALOG_CACHE_KEY)


def player_state_key(user_id):
    return STATE_CACHE_KEY.format(user_id=user_id)


def read_player_state(user_id):
    return _cache().get(player_state_key(user_id))


def read_player_states(user_ids):
    mapping = {player_state_key(user_id): user_id for user_id in user_ids}
    found = _cache().get_many(list(mapping))
    return {mapping[key]: value for key, value in found.items()}


def write_player_state(user_id, payload):
    # timeout=None：django-redis 不设 TTL，LocMem 的过期时间也是 None。
    _cache().set(player_state_key(user_id), payload, timeout=None)


def delete_player_states(user_ids):
    if not user_ids:
        return
    _cache().delete_many([player_state_key(user_id) for user_id in user_ids])
