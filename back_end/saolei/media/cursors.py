"""作品列表的数值游标；不依赖模型或排行缓存。"""

from datetime import datetime, timedelta, timezone
from math import isfinite

from django.core import signing

CURSOR_SALT = 'media.works.cursor.v1'
SORT_FIELDS = {'hot': 'hot_value', 'likes': 'likes', 'latest': 'created_at', 'submitted': 'submitted_at'}
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def encode_cursor(sort, filters, value, media_id):
    if sort in ('latest', 'submitted'):
        delta = value - EPOCH
        value = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
    return signing.dumps({'v': 1, 'sort': sort, 'filters': filters, 'value': str(value), 'id': str(media_id)}, salt=CURSOR_SALT)


def decode_cursor(cursor, sort, filters):
    try:
        if len(cursor) > 2048:
            raise ValueError
        payload = signing.loads(cursor, salt=CURSOR_SALT)
        if not isinstance(payload, dict) or type(payload.get('v')) is not int or payload['v'] != 1:
            raise ValueError
        if payload.get('sort') != sort or payload.get('filters') != filters:
            raise ValueError('cursor_query_mismatch')
        value, media_id = payload['value'], payload['id']
        if not isinstance(value, str) or not isinstance(media_id, str) or not media_id.isascii() or not media_id.isdecimal():
            raise ValueError
        media_id = int(media_id)
        if not 1 <= media_id <= 2**63 - 1:
            raise ValueError
        if sort in ('latest', 'submitted'):
            value = EPOCH + timedelta(microseconds=int(value))
        elif sort == 'likes':
            if not value.isascii() or not value.isdecimal() or not 0 <= int(value) <= 2**64 - 1:
                raise ValueError
            value = int(value)
        else:
            value = float(value)
            if not isfinite(value) or value < 0:
                raise ValueError
        return value, media_id
    except (signing.BadSignature, KeyError, TypeError, ValueError, OverflowError) as exc:
        code = 'cursor_query_mismatch' if str(exc) == 'cursor_query_mismatch' else 'invalid_cursor'
        raise ValueError(code) from exc
