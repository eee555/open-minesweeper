"""外站作品元数据适配：详情接口只返回临时元数据，作者 id 不落库；见 MEDIA_PLAN.md 第 7.1、7.2 节。"""

from contextlib import contextmanager
from datetime import datetime, timezone as datetime_timezone
from time import sleep
from typing import NamedTuple

from bilibili_api import sync
from bilibili_api.article import Article
from bilibili_api.exceptions import ApiException, NetworkException, ResponseCodeException
from bilibili_api.utils.network import request_settings
from bilibili_api.video import Video
from curl_cffi import CurlError
from curl_cffi.requests.exceptions import Timeout as CurlTimeout
from django.utils import timezone
from httpx import TimeoutException
from saolei_api import AuthenticationError, Client, RateLimitError, ResponseError, TransportError

from accountlink.saolei.client import ThrottledTransport
from utils.secrets_json import read_secret
from .utils import MediaFormat, normalize_external_author_id

MEDIA_TITLE_MAX_LENGTH = 200
BILIBILI_TIMEOUT = 8.0
SAOLEI_TIMEOUT = 8.0
MAX_RETRY_WAIT = 1.0
BILIBILI_RATE_LIMIT_CODE = -509
DEGRADED_FETCH_CATEGORIES = frozenset({'timeout', 'upstream_error'})
# bilibili_api 默认 CurlCFFIClient 直接透传 curl_cffi 原生异常，不会包成 NetworkException。
BILIBILI_TIMEOUT_ERRORS = (TimeoutError, TimeoutException, CurlTimeout)
BILIBILI_NETWORK_ERRORS = (CurlError, NetworkException, ApiException)


class MediaMetadata(NamedTuple):
    """author_id 只在本次请求内用于与 AccountLinkQueue 比对，不持久化、不输出。"""
    title: str
    created_at: datetime
    author_id: str


class MediaFetchError(Exception):
    """外站拉取失败的分类；API 层据此转成统一错误响应，不含上游原始内容。"""

    def __init__(self, category, status_code):
        super().__init__(category, status_code)
        self.category = category
        self.status_code = status_code


@contextmanager
def _bilibili_timeout(timeout):
    """依赖只有全局 request_settings，临时设置并恢复，避免长期改变 accountlink 的 B 站调用。"""
    previous = request_settings.get_timeout()
    request_settings.set_timeout(timeout)
    try:
        yield
    finally:
        request_settings.set_timeout(previous)


def _retry_ttl(exc):
    raw = exc.raw if isinstance(exc.raw, dict) else {}
    ttl = raw.get('ttl')
    try:
        return min(max(float(ttl), 0.0), MAX_RETRY_WAIT)
    except (TypeError, ValueError):
        return MAX_RETRY_WAIT


def _call_bilibili(coroutine_factory):
    """每次重试都要新建协程；-509 按 ttl 等待 <= 1s 后重试一次，其它错误不重试。"""
    for attempt in range(2):
        try:
            with _bilibili_timeout(BILIBILI_TIMEOUT):
                return sync(coroutine_factory())
        except ResponseCodeException as exc:
            if exc.code == BILIBILI_RATE_LIMIT_CODE and attempt == 0:
                sleep(_retry_ttl(exc))
                continue
            raise MediaFetchError('upstream_error', 502) from None
        except BILIBILI_TIMEOUT_ERRORS:
            raise MediaFetchError('timeout', 504) from None
        except BILIBILI_NETWORK_ERRORS:
            raise MediaFetchError('upstream_error', 502) from None
    raise MediaFetchError('upstream_error', 502)


def _fetch_bilibili_video(bvid):
    data = _call_bilibili(lambda: Video(bvid=bvid).get_info())
    return data['title'], data['pubdate'], data['owner']['mid']


def _fetch_bilibili_article(cvid):
    data = _call_bilibili(lambda: Article(cvid=int(cvid)).get_detail())
    return data['title'], data.get('publish_time') or data['ctime'], data['author']['mid']


def _fetch_saolei_post(post_id):
    try:
        with Client(read_secret('saolei_api_key'), timeout=SAOLEI_TIMEOUT, min_interval=2.1,
                    download_interval=0.4, transport=ThrottledTransport()) as client:
            response = client.post_info(int(post_id))
    except (AuthenticationError, RateLimitError):
        raise MediaFetchError('upstream_error', 502) from None
    except TransportError:
        raise MediaFetchError('timeout', 504) from None
    except (ResponseError, ValueError, OSError):
        raise MediaFetchError('parse_error', 502) from None
    if not response.items:
        raise MediaFetchError('invalid_metadata', 502)
    post = response.items[0]
    return post.title, post.post_time, post.user_id


def _validate_metadata(title, timestamp, author_id):
    """作者 id 归一化为字符串，兼容非数字平台 id；仅用于一次性归属比对，不落库。"""
    if not isinstance(title, str) or not title.strip() or len(title) > MEDIA_TITLE_MAX_LENGTH:
        raise MediaFetchError('invalid_metadata', 502)
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
        raise MediaFetchError('invalid_metadata', 502)
    try:
        normalized = normalize_external_author_id(author_id)
    except ValueError:
        raise MediaFetchError('invalid_metadata', 502) from None
    try:
        created_at = datetime.fromtimestamp(timestamp, tz=datetime_timezone.utc)
    except (OverflowError, OSError, ValueError):
        raise MediaFetchError('invalid_metadata', 502) from None
    if created_at > timezone.now():
        raise MediaFetchError('invalid_metadata', 502)
    return MediaMetadata(title.strip(), created_at, normalized)


def fetch_media_metadata(media_format, suffix):
    """返回 MediaMetadata；失败抛 MediaFetchError。新增平台只需在此加分派分支。"""
    try:
        if media_format == MediaFormat.B_V:
            raw = _fetch_bilibili_video(suffix)
        elif media_format == MediaFormat.B_A:
            raw = _fetch_bilibili_article(suffix)
        elif media_format == MediaFormat.C_P:
            raw = _fetch_saolei_post(suffix)
        else:
            raise MediaFetchError('invalid_metadata', 502)
    except (KeyError, TypeError, IndexError, AttributeError):
        raise MediaFetchError('parse_error', 502) from None
    return _validate_metadata(*raw)


def fetch_media_metadata_optional(media_format, suffix):
    """外站不可用时降级投稿：返回 None 表示标题待管理员补全；结构性错误仍拒绝。"""
    try:
        return fetch_media_metadata(media_format, suffix)
    except MediaFetchError as exc:
        if exc.category in DEGRADED_FETCH_CATEGORIES:
            return None
        raise
