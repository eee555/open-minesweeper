from importlib import import_module
import logging
import re
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import HASH_SESSION_KEY, SESSION_KEY
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.crypto import constant_time_compare
from django.views.decorators.cache import never_cache
from django_ratelimit.decorators import ratelimit
from ninja import Router, Schema
from ninja.decorators import decorate_view

from userprofile.decorators import admin_csrf_required, login_required_error
from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from .cache import consume_flow, create_flow, invalidate_flow, require_active_flow
from .client import authorization_url, authorized_user_id
from .services import unlink_github_account
from ..models import AccountGitHub, Platform
from ..services import save_verified_account_link

router = Router()
logger = logging.getLogger('accountlink')


class AuthorizationOut(Schema):
    authorization_url: str


def current_session_user(request):
    if not request.user.is_authenticated or not request.session.session_key:
        raise ExceptionToResponse('github', 'expired', 403)
    user = UserProfile.objects.filter(pk=request.user.pk, is_active=True, is_memorial=False).first()
    session = import_module(settings.SESSION_ENGINE).SessionStore(request.session.session_key).load()
    if user is None or str(session.get(SESSION_KEY)) != str(user.pk) or not constant_time_compare(session.get(HASH_SESSION_KEY, ''), user.get_session_auth_hash()):
        # 并行退出会删除服务端 Session；不要让响应中间件再次保存旧登录数据。
        request.session.flush()
        raise ExceptionToResponse('github', 'expired', 403)
    return user


def result_redirect(user_id, result):
    # 前端地址来自服务端配置，不接受 return_url；code/state 不带回 SPA。
    origin = getattr(settings, 'GITHUB_OAUTH_FRONTEND_URL', 'http://localhost:8080' if settings.DEBUG else 'https://openms.top')
    response = HttpResponseRedirect(f'{origin.rstrip("/")}/#/player/{user_id}/accountlink?{urlencode({"github": result})}')
    response['Referrer-Policy'] = 'no-referrer'
    return response


@router.post('/start', response=AuthorizationOut)
@decorate_view(never_cache, login_required_error, admin_csrf_required, ratelimit(key='user', rate='6/h', block=True))
def start(request):
    """
    - never_cache
    - login_required_error
    - admin_csrf_required
    - ratelimit(key='user', rate='6/h', block=True)
    """
    user = current_session_user(request)
    with transaction.atomic():
        UserProfile.objects.select_for_update().get(pk=user.pk)
        if AccountGitHub.objects.filter(parent=user).exists():
            raise ExceptionToResponse('github', 'already_linked', 409)
        state, verifier = create_flow(user.pk, request.session.session_key)
        url = authorization_url(state, verifier)
    return {'authorization_url': url}


@router.get('/callback')
@decorate_view(never_cache, ratelimit(key='ip', rate='30/m', block=True))
def callback(request):
    """
    - never_cache
    - ratelimit(key='ip', rate='30/m', block=True)
    """
    user_id = request.user.pk if request.user.is_authenticated else 0
    try:
        user = current_session_user(request)
        state = request.GET.get('state', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}', state):
            raise ExceptionToResponse('github', 'expired', 409)
        verifier = consume_flow(state, user.pk, request.session.session_key)
        if request.GET.get('error'):
            return result_redirect(user.pk, 'cancelled')
        code = request.GET.get('code', '')
        if not code or len(code) > 512:
            raise ExceptionToResponse('github', 'remote_failed', 400)
        github_id = authorized_user_id(code, verifier)
        with transaction.atomic():
            UserProfile.objects.select_for_update().get(pk=user.pk)
            user = current_session_user(request)
            require_active_flow(state, user.pk)
            save_verified_account_link(user, Platform.GITHUB, str(github_id))
            invalidate_flow(user.pk)
        logger.info('GitHub linked user_id=%s github_id=%s', user.pk, github_id)
        return result_redirect(user.pk, 'linked')
    except ExceptionToResponse as exc:
        result = 'conflict' if exc.category == 'collision' else exc.category
        if result not in {'conflict', 'expired', 'remote_failed', 'not_configured'}:
            result = 'remote_failed'
        logger.warning('GitHub linking failed user_id=%s category=%s', user_id, result)
        return result_redirect(user_id, result)
    except Exception as exc:
        logger.error('GitHub linking failed user_id=%s exception_type=%s', user_id, type(exc).__name__)
        return result_redirect(user_id, 'remote_failed')


@router.post('/unlink')
@decorate_view(never_cache, login_required_error, admin_csrf_required, ratelimit(key='user', rate='6/h', block=True))
def unlink(request):
    """
    - never_cache
    - login_required_error
    - admin_csrf_required
    - ratelimit(key='user', rate='6/h', block=True)
    """
    user = current_session_user(request)
    unlink_github_account(user.pk)
    return HttpResponse()
