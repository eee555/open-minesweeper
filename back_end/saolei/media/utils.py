"""作品页专有常量与纯函数：枚举、衰减公式与投稿 URL 解析。"""

import re
from urllib.parse import urlsplit

from django.db import models

MEDIA_HOT_DAILY_RETENTION = 0.99
SECONDS_PER_DAY = 86400.0
MEDIA_LANGUAGE_MAX_LENGTH = 32
MEDIA_AUTHOR_ID_MAX_LENGTH = 128
MEDIA_DAILY_LIKE_LIMIT = 10


class MediaFormat(models.TextChoices):
    B_V = 'B_v', 'Bilibili video'
    B_A = 'B_a', 'Bilibili article'
    C_P = 'c_p', 'Saolei post'
    G_R = 'g_r', 'GitHub repository'


class MediaStatus(models.TextChoices):
    PENDING = 'pending', 'Pending review'
    VERIFIED = 'verified', 'Verified'
    REJECTED = 'rejected', 'Rejected'


FORMAT_PLATFORM = {
    MediaFormat.B_V: 'B',
    MediaFormat.B_A: 'B',
    MediaFormat.C_P: 'c',
    MediaFormat.G_R: 'g',
}
BILIBILI_HOSTS = frozenset({'www.bilibili.com', 'bilibili.com', 'm.bilibili.com'})
SAOLEI_HOSTS = frozenset({'saolei.wang'})
SUFFIX_PATTERNS = {
    MediaFormat.B_V: re.compile(r'BV[0-9A-Za-z]{10}'),
    MediaFormat.B_A: re.compile(r'[0-9]+'),
    MediaFormat.C_P: re.compile(r'[0-9]+'),
}
# 数字 id 的前导零不代表不同作品，必须归一化后才能用 (format, suffix) 唯一约束防重复投稿。
NUMERIC_MEDIA_FORMATS = frozenset({MediaFormat.B_A, MediaFormat.C_P})
GITHUB_LOCATOR_PATTERN = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9_.-]{1,100}')


def decay(start_time, end_time):
    """热度从 start_time 到 end_time 的连续指数衰减因子；负时间差会放大。"""
    elapsed_seconds = (end_time - start_time).total_seconds()
    return MEDIA_HOT_DAILY_RETENTION ** (elapsed_seconds / SECONDS_PER_DAY)


def real_hot(media, at_time):
    """以 at_time 为观察时刻的实时热度；media 只需提供两个热度字段。"""
    return media.hot_value * decay(media.hot_value_updated_at, at_time)


def normalize_language(value):
    """语言只做 strip 与长度校验，不限制内容。"""
    normalized = (value or '').strip()
    if len(normalized) > MEDIA_LANGUAGE_MAX_LENGTH:
        raise ValueError('Language is too long')
    return normalized.lower() if normalized.lower() in ('zh-cn', 'en', 'es') else normalized


def default_media_language(media_format):
    return 'en' if format_to_platform(media_format) == 'g' else 'zh-cn'


def normalize_external_author_id(value):
    """外站作者 id 归一化为字符串，仅用于一次性归属核验，不写入 Media。"""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError('Invalid external author id')
    normalized = str(value).strip()
    if not normalized or len(normalized) > MEDIA_AUTHOR_ID_MAX_LENGTH:
        raise ValueError('Invalid external author id')
    return normalized


def format_to_platform(media_format):
    platform = FORMAT_PLATFORM.get(media_format)
    if platform is None:
        raise ValueError('Unknown media format')
    return platform


def parse_media_url(value, media_format=None):
    """把完整外链或规范化 suffix 解析为 (format, suffix)；非法输入抛 ValueError。"""
    text = (value or '').strip()
    if not text:
        raise ValueError('Empty media URL')
    if '://' in text:
        return _parse_full_url(text)
    return _parse_suffix(text, media_format)


def _parse_full_url(text):
    parts = urlsplit(text)
    host = (parts.hostname or '').lower()
    segments = [segment for segment in parts.path.split('/') if segment]
    if parts.username or parts.password or parts.port or parts.fragment:
        raise ValueError('Unexpected URL components')
    if host in BILIBILI_HOSTS:
        if parts.scheme not in ('http', 'https'):
            raise ValueError('Unexpected URL scheme')
        media_format, suffix = _bilibili_path(segments)
    elif host in SAOLEI_HOSTS:
        if parts.scheme != 'https' or len(segments) != 2 or segments[0] != 'bbs':
            raise ValueError('Unsupported Saolei URL')
        media_format, suffix = MediaFormat.C_P, segments[1]
    elif host == 'github.com':
        if parts.scheme != 'https' or parts.query or parts.netloc.lower() != 'github.com':
            raise ValueError('Unsupported GitHub URL')
        return MediaFormat.G_R, normalize_github_locator(parts.path.removeprefix('/').removesuffix('/'))
    else:
        raise ValueError('Unexpected media host')
    return _validate_suffix(media_format, suffix)


def _bilibili_path(segments):
    if len(segments) != 2:
        raise ValueError('Unsupported Bilibili path')
    if segments[0] == 'video':
        return MediaFormat.B_V, segments[1]
    if segments[0] == 'read' and segments[1].startswith('cv'):
        return MediaFormat.B_A, segments[1][2:]
    raise ValueError('Unsupported Bilibili path')


def _parse_suffix(text, media_format):
    if media_format == MediaFormat.G_R:
        return media_format, normalize_github_locator(text)
    if media_format is None:
        if not SUFFIX_PATTERNS[MediaFormat.B_V].fullmatch(text):
            raise ValueError('Ambiguous media suffix')
        media_format = MediaFormat.B_V
    return _validate_suffix(media_format, text)


def normalize_github_locator(value):
    """投稿只接受 owner/repo；落库使用详情 API 返回的数字仓库 ID。"""
    locator = value.removesuffix('.git')
    if not GITHUB_LOCATOR_PATTERN.fullmatch(locator) or locator.split('/')[1] in {'.', '..'}:
        raise ValueError('Invalid GitHub repository')
    return locator.lower()


def _validate_suffix(media_format, suffix):
    pattern = SUFFIX_PATTERNS.get(media_format)
    if pattern is None or not pattern.fullmatch(suffix):
        raise ValueError('Invalid media suffix')
    if media_format in NUMERIC_MEDIA_FORMATS:
        suffix = suffix.lstrip('0') or '0'
    return media_format, suffix
