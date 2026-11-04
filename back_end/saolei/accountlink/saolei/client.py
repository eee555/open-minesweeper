import time

from django_redis import get_redis_connection
import httpx
from saolei_api import Client, RateLimitError

from utils.secrets_json import read_secret


class ThrottledTransport(httpx.BaseTransport):
    """手动请求、worker 和命令共用上游额度，HTTP 和响应解析仍由现有客户端处理。"""

    def __init__(self, transport=None):
        self.transport = transport if transport is not None else httpx.HTTPTransport()

    def handle_request(self, request):
        download = request.url.path.startswith('/videos/')
        interval = 400 if download else 2100
        key = 'saolei:throttle:download' if download else 'saolei:throttle:data'
        redis = get_redis_connection()
        deadline = time.monotonic() + 6
        while not redis.set(key, '1', nx=True, px=interval):
            if time.monotonic() >= deadline:
                raise RateLimitError('local shared quota', interval / 1000)
            time.sleep(0.1)
        return self.transport.handle_request(request)

    def close(self):
        self.transport.close()


def saolei_client():
    """密钥只在实际同步时读取；跨进程节流不依赖客户端实例的生命周期。"""
    return Client(read_secret('saolei_api_key'), timeout=30, min_interval=2.1, download_interval=0.4, transport=ThrottledTransport())
