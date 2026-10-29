import http.client
import json
import logging
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit

import certifi
from django.conf import settings

from utils.exceptions import ExceptionToResponse
from .utils import normalize_wom_profile

logger = logging.getLogger('accountlink')

# 超时预算链，改动其中任一层都要同步检查其余三层：
#   客户端：总预算 10s，单次请求超时 6s，最多 2 次，退避上限 2s
#   nginx：/accountlink/update/ 与 /api/accountlink/verify/ 18s（default.conf）
#   uwsgi：这两条路径跳过 harakiri:10，用全局 90s（uwsgi.ini 的 route 例外）
#   前端：axios 20s
ATTEMPTS = 2
MAX_RETRY_DELAY = 2.0
# 总预算由看门狗兑现：到点 shutdown 连接，能打断建连、等响应头和读 body 的任意阻塞。
# 取 10s，给 nginx 的 18s 留足余量。
TOTAL_BUDGET = 10.0
# 服务方文档：429 是 nginx 入口限速（响应体是 HTML），503 是服务内并发已满，502/504 是上游异常。
RETRYABLE_STATUSES = frozenset({429, 502, 503, 504})
# 502 只有这几类值得重试；502 protocol 表示源站协议已变，重试无意义。
RETRYABLE_UPSTREAM_ERRORS = frozenset({'connection', 'timeout', 'error', ''})


class _Retry(Exception):
    """内部信号：本次尝试可以重试，delay 为建议等待秒数。"""

    def __init__(self, category: str, delay: float):
        super().__init__(category, delay)
        self.category = category
        self.delay = delay


class _RequestError(Exception):
    """一次请求在传输层失败，category 直接沿用站内错误分类。"""

    def __init__(self, category: str):
        super().__init__(category)
        self.category = category


def _backoff(attempt: int) -> float:
    return min(float(2 ** attempt), MAX_RETRY_DELAY)


def _delay(headers: dict, attempt: int) -> float:
    retry_after = headers.get('retry-after')
    if retry_after:
        try:
            return min(float(retry_after), MAX_RETRY_DELAY)
        except ValueError:
            pass
    return _backoff(attempt)


def _upstream_error(headers: dict, body: bytes) -> str:
    if not headers.get('content-type', '').startswith('application/json'):
        return ''
    try:
        payload = json.loads(body)
    except ValueError:
        return ''
    error = payload.get('error') if isinstance(payload, dict) else None
    return error if isinstance(error, str) else ''


def _parse(body: bytes, user_id: int) -> dict:
    try:
        profile = json.loads(body)
    except ValueError:
        logger.warning('WOM 资料解析失败 user #%s：响应不是 JSON', user_id)
        raise ExceptionToResponse(obj='import', category='indexerror') from None
    try:
        return normalize_wom_profile(profile, user_id)
    except ValueError:
        logger.warning('WOM 资料解析失败 user #%s：结构或身份与关联账号不符', user_id)
        raise ExceptionToResponse(obj='import', category='indexerror') from None


def _remaining(deadline: float) -> float:
    # 至少留 0.5 秒给一次尝试，避免预算耗尽时把 timeout 算成 0 或负数。
    return max(0.5, min(settings.WOM_API_TIMEOUT, deadline - time.monotonic()))


def _request(url: str, headers: dict, timeout: float, deadline: float) -> tuple[int, dict, bytes]:
    """发一次 GET，返回 (status, headers, body)。看门狗在总预算耗尽时打断阻塞读。"""
    parts = urlsplit(url)
    if parts.scheme == 'https':
        context = ssl.create_default_context(cafile=certifi.where())
        connection = http.client.HTTPSConnection(parts.hostname, parts.port or 443, timeout=timeout, context=context)
    else:
        connection = http.client.HTTPConnection(parts.hostname, parts.port or 80, timeout=timeout)
    sock = None
    aborted = threading.Event()

    def abort():
        aborted.set()
        # getresponse() 之后 connection.sock 会被置空，必须在建连后先留一份引用。
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    timer = threading.Timer(max(0.0, deadline - time.monotonic()), abort)
    timer.daemon = True
    try:
        connection.connect()
        sock = connection.sock
        timer.start()
        connection.request('GET', parts.path or '/', headers=headers)
        response = connection.getresponse()
        body = response.read()
        if aborted.is_set():
            # 被看门狗打断时 peer 可能只发了一半，看起来像正常响应，必须按超时处理。
            raise _RequestError('timeout')
        return response.status, {name.lower(): value for name, value in response.getheaders()}, body
    except TimeoutError:
        raise _RequestError('timeout') from None
    except (OSError, http.client.HTTPException):
        raise _RequestError('timeout' if aborted.is_set() else 'requestexception') from None
    finally:
        timer.cancel()
        connection.close()


def _attempt(url: str, headers: dict, user_id: int, attempt: int, deadline: float) -> dict:
    try:
        status, response_headers, body = _request(url, headers, _remaining(deadline), deadline)
    except _RequestError as error:
        raise _Retry(error.category, _backoff(attempt)) from None

    if status == 200:
        return _parse(body, user_id)

    error = _upstream_error(response_headers, body)
    logger.warning('WOM 资料请求失败 user #%s：HTTP %s %s', user_id, status, error)
    retryable = status in RETRYABLE_STATUSES
    if retryable and status == 502 and error not in RETRYABLE_UPSTREAM_ERRORS:
        retryable = False
    # 504 和 502 timeout 都来自上游超时，按原有约定归为 timeout。
    category = 'timeout' if status == 504 or error == 'timeout' else 'requestexception'
    if not retryable:
        raise ExceptionToResponse(obj='import', category=category)
    raise _Retry(category, _delay(response_headers, attempt))


def fetch_wom_profile(user_id: int) -> dict:
    """
    读取玩家公开资料并转换为站内字段。

    - 只读 HTTP 调用（api.lockhart.ren），不再使用 wom-api 的进程内 WebSocket 客户端。
    - 令牌来自环境变量 WOM_API_TOKEN，缺失时直接失败，不发起请求。
    - 只重试 429 / 502(connection|timeout|error) / 503 / 504 与网络异常；其余直接失败。
    """
    if not settings.WOM_API_TOKEN:
        logger.error('WOM 资料同步失败 user #%s：未配置 WOM_API_TOKEN', user_id)
        raise ExceptionToResponse(obj='import', category='requestexception')

    url = f'{settings.WOM_API_BASE_URL.rstrip("/")}/profile/{user_id}'
    headers = {'X-Api-Token': settings.WOM_API_TOKEN}
    deadline = time.monotonic() + TOTAL_BUDGET
    for attempt in range(ATTEMPTS - 1):
        try:
            return _attempt(url, headers, user_id, attempt, deadline)
        except _Retry as retry:
            if time.monotonic() + retry.delay >= deadline:
                raise ExceptionToResponse(obj='import', category=retry.category) from None
            time.sleep(retry.delay)
    try:
        return _attempt(url, headers, user_id, ATTEMPTS - 1, deadline)
    except _Retry as retry:
        raise ExceptionToResponse(obj='import', category=retry.category) from None
