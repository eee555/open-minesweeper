from importlib import import_module
import logging
import secrets
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import HASH_SESSION_KEY, login, SESSION_KEY
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.crypto import constant_time_compare
from django.views.decorators.cache import never_cache
from django_ratelimit.decorators import ratelimit
from ninja import Router
from ninja.decorators import decorate_view

from utils.exceptions import ExceptionToResponse
from . import cache, client, services
from .schema import EmailIn, RegisteredOut, StartIn, StartOut, StatusOut, UsernameIn
from .utils import qq_error
from ..decorators import admin_csrf_required, login_required_error
from ..models import QQConnectIdentity, UserProfile

router = Router()
logger = logging.getLogger('userprofile')


def require_session(request, user_id=0):
    """回调提交前复核服务端会话，避免退出、换号或停用后签发/恢复旧会话。"""
    session_key = request.session.session_key
    stored = import_module(settings.SESSION_ENGINE).SessionStore(session_key).load() if session_key else {}
    nonce = request.session.get('qq_oauth_nonce', '')
    if not nonce or not constant_time_compare(stored.get('qq_oauth_nonce', ''), nonce):
        request.session.flush()
        raise qq_error('expired', 409)
    if not user_id:
        if request.user.is_authenticated or stored.get(SESSION_KEY):
            raise qq_error('expired', 409)
        return None
    user = UserProfile.objects.filter(pk=user_id, is_active=True, is_memorial=False).first()
    if user is None or request.user.pk != user_id or str(stored.get(SESSION_KEY)) != str(user_id) or not constant_time_compare(stored.get(HASH_SESSION_KEY, ''), user.get_session_auth_hash()):
        request.session.flush()
        raise qq_error('expired', 409)
    return user


def ensure_session(request):
    if not request.session.session_key:
        request.session.create()
    request.session['qq_oauth_nonce'] = secrets.token_urlsafe(24)
    request.session.save()  # noqa: DJM100 - SessionStore is not a Django model


def result_redirect(result):
    origin = settings.QQ_OAUTH_FRONTEND_URL.rstrip('/')
    response = HttpResponseRedirect(f'{origin}/#/qq-login?{urlencode({"result": result})}')
    response['Referrer-Policy'] = 'no-referrer'
    return response


def establish_login(request, user):
    if not user.is_active or user.is_memorial:
        raise qq_error('disabled', 403)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    request.session.set_expiry(settings.SESSION_COOKIE_AGE)


@router.post('/start', response=StartOut)
@decorate_view(never_cache, admin_csrf_required, ratelimit(key='ip', rate='12/h', block=True))
def start(request, data: StartIn):
    """
    - never_cache
    - admin_csrf_required
    - ratelimit(key='ip', rate='12/h', block=True)
    """
    if data.mode == 'login' and (request.user.is_authenticated or not settings.QQ_OAUTH_LOGIN_ENABLED):
        raise qq_error('login_unavailable', 409)
    if data.mode == 'bind' and not request.user.is_authenticated:
        raise qq_error('login_required', 403)
    with client.oauth_client() as oauth:
        ensure_session(request)
        user_id = request.user.pk if data.mode == 'bind' else 0
        require_session(request, user_id)
        with transaction.atomic():
            if user_id:
                UserProfile.objects.select_for_update().get(pk=user_id)
                require_session(request, user_id)
            state = cache.create_flow(request.session.session_key, user_id, oauth.client_id, data.mode)
            return {'authorization_url': client.authorization_url(oauth, state)}


@router.get('/callback')
@decorate_view(never_cache, ratelimit(key='ip', rate='30/m', block=True))
def callback(request):
    """
    - never_cache
    - ratelimit(key='ip', rate='30/m', block=True)
    """
    try:
        state = request.GET.get('state', '')
        flow = cache.consume_flow(state, request.session.session_key)
        require_session(request, flow['user_id'])
        if request.GET.get('error'):
            cache.revoke(state)
            return result_redirect('cancelled')
        code = request.GET.get('code', '')
        if not code or len(code) > 512:
            raise qq_error('remote_failed', 400)
        if flow['mode'] == 'login' and not settings.QQ_OAUTH_LOGIN_ENABLED:
            raise qq_error('login_unavailable', 409)
        data = client.authorized_identity(code)
        if data['appid'] != flow['appid']:
            raise qq_error('expired', 409)
        if flow['mode'] == 'bind':
            with transaction.atomic():
                UserProfile.objects.select_for_update().get(pk=flow['user_id'])
                user = require_session(request, flow['user_id'])
                cache.require_active(state, request.session.session_key, user.pk)
                services.bind_identity(user, data)
                cache.revoke(state)
            logger.info('QQ login bound user_id=%s', user.pk)
            return result_redirect('linked')
        require_session(request)
        cache.require_active(state, request.session.session_key)
        identity = QQConnectIdentity.objects.filter(appid=data['appid'], openid=data['openid']).first()
        if identity is None:
            cache.set_pending(request.session.session_key, state, data)
            return result_redirect('pending')
        with transaction.atomic():
            user = UserProfile.objects.select_for_update().get(pk=identity.parent_id)
            require_session(request)
            cache.require_active(state, request.session.session_key)
            identity = QQConnectIdentity.objects.filter(pk=identity.pk, parent=user, appid=data['appid'], openid=data['openid']).first()
            if identity is None:
                raise qq_error('expired', 409)
            if not user.is_active or user.is_memorial:
                raise qq_error('disabled', 403)
            services.update_profile(identity, data)
            cache.revoke(state)
            establish_login(request, user)
        logger.info('QQ login user_id=%s', user.pk)
        return result_redirect('logged_in')
    except ExceptionToResponse as exc:
        logger.warning('QQ login failed category=%s', exc.category)
        return result_redirect(exc.category)
    except Exception as exc:
        logger.error('QQ login failed exception_type=%s', type(exc).__name__)
        return result_redirect('remote_failed')


@router.get('/status', response=StatusOut)
@decorate_view(never_cache, ratelimit(key='ip', rate='60/m', block=True))
def status(request):
    """
    - never_cache
    - ratelimit(key='ip', rate='60/m', block=True)
    """
    identity = QQConnectIdentity.objects.filter(parent=request.user).first() if request.user.is_authenticated else None
    pending = cache.get_pending(request.session.session_key) if not request.user.is_authenticated else None
    return {
        'user_id': request.user.pk if request.user.is_authenticated else 0,
        'username': request.user.username if request.user.is_authenticated else '',
        'configured': client.configured(), 'login_enabled': settings.QQ_OAUTH_LOGIN_ENABLED,
        'linked': identity is not None, 'profile': identity,
        'pending': pending['identity'] if pending else None,
        'can_unlink': services.has_recovery(request.user) if identity else False,
        'has_email': request.user.is_authenticated and not request.user.email.lower().endswith('@accounts.invalid'),
        'can_set_username': identity is not None and services.can_set_username(request.user),
    }


@router.post('/register', response=RegisteredOut)
@decorate_view(never_cache, ratelimit(key='ip', rate='6/h', block=True))
def register(request):
    """
    - never_cache
    - ratelimit(key='ip', rate='6/h', block=True)

    授权后一次确认开通，不要求邮箱或密码；消费当前匿名会话的一次性凭证。
    """
    require_session(request)
    if not settings.QQ_OAUTH_LOGIN_ENABLED:
        raise qq_error('login_unavailable', 409)
    pending = cache.take_pending(request.session.session_key)
    if pending['identity']['appid'] != settings.QQ_OAUTH_CLIENT_ID:
        raise qq_error('expired', 409)
    with transaction.atomic():
        require_session(request)
        cache.require_active(pending['state'], request.session.session_key)
        user = services.register_identity(pending['identity'])
        cache.revoke(pending['state'])
        establish_login(request, user)
    logger.info('QQ account created user_id=%s', user.pk)
    return {'user': user}


@router.post('/cancel')
@decorate_view(never_cache, admin_csrf_required, ratelimit(key='ip', rate='30/h', block=True))
def cancel(request):
    """
    - never_cache
    - admin_csrf_required
    - ratelimit(key='ip', rate='30/h', block=True)
    """
    cache.cancel(request.session.session_key)
    return HttpResponse()


@router.post('/unlink')
@decorate_view(never_cache, login_required_error, admin_csrf_required, ratelimit(key='user', rate='6/h', block=True))
def unlink(request):
    """
    - never_cache
    - login_required_error
    - admin_csrf_required
    - ratelimit(key='user', rate='6/h', block=True)
    """
    with transaction.atomic():
        user = UserProfile.objects.select_for_update().get(pk=request.user.pk)
        if not user.is_active or user.is_memorial:
            raise qq_error('disabled', 403)
        services.unlink_identity(user)
    return HttpResponse()


@router.post('/recovery-email')
@decorate_view(never_cache, login_required_error, admin_csrf_required, ratelimit(key='user', rate='6/h', block=True))
def recovery_email(request, data: EmailIn):
    """
    - never_cache
    - login_required_error
    - admin_csrf_required
    - ratelimit(key='user', rate='6/h', block=True)
    """
    with transaction.atomic():
        user = UserProfile.objects.select_for_update().get(pk=request.user.pk)
        if not user.is_active or user.is_memorial or not QQConnectIdentity.objects.filter(parent=user).exists():
            raise qq_error('login_required', 403)
        if not user.email.lower().endswith('@accounts.invalid'):
            raise qq_error('already_has_email', 409)
        try:
            services.bind_recovery_email(user, data.email, data.email_key, data.email_captcha)
        except ValidationError:
            raise qq_error('invalid_email', 400) from None
    return HttpResponse()


@router.post('/username', response=RegisteredOut)
@decorate_view(never_cache, login_required_error, admin_csrf_required, ratelimit(key='user', rate='6/h', block=True))
def username(request, data: UsernameIn):
    """
    - never_cache
    - login_required_error
    - admin_csrf_required
    - ratelimit(key='user', rate='6/h', block=True)

    QQ 新账号可自愿把系统生成的用户名设置一次；沿用用户名校验与内容审核。
    """
    user = request.user
    if not user.is_active or user.is_memorial or not QQConnectIdentity.objects.filter(parent=user).exists():
        raise qq_error('login_required', 403)
    if not services.can_set_username(user):
        raise qq_error('username_readonly', 409)
    try:
        value = services.prepare_username(user, data.username, request.META.get('REMOTE_ADDR', ''))
    except ValidationError:
        raise qq_error('invalid_username') from None
    with transaction.atomic():
        user = UserProfile.objects.select_for_update().get(pk=user.pk)
        if not user.is_active or user.is_memorial or not QQConnectIdentity.objects.filter(parent=user).exists():
            raise qq_error('login_required', 403)
        services.set_username(user, value)
    return {'user': user}
