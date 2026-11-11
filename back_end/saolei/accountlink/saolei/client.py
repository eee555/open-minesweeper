import time

from django_redis import get_redis_connection
import httpx
from saolei_api import Client, RateLimitError

from accountlink.saolei.challenge import is_bot_challenge
from utils.secrets_json import read_secret


class ThrottledTransport(httpx.BaseTransport):
    """手动请求、worker 和命令共用上游额度，HTTP 和响应解析仍由现有客户端处理。"""

    def __init__(self, transport=None, challenge=None):
        self.transport = transport if transport is not None else httpx.HTTPTransport()
        self.challenge = challenge
        self.challenge_cookies = {}

    def handle_request(self, request):
        download = request.url.path.startswith(('/videos/', '/video/download/'))
        interval = 400 if download else 2100
        key = 'saolei:throttle:download' if download else 'saolei:throttle:data'
        redis = get_redis_connection()
        deadline = time.monotonic() + 6
        while not redis.set(key, '1', nx=True, px=interval):
            if time.monotonic() >= deadline:
                raise RateLimitError('local shared quota', interval / 1000)
            time.sleep(0.1)
        response = self.transport.handle_request(self._with_cookies(request))
        if self.challenge is not None and self._needs_challenge(response):
            self.challenge_cookies = self.challenge(response.headers['Location'])
            response = self.transport.handle_request(self._with_cookies(request))
        return response

    @staticmethod
    def _needs_challenge(response):
        return 300 <= response.status_code < 400 and is_bot_challenge(response.headers.get('Location', ''))

    def _with_cookies(self, request):
        if not self.challenge_cookies:
            return request
        cookies = {}
        existing = request.headers.get('Cookie')
        if existing:
            for part in existing.split(';'):
                name, _, value = part.strip().partition('=')
                if name:
                    cookies[name] = value
        cookies.update(self.challenge_cookies)
        request.headers['Cookie'] = '; '.join(f'{name}={value}' for name, value in cookies.items())
        return request

    def close(self):
        self.transport.close()


def saolei_client(challenge=None):
    """密钥只在实际同步时读取；跨进程节流不依赖客户端实例的生命周期。"""
    return Client(read_secret('saolei_api_key'), timeout=30, min_interval=2.1, download_interval=0.4, transport=ThrottledTransport(challenge=challenge))
