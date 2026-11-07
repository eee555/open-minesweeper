import secrets

from django.core.cache import cache
from django.utils.crypto import salted_hmac

from utils.exceptions import ExceptionToResponse

FLOW_TTL = 600


def session_fingerprint(session_key):
    return salted_hmac('github-oauth-session', session_key).hexdigest()


def active_key(user_id):
    return f'accountlink:github:active:{user_id}'


def create_flow(user_id, session_key):
    state = secrets.token_urlsafe(32)
    flow = {'user_id': user_id, 'session': session_fingerprint(session_key), 'verifier': secrets.token_urlsafe(48)}
    cache.set(f'accountlink:github:flow:{state}', flow, timeout=FLOW_TTL)
    cache.set(active_key(user_id), state, timeout=FLOW_TTL)
    return state, flow['verifier']


def consume_flow(state, user_id, session_key):
    flow = cache.get(f'accountlink:github:flow:{state}')
    if not flow or flow['user_id'] != user_id or flow['session'] != session_fingerprint(session_key) or cache.get(active_key(user_id)) != state:
        raise ExceptionToResponse('github', 'expired', 409)
    if not cache.add(f'accountlink:github:used:{state}', True, timeout=FLOW_TTL):
        raise ExceptionToResponse('github', 'expired', 409)
    cache.delete(f'accountlink:github:flow:{state}')
    return flow['verifier']


def require_active_flow(state, user_id):
    if cache.get(active_key(user_id)) != state:
        raise ExceptionToResponse('github', 'expired', 409)


def invalidate_flow(user_id):
    cache.delete(active_key(user_id))
