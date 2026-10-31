from dataclasses import dataclass
from urllib.parse import urlsplit

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.requests_client import OAuth2Session
from django.conf import settings
from pydantic import BaseModel, ConfigDict, Field
import requests

from utils.exceptions import ExceptionToResponse
from utils.secrets_json import read_secrets

AUTHORIZE_URL = 'https://discord.com/oauth2/authorize'
TOKEN_URL = 'https://discord.com/api/oauth2/token'
USER_URL = 'https://discord.com/api/v10/users/@me'
DISCORD_TIMEOUT = 5


@dataclass(frozen=True)
class DiscordConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    frontend_url: str


class DiscordProfile(BaseModel):
    model_config = ConfigDict(strict=True, extra='ignore')
    id: str = Field(pattern=r'^[1-9][0-9]{0,19}$')
    username: str = Field(min_length=1, max_length=32)
    global_name: str | None = Field(default=None, max_length=32)
    avatar: str | None = Field(default=None, pattern=r'^(a_)?[0-9a-f]{32}$')
    banner: str | None = Field(default=None, pattern=r'^(a_)?[0-9a-f]{32}$')
    accent_color: int | None = Field(default=None, ge=0, le=0xFFFFFF)
    public_flags: int | None = Field(default=None, ge=0, le=9223372036854775807)

    def account_fields(self) -> dict:
        return {
            'username': self.username, 'global_name': self.global_name or '',
            'avatar': self.avatar or '', 'banner': self.banner or '',
            'accent_color': self.accent_color, 'public_flags': self.public_flags,
        }


def get_discord_config() -> DiscordConfig:
    try:
        data = read_secrets()
        values = [settings.DISCORD_OAUTH_CLIENT_ID, data.get('discord_oauth_client_secret')]
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise ValueError
        client_id, client_secret = [value.strip() for value in values]
        if not client_id.isascii() or not client_id.isdecimal() or len(client_id) > 20:
            raise ValueError
        redirect_uri = settings.DISCORD_OAUTH_REDIRECT_URI
        redirect = _validate_url(redirect_uri)
        frontend_url = data.get('discord_oauth_frontend_url', f'{redirect.scheme}://{redirect.netloc}')
        _validate_url(frontend_url)
    except (OSError, ValueError, TypeError):
        raise ExceptionToResponse('discord', 'not_configured', status_code=503) from None
    return DiscordConfig(client_id, client_secret, redirect_uri, frontend_url.rstrip('/'))


def _validate_url(value: str):
    if not isinstance(value, str) or not value or value != value.strip() or '\\' in value:
        raise ValueError
    parsed = urlsplit(value)
    local = parsed.hostname in ('localhost', '127.0.0.1', '::1')
    if not parsed.netloc or parsed.username or parsed.password or parsed.fragment or parsed.query:
        raise ValueError
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and local):
        raise ValueError
    return parsed


def discord_client(config: DiscordConfig) -> OAuth2Session:
    return OAuth2Session(
        config.client_id, config.client_secret,
        redirect_uri=config.redirect_uri, scope='identify',
        token_endpoint_auth_method='client_secret_basic', code_challenge_method='S256',
        default_timeout=DISCORD_TIMEOUT,
    )


def discord_authorization_url(config: DiscordConfig, verifier: str) -> tuple[str, str]:
    with discord_client(config) as client:
        return client.create_authorization_url(AUTHORIZE_URL, code_verifier=verifier, prompt='consent')


def fetch_discord_profile(config: DiscordConfig, code: str, verifier: str) -> DiscordProfile:
    try:
        with discord_client(config) as client:
            client.register_compliance_hook('access_token_response', _validate_token_response)
            client.fetch_token(TOKEN_URL, code=code, code_verifier=verifier, allow_redirects=False)
            response = client.get(USER_URL, allow_redirects=False)
            if response.status_code != 200:
                raise ExceptionToResponse('discord', 'upstream_error', status_code=502)
            return DiscordProfile.model_validate(response.json())
    except requests.exceptions.Timeout:
        raise ExceptionToResponse('discord', 'timeout', status_code=504) from None
    except OAuthError:
        raise ExceptionToResponse('discord', 'authorization_failed', status_code=400) from None
    except (requests.exceptions.RequestException, ValueError, TypeError):
        raise ExceptionToResponse('discord', 'upstream_error', status_code=502) from None


def _validate_token_response(response):
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError
    if 'error' in payload:
        return response
    token_type, token, scope = (payload.get(key) for key in ('token_type', 'access_token', 'scope'))
    if response.status_code != 200 or not isinstance(token_type, str) or token_type.lower() != 'bearer':
        raise ValueError
    if not isinstance(token, str) or not token or not isinstance(scope, str) or 'identify' not in scope.split():
        raise ValueError
    return response
