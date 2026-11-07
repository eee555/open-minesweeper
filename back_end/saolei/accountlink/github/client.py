from urllib.parse import urlsplit

from authlib.common.errors import AuthlibBaseError
from authlib.integrations.requests_client import OAuth2Session
from django.conf import settings
import requests

from utils.exceptions import ExceptionToResponse

AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
TOKEN_URL = 'https://github.com/login/oauth/access_token'
USER_URL = 'https://api.github.com/user'
CALLBACK_PATH = settings.GITHUB_OAUTH_CALLBACK_PATH
REQUEST_TIMEOUT = (1, 1.5)


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
    try:
        with oauth_client() as client:
            client.fetch_token(TOKEN_URL, code=code, code_verifier=verifier, timeout=REQUEST_TIMEOUT, allow_redirects=False)
            response = client.get(USER_URL, timeout=REQUEST_TIMEOUT, allow_redirects=False, headers={'Accept': 'application/vnd.github+json'})
            response.raise_for_status()
            data = response.json()
    except (requests.RequestException, AuthlibBaseError, ValueError):
        # OAuth 异常的 description 及 HTTP 异常可能含凭据或 URL，不写入日志。
        raise ExceptionToResponse('github', 'remote_failed', 502) from None
    value = data.get('id') if isinstance(data, dict) else None
    if type(value) is not int or not 1 <= value <= 9223372036854775807:
        raise ExceptionToResponse('github', 'remote_failed', 502)
    return value
