import re
from urllib.parse import urlsplit, urlunsplit

from utils.exceptions import ExceptionToResponse

CALLBACK_PATH = '/api/userprofile/qq/callback'
STATE_PATTERN = re.compile(r'^[A-Za-z0-9_-]{43}$')
OPENID_PATTERN = re.compile(r'^[0-9A-Fa-f]{32}(?:[0-9A-Fa-f]{4})?$')


def qq_error(category, status_code=400):
    return ExceptionToResponse('qq_login', category, status_code)


def avatar_url(value):
    if not isinstance(value, str) or len(value) > 1024:
        return ''
    parsed = urlsplit(value)
    host = parsed.hostname or ''
    if parsed.scheme not in {'http', 'https'} or not host.endswith('.qlogo.cn') or parsed.netloc != host or parsed.fragment:
        return ''
    # 官方接口仍可能返回 http 头像；只把已核实的腾讯头像域升级到 HTTPS。
    return urlunsplit(('https', parsed.netloc, parsed.path, parsed.query, ''))
