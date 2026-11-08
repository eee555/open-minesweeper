"""作品页专有常量与纯函数：枚举、URL 前缀、衰减公式与 URL 解析；见 MEDIA_PLAN.md 第 3、5 节。"""

import re
from urllib.parse import urlsplit

from django.db import models

MEDIA_HOT_DAILY_RETENTION = 0.99
SECONDS_PER_DAY = 86400.0
MEDIA_LANGUAGE_MAX_LENGTH = 32


class MediaFormat(models.TextChoices):
    B_V = 'B_v', 'Bilibili video'
    B_A = 'B_a', 'Bilibili article'
    C_P = 'c_p', 'Saolei post'


class MediaStatus(models.TextChoices):
    PENDING = 'pending', 'Pending review'
    VERIFIED = 'verified', 'Verified'
    REJECTED = 'rejected', 'Rejected'


FORMAT_PREFIX = {
    MediaFormat.B_V: 'https://www.bilibili.com/video/',
    MediaFormat.B_A: 'https://www.bilibili.com/read/cv',
    MediaFormat.C_P: 'https://saolei.wang/bbs/',
}
FORMAT_PLATFORM = {
    MediaFormat.B_V: 'B',
    MediaFormat.B_A: 'B',
    MediaFormat.C_P: 'c',
}
BILIBILI_HOSTS = frozenset({'www.bilibili.com', 'bilibili.com', 'm.bilibili.com'})
SAOLEI_HOSTS = frozenset({'saolei.wang'})
SUFFIX_PATTERNS = {
    MediaFormat.B_V: re.compile(r'BV[0-9A-Za-z]{10}'),
    MediaFormat.B_A: re.compile(r'[0-9]+'),
    MediaFormat.C_P: re.compile(r'[0-9]+'),
}
EMBED_PREFIX = 'https://player.bilibili.com/player.html?bvid='
EMBED_SUFFIX = '&page=1&autoplay=0&danmaku=0'


def decay(start_time, end_time):
    """热度从 start_time 到 end_time 的连续指数衰减因子；负时间差会放大。"""
    elapsed_seconds = (end_time - start_time).total_seconds()
    return MEDIA_HOT_DAILY_RETENTION ** (elapsed_seconds / SECONDS_PER_DAY)


def real_hot(media, at_time):
    """以 at_time 为观察时刻的实时热度；media 只需提供两个热度字段。"""
    return media.hot_value * decay(media.hot_value_updated_at, at_time)


def normalize_language(value):
    """语言只做 strip 与长度校验，不限制内容（Q4）。"""
    normalized = (value or '').strip()
    if len(normalized) > MEDIA_LANGUAGE_MAX_LENGTH:
        raise ValueError('Language is too long')
    return normalized


def format_to_platform(media_format):
    platform = FORMAT_PLATFORM.get(media_format)
    if platform is None:
        raise ValueError('Unknown media format')
    return platform


def build_external_url(media_format, suffix):
    prefix = FORMAT_PREFIX.get(media_format)
    if prefix is None:
        raise ValueError('Unknown media format')
    trailing_slash = '/' if media_format == MediaFormat.B_V else ''
    return prefix + suffix + trailing_slash


def build_embed_url(media_format, suffix):
    if media_format == MediaFormat.B_V:
        return EMBED_PREFIX + suffix + EMBED_SUFFIX
    return None


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
    if media_format is None:
        if not SUFFIX_PATTERNS[MediaFormat.B_V].fullmatch(text):
            raise ValueError('Ambiguous media suffix')
        media_format = MediaFormat.B_V
    return _validate_suffix(media_format, text)


def _validate_suffix(media_format, suffix):
    pattern = SUFFIX_PATTERNS.get(media_format)
    if pattern is None or not pattern.fullmatch(suffix):
        raise ValueError('Invalid media suffix')
    return media_format, suffix
