import logging
from time import monotonic
from urllib.parse import urlsplit

from authlib.common.errors import AuthlibBaseError
from authlib.integrations.requests_client import OAuth2Session
from django.conf import settings
import requests

from utils.exceptions import ExceptionToResponse
from .utils import avatar_url, CALLBACK_PATH, OPENID_PATTERN, qq_error

AUTHORIZE_URL = 'https://graph.qq.com/oauth2.0/authorize'
TOKEN_URL = 'https://graph.qq.com/oauth2.0/token'
ME_URL = 'https://graph.qq.com/oauth2.0/me'
PROFILE_URL = 'https://graph.qq.com/user/get_user_info'
REQUEST_TIMEOUT = (1, 1.5)
logger = logging.getLogger('userprofile')


def oauth_client():
    appid = settings.QQ_OAUTH_CLIENT_ID.strip()
    secret = settings.QQ_OAUTH_CLIENT_SECRET.strip()
    redirect = settings.QQ_OAUTH_REDIRECT_URI
    parsed = urlsplit(redirect)
    schemes = {'http', 'https'} if settings.DEBUG else {'https'}
    if not appid.isascii() or not appid.isdigit() or len(appid) > 32 or not secret or parsed.scheme not in schemes or not parsed.netloc or parsed.username or parsed.path != CALLBACK_PATH or parsed.query or parsed.fragment:
        raise qq_error('not_configured', 503)
    # 腾讯要求 GET 查询参数传 appkey；fetch_token 显式传 secret，Authlib 添加 client_id。
    return OAuth2Session(appid, secret, redirect_uri=redirect, scope='get_user_info', token_endpoint_auth_method='none', token_placement='uri', default_timeout=REQUEST_TIMEOUT)


def configured():
    try:
        with oauth_client():
            return True
    except ExceptionToResponse as exc:
        if exc.category == 'not_configured':
            return False
        raise


def authorization_url(client, state):
    url, _ = client.create_authorization_url(AUTHORIZE_URL, state=state)
    return url


def authorized_identity(code):
    stage = 'token'
    started = monotonic()
    try:
        with oauth_client() as client:
            token = client.fetch_token(TOKEN_URL, method='GET', code=code, client_secret=client.client_secret, fmt='json', timeout=REQUEST_TIMEOUT, allow_redirects=False)
            if not isinstance(token.get('access_token'), str) or not token['access_token'] or len(token['access_token']) > 4096:
                raise qq_error('remote_failed', 502)
            stage = 'identity'
            response = client.get(ME_URL, params={'fmt': 'json'}, timeout=REQUEST_TIMEOUT, allow_redirects=False)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or str(data.get('client_id')) != client.client_id or not isinstance(data.get('openid'), str) or not OPENID_PATTERN.fullmatch(data['openid']):
                raise qq_error('remote_failed', 502)
            identity = {'appid': client.client_id, 'openid': data['openid'].upper(), 'unionid': None, 'nickname': '', 'avatar_url': ''}
            if isinstance(data.get('unionid'), str) and 0 < len(data['unionid']) <= 64:
                identity['unionid'] = data['unionid']
            # 身份验证已完成；资料拉取失败不影响登录或绑定，下次授权再补齐。
            stage = 'profile'
            try:
                response = client.get(PROFILE_URL, params={'oauth_consumer_key': client.client_id, 'openid': identity['openid']}, timeout=REQUEST_TIMEOUT, allow_redirects=False)
                response.raise_for_status()
                profile = response.json()
                if not isinstance(profile, dict) or type(profile.get('ret')) is not int or profile['ret'] != 0:
                    raise ValueError('invalid_profile')
                nickname = profile.get('nickname')
                identity['nickname'] = nickname.strip()[:128] if isinstance(nickname, str) else ''
                identity['avatar_url'] = avatar_url(profile.get('figureurl_qq_2') or profile.get('figureurl_qq_1') or profile.get('figureurl_2'))
            except (requests.RequestException, AuthlibBaseError, ValueError, TypeError) as exc:
                logger.warning('QQ profile unavailable exception_type=%s', type(exc).__name__)
            if monotonic() - started > 8:
                logger.warning('QQ OAuth slow stage=%s', stage)
            return identity
    except (requests.RequestException, AuthlibBaseError, ValueError, TypeError) as exc:
        logger.warning('QQ OAuth failed stage=%s exception_type=%s', stage, type(exc).__name__)
        raise qq_error('remote_failed', 502) from None
