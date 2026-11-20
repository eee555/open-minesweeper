import secrets

from django.core.cache import cache
from django.utils.crypto import salted_hmac

from utils.exceptions import ExceptionToResponse
from .utils import qq_error, STATE_PATTERN

FLOW_TTL = 600


def session_fingerprint(session_key):
    return salted_hmac('qq-oauth-session', session_key or '').hexdigest()


def key(kind, value):
    return f'userprofile:qq:{kind}:{value}'


def revoke(state):
    if state:
        cache.set(key('used', state), 'revoked', timeout=FLOW_TTL)
        cache.delete(key('flow', state))


def invalidate_user_flow(user_id):
    revoke(cache.get(key('user', user_id)))


def create_flow(session_key, user_id, appid, mode):
    fingerprint = session_fingerprint(session_key)
    revoke(cache.get(key('active', fingerprint)))
    cache.delete(key('pending', fingerprint))
    state = secrets.token_urlsafe(32)
    flow = {'session': fingerprint, 'user_id': user_id, 'appid': appid, 'mode': mode}
    cache.set(key('flow', state), flow, timeout=FLOW_TTL)
    cache.set(key('active', fingerprint), state, timeout=FLOW_TTL)
    if user_id:
        invalidate_user_flow(user_id)
        cache.set(key('user', user_id), state, timeout=FLOW_TTL)
    return state


def require_active(state, session_key, user_id=0):
    if cache.get(key('active', session_fingerprint(session_key))) != state or cache.get(key('used', state)) == 'revoked':
        raise qq_error('expired', 409)
    if user_id and cache.get(key('user', user_id)) != state:
        raise qq_error('expired', 409)


def consume_flow(state, session_key):
    if not STATE_PATTERN.fullmatch(state):
        raise qq_error('expired', 409)
    flow = cache.get(key('flow', state))
    if not flow or flow['session'] != session_fingerprint(session_key):
        raise qq_error('expired', 409)
    require_active(state, session_key, flow['user_id'])
    if not cache.add(key('used', state), True, timeout=FLOW_TTL):
        raise qq_error('expired', 409)
    cache.delete(key('flow', state))
    return flow


def set_pending(session_key, state, identity):
    require_active(state, session_key)
    cache.set(key('pending', session_fingerprint(session_key)), {'state': state, 'identity': identity}, timeout=FLOW_TTL)


def get_pending(session_key):
    pending = cache.get(key('pending', session_fingerprint(session_key)))
    if pending:
        try:
            require_active(pending['state'], session_key)
        except ExceptionToResponse as exc:
            if exc.category != 'expired':
                raise
            return None
    return pending


def take_pending(session_key):
    pending = get_pending(session_key)
    if not pending or not cache.add(key('registered', pending['state']), True, timeout=FLOW_TTL):
        raise qq_error('expired', 409)
    cache.delete(key('pending', session_fingerprint(session_key)))
    return pending


def cancel(session_key):
    fingerprint = session_fingerprint(session_key)
    revoke(cache.get(key('active', fingerprint)))
    cache.delete(key('pending', fingerprint))
