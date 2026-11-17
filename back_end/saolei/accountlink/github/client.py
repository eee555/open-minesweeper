import logging
from time import monotonic
from urllib.parse import urlsplit

from authlib.common.errors import AuthlibBaseError
from authlib.integrations.requests_client import OAuth2Session
from django.conf import settings
import requests

from utils.exceptions import ExceptionToResponse

AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
TOKEN_URL = 'https://github.com/login/oauth/access_token'
USER_URL = 'https://api.github.com/user'
CALLBACK_PATH = '/api/accountlink/github/callback'
REQUEST_TIMEOUT = (1, 1.5)
OAUTH_ERROR_CODES = frozenset({
    'incorrect_client_credentials', 'redirect_uri_mismatch', 'bad_verification_code', 'unverified_user_email',
    'invalid_request', 'invalid_client', 'invalid_grant', 'unauthorized_client', 'unsupported_grant_type',
    'invalid_scope', 'access_denied', 'server_error', 'temporarily_unavailable', 'missing_token', 'unsupported_token_type',
})
logger = logging.getLogger('accountlink')


def oauth_client():
    client_id = settings.GITHUB_OAUTH_CLIENT_ID.strip()
    client_secret = settings.GITHUB_OAUTH_CLIENT_SECRET.strip()
    redirect_uri = settings.GITHUB_OAUTH_REDIRECT_URI.strip()
    parsed = urlsplit(redirect_uri)
    schemes = ('http', 'https') if settings.DEBUG else ('https',)
    if not client_id or not client_secret or parsed.scheme not in schemes or not parsed.netloc or parsed.path != CALLBACK_PATH or parsed.query or parsed.fragment or parsed.username:
        raise ExceptionToResponse('github', 'not_configured', 503)
    return OAuth2Session(
        client_id, client_secret, redirect_uri=redirect_uri, scope='', code_challenge_method='S256',
        token_endpoint_auth_method='client_secret_post', default_timeout=REQUEST_TIMEOUT,
    )


def authorization_url(client, state, verifier):
    url, _ = client.create_authorization_url(AUTHORIZE_URL, state=state, code_verifier=verifier, prompt='select_account')
    return url


def authorized_user_id(code, verifier):
    """访问令牌仅在本次请求内使用；公开资料不持久化。"""
    stage = 'token'
    http_status = None
    started = monotonic()

    def record_token_response(response):
        nonlocal http_status
        http_status = response.status_code
        return response

    try:
        with oauth_client() as client:
            client.register_compliance_hook('access_token_response', record_token_response)
            client.fetch_token(TOKEN_URL, code=code, code_verifier=verifier, timeout=REQUEST_TIMEOUT, allow_redirects=False)
            stage = 'user'
            http_status = None
            started = monotonic()
            response = client.get(USER_URL, timeout=REQUEST_TIMEOUT, allow_redirects=False, headers={'Accept': 'application/vnd.github+json'})
            http_status = response.status_code
            response.raise_for_status()
            data = response.json()
    except (requests.RequestException, AuthlibBaseError, ValueError) as exc:
        oauth_error = 'none'
        if isinstance(exc, AuthlibBaseError):
            oauth_error = exc.error if isinstance(exc.error, str) and exc.error in OAUTH_ERROR_CODES else 'unknown'
        # 不记录异常消息、description、响应体、请求头或 URL；错误码只接受白名单。
        logger.warning(
            'GitHub upstream failed stage=%s exception_type=%s http_status=%s oauth_error=%s elapsed_ms=%s',
            stage, type(exc).__name__, http_status, oauth_error, round((monotonic() - started) * 1000),
        )
        raise ExceptionToResponse('github', 'remote_failed', 502) from None
    value = data.get('id') if isinstance(data, dict) else None
    if type(value) is not int or not 1 <= value <= 9223372036854775807:
        logger.warning('GitHub upstream failed stage=user http_status=%s reason=invalid_identity', http_status)
        raise ExceptionToResponse('github', 'remote_failed', 502)
    return value
