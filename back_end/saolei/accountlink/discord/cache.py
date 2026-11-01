import secrets

from django.core.cache import caches

from utils.exceptions import ExceptionToResponse

FLOW_SECONDS = 600
BROWSER_SESSION_KEY = 'discord_oauth_browser'


def save_discord_flow(state: str, flow: dict):
    caches['default'].set(f'accountlink:discord:flow:{state}', flow, timeout=FLOW_SECONDS)


def consume_discord_flow(state: str, browser_nonce: str | None) -> dict:
    cache = caches['default']
    key = f'accountlink:discord:flow:{state}'
    flow = cache.get(key) if 0 < len(state) <= 128 else None
    if not flow or not browser_nonce or not secrets.compare_digest(flow['browser_nonce'], browser_nonce):
        raise ExceptionToResponse('discord', 'invalid_state', status_code=400)
    # Atomic cache.add makes simultaneous callbacks single-use across web workers.
    if not cache.add(f'accountlink:discord:used:{state}', True, timeout=FLOW_SECONDS):
        raise ExceptionToResponse('discord', 'invalid_state', status_code=400)
    cache.delete(key)
    return flow
