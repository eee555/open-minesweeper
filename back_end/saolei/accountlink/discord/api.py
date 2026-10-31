import secrets
from typing import Literal
from urllib.parse import urlencode

from django.contrib.auth import login
from django.http import HttpResponseRedirect
from django.views.decorators.cache import never_cache
from django_ratelimit.decorators import ratelimit
from ninja import Form, Router, Schema
from ninja.decorators import decorate_view
from pydantic import field_validator

from utils.exceptions import ExceptionToResponse
from .cache import BROWSER_SESSION_KEY, consume_discord_flow, save_discord_flow
from .client import discord_authorization_url, fetch_discord_profile, get_discord_config
from .services import discord_login_user
from ..models import Platform
from ..services import save_verified_account_link, unverify_account_link

router = Router()


class DiscordStartIn(Schema):
    mode: Literal['link', 'login']
    set_expiry: int = 0

    @field_validator('set_expiry')
    @classmethod
    def valid_expiry(cls, value):
        if value not in (0, 1, 7, 30, 90):
            raise ValueError('Expected 0, 1, 7, 30 or 90 days.')
        return value


class DiscordStartOut(Schema):
    authorization_url: str


class DiscordConfigOut(Schema):
    enabled: bool


@router.get('/config', response=DiscordConfigOut)
@decorate_view(never_cache, ratelimit(key='ip', rate='60/m', block=True))
def discord_config(request):
    """
    - never_cache
    - ratelimit(key='ip', rate='60/m', block=True)

    Report availability without exposing application credentials.
    """
    try:
        get_discord_config()
    except ExceptionToResponse:
        return {'enabled': False}
    return {'enabled': True}


@router.post('/start', response=DiscordStartOut)
@decorate_view(never_cache, ratelimit(key='ip', rate='30/h', block=True))
def discord_start(request, data: DiscordStartIn = Form(...)):  # noqa: B008
    """
    - never_cache
    - ratelimit(key='ip', rate='30/h', block=True)

    Start linking for the authenticated user, or login for an anonymous browser.
    Store the verifier server-side and bind state to this browser and user.
    """
    if data.mode == 'link' and not request.user.is_authenticated:
        raise ExceptionToResponse('discord', 'login_required', status_code=403)
    if data.mode == 'login' and request.user.is_authenticated:
        raise ExceptionToResponse('discord', 'session_changed', status_code=409)
    config = get_discord_config()
    browser_nonce = request.session.get(BROWSER_SESSION_KEY) or secrets.token_urlsafe(32)
    request.session[BROWSER_SESSION_KEY] = browser_nonce
    verifier = secrets.token_urlsafe(48)
    authorization_url, state = discord_authorization_url(config, verifier)
    save_discord_flow(state, {
        'mode': data.mode, 'user_id': request.user.pk, 'browser_nonce': browser_nonce,
        'verifier': verifier, 'client_id': config.client_id, 'redirect_uri': config.redirect_uri,
        'set_expiry': data.set_expiry,
    })
    return {'authorization_url': authorization_url}


@router.get('/callback')
@decorate_view(never_cache, ratelimit(key='ip', rate='60/h', block=True))
def discord_callback(request):
    """
    - never_cache
    - ratelimit(key='ip', rate='60/h', block=True)

    Consume state once, exchange the code and link or log in. Never forward codes,
    tokens or remote error descriptions to the frontend. No automatic registration.
    """
    config = get_discord_config()
    result = {}
    try:
        if any(len(request.GET.getlist(key)) > 1 for key in ('state', 'code', 'error', 'iss')):
            raise ExceptionToResponse('discord', 'invalid_state', status_code=400)
        flow = consume_discord_flow(request.GET.get('state', ''), request.session.get(BROWSER_SESSION_KEY))
        if flow['user_id'] != request.user.pk:
            raise ExceptionToResponse('discord', 'session_changed', status_code=409)
        if (flow['client_id'], flow['redirect_uri']) != (config.client_id, config.redirect_uri):
            raise ExceptionToResponse('discord', 'not_configured', status_code=503)
        # Discord currently supplies iss; accept its absence for older responses.
        if request.GET.get('iss', 'https://discord.com') != 'https://discord.com':
            raise ExceptionToResponse('discord', 'invalid_state', status_code=400)
        if request.GET.get('error'):
            raise ExceptionToResponse('discord', 'access_denied', status_code=400)
        code = request.GET.get('code', '')
        if not code or len(code) > 2048:
            raise ExceptionToResponse('discord', 'authorization_failed', status_code=400)
        profile = fetch_discord_profile(config, code, flow['verifier'])
        if flow['mode'] == 'link':
            save_verified_account_link(request.user, Platform.DISCORD, profile.id, profile.account_fields())
            result = {'status': 'linked', 'user_id': request.user.pk}
        else:
            user = discord_login_user(profile)
            if not user.is_active or user.is_memorial:
                raise ExceptionToResponse('discord', 'account_disabled', status_code=403)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            request.session.set_expiry(flow['set_expiry'] * 86400)
            result = {'status': 'logged_in', 'user_id': user.pk}
    except ExceptionToResponse as exc:
        category = 'identifier_conflict' if exc.obj == 'accountlink' and exc.category == 'collision' else exc.category
        result = {'error': category}
    response = HttpResponseRedirect(f'{config.frontend_url}/#/discord?{urlencode(result)}')
    response['Referrer-Policy'] = 'no-referrer'
    return response


@router.post('/unlink')
@decorate_view(never_cache, ratelimit(key='ip', rate='10/h', block=True))
def discord_unlink(request):
    """
    - never_cache
    - ratelimit(key='ip', rate='10/h', block=True)

    Remove the current user's Discord login identity. Existing site credentials remain.
    """
    if not request.user.is_authenticated:
        raise ExceptionToResponse('discord', 'login_required', status_code=403)
    account = getattr(request.user, 'account_discord', None)
    if account is None:
        raise ExceptionToResponse('discord', 'not_linked', status_code=404)
    unverify_account_link(request.user.pk, Platform.DISCORD, account.pk)
    return {'type': 'success'}
