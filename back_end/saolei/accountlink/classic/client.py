"""95经典扫雷外部应用接口：服务端到服务端，只有发起绑定与回调验签两件事。"""
import hashlib
import hmac
import time

from django.conf import settings
import requests

from utils.exceptions import ExceptionToResponse
from utils.secrets_json import read_secret

# 远端错误码 → 本地错误分类与响应状态；未列出的码一律视为无法识别的响应。
CLASSIC_ERROR_CATEGORIES = {
    40001: ('bad_request', 400),
    40002: ('bad_callback', 502),
    40101: ('unauthorized', 502),
    40301: ('app_mismatch', 502),
    40401: ('uid_not_found', 404),
    40901: ('already_bound', 409),
    40902: ('denied_recently', 409),
    40903: ('revoked_recently', 409),
    42901: ('rate_limited', 429),
}


def request_classic_bind(uid: int, account: str, callback_url: str, expires_in: int) -> int:
    """发起绑定申请，返回远端 requestId；受理不代表绑定成功。"""
    api_key = _required_secret('classic_bind_api_key')

    try:
        response = requests.post(
            settings.CLASSIC_BIND_URL,
            headers={'Authorization': f'Bearer {api_key}'},
            json={
                'uid': uid,
                'account': account,
                'callback': callback_url,
                'expiresIn': expires_in,
                'method': 'POST',
            },
            timeout=settings.CLASSIC_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        raise ExceptionToResponse('classic', 'timeout', status_code=503)
    except requests.exceptions.RequestException:
        raise ExceptionToResponse('classic', 'requestexception', status_code=503)

    return _parse_bind_response(response)


def verify_classic_callback(app_secret: str, timestamp: str, raw_body: bytes, signature: str) -> bool:
    """HMAC-SHA256(app_secret, timestamp + '.' + 原始请求体)，并限制时间戳窗口。"""
    if not app_secret or not timestamp or not signature:
        return False
    try:
        signed_at = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(int(time.time()) - signed_at) > settings.CLASSIC_CALLBACK_TOLERANCE_SECONDS:
        return False
    expected = hmac.new(app_secret.encode(), f'{timestamp}.'.encode() + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


def required_callback_secret() -> str:
    """回调验签密钥，使用前才从 secrets.json 读取，更换密钥无需重启。"""
    return _required_secret('classic_callback_app_secret')


def _required_secret(key: str) -> str:
    value = str(read_secret(key)).strip()
    if not value:
        raise ExceptionToResponse('classic', 'not_configured', status_code=503)
    return value


def _parse_bind_response(response) -> int:
    try:
        payload = response.json()
    except ValueError:
        raise ExceptionToResponse('classic', 'response', status_code=502)
    if not isinstance(payload, dict):
        raise ExceptionToResponse('classic', 'response', status_code=502)

    code = payload.get('code')
    if not isinstance(code, int) or isinstance(code, bool):
        raise ExceptionToResponse('classic', 'response', status_code=502)

    if code == 0:
        data = payload.get('data')
        request_id = data.get('requestId') if isinstance(data, dict) else None
        if response.status_code != 200 or not isinstance(request_id, int) or isinstance(request_id, bool) or request_id <= 0:
            raise ExceptionToResponse('classic', 'response', status_code=502)
        return request_id

    category, status_code = CLASSIC_ERROR_CATEGORIES.get(code, ('response', 502))
    raise ExceptionToResponse('classic', category, status_code=status_code)
