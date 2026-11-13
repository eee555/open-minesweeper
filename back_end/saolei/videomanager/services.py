from datetime import datetime, timezone as dt_timezone
import errno
from io import BytesIO
import json
import logging
import math
from pathlib import PurePosixPath
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django_apscheduler import util

from config.text_choices import MS_TextChoices
from utils.ranking_lock import ranking_access
from .cache import newest_cache
from .config import TARGET_COMPRESSION_FORMAT
from .events import video_storage_changed
from .files import compress_original, original_file, validate_compression_target
from .models import ExpandVideoModel, STNB_COEFFICIENTS, VideoModel
from .utils import calculate_original_hash, pack_compression_format, replay_filename, VIDEO_QUERY_DATETIME_FIELDS, VIDEO_QUERY_ENUM_FIELDS, VIDEO_QUERY_FILTER_FIELDS, VIDEO_QUERY_FLOAT_FIELDS, VIDEO_QUERY_INT_FIELDS, VIDEO_QUERY_LIMIT, VIDEO_QUERY_LOOKUPS, VIDEO_QUERY_LOWER_OPS, VIDEO_QUERY_MAX_IN_VALUES, VIDEO_QUERY_MAX_VALUE_LENGTH, VIDEO_QUERY_OPS, VIDEO_QUERY_SORT_FIELDS, VIDEO_QUERY_STNB_LEVELS, VIDEO_QUERY_UPPER_OPS, VideoQueryError

logger = logging.getLogger('videomanager')


@ranking_access(operation='videomanager.freeze_video')
@transaction.atomic
def freeze_video_by_id(video_id: int, freeze_reason: str, *, actor_id: int):
    reason = freeze_reason.strip()
    if not reason:
        raise ValueError('Freeze reason is required.')
    video = VideoModel.objects.select_for_update().get(pk=video_id)
    expansion = ExpandVideoModel.objects.select_for_update().get(pk=video.video_id)
    expansion.freeze_reason = reason
    expansion.save(update_fields=['freeze_reason'])
    previous_state = video.state
    if video.state != MS_TextChoices.State.FROZEN:
        video.state = MS_TextChoices.State.FROZEN
        video.save(update_fields=['state'])
    logger.info('Staff #%s froze video #%s (previous_state=%s)', actor_id, video_id, previous_state)
    return {'id': video.pk, 'state': video.state, 'freeze_reason': expansion.freeze_reason}


@ranking_access(operation='videomanager.delete_video')
@transaction.atomic
def delete_video_by_id(video_id: int, *, actor_id: int):
    video = VideoModel.objects.select_for_update().filter(pk=video_id).first()
    if video is None:
        return {'id': video_id, 'deleted': False, 'affected_tournament_ids': []}
    tournament_ids = list(video.tournaments.order_by('pk').values_list('pk', flat=True))
    if tournament_ids:
        logger.warning('Superuser #%s requested tournament video deletion: video_id=%s tournament_ids=%s; saved results are not recalculated', actor_id, video_id, tournament_ids)
    video.delete()
    logger.info('Superuser #%s deleted video #%s', actor_id, video_id)
    return {'id': video_id, 'deleted': True, 'affected_tournament_ids': tournament_ids}


def find_identical_video(original_hash: str):
    return VideoModel.objects.filter(original_hash=original_hash).first()


def _delete_unreferenced_file(file_name):
    if not VideoModel.objects.filter(file=file_name).exists():
        try:
            default_storage.delete(file_name)
        except OSError:
            logger.exception('Failed to remove unreferenced replay: %s', file_name)


def compress_video_file(video, *, target=TARGET_COMPRESSION_FORMAT, retry_failed=False):
    """转换独立文件，校验后短事务切换，并同步存储空间统计。"""
    validate_compression_target(target)
    target_code = pack_compression_format(*target)
    if not retry_failed and (video.compression_failed or video.compression_format == target_code):
        return 'skipped'
    source_name = video.file.name
    current = VideoModel.objects.filter(pk=video.pk, file=source_name, compression_format=video.compression_format)
    archive_name = None
    try:
        with original_file(source_name, video.compression_format, video.original_filename) as source:
            raw = source.read()
        if len(raw) != video.file_size:
            raise ValueError('Original replay size differs from file_size')
        if video.original_hash and calculate_original_hash(BytesIO(raw)) != video.original_hash:
            raise ValueError('Original replay hash differs from original_hash')
        archive, actual_format = compress_original(raw, target)
        archive_name = str(PurePosixPath(source_name).parent / f'{uuid4().hex}.msrc')
        archive_name = default_storage.save(archive_name, ContentFile(archive))  # noqa: DJM100
        with default_storage.open(archive_name, 'rb') as saved:
            if saved.read() != archive:
                raise ValueError('Stored archive differs from validated archive')
    except (OSError, ValueError, EOFError) as error:
        if archive_name:
            _delete_unreferenced_file(archive_name)
        if isinstance(error, OSError) and error.errno in (errno.ENOSPC, errno.EROFS, errno.EACCES):
            raise
        changed = current.update(compression_failed=True)
        logger.warning('Replay compression failed: id=%s source=%s target=%s error=%s', video.pk, source_name, target, error)
        return 'failed' if changed else 'skipped'
    # A database failure can leave the commit result unknown. Keep both files for recovery.
    with transaction.atomic():
        previous = current.select_for_update().values('stored_file_size', 'file_size').first()
        changed = previous is not None and current.update(
            file=archive_name, original_filename=replay_filename(source_name, video.original_filename),
            stored_file_size=len(archive), compression_format=actual_format, compression_failed=False,
        )
        if changed:
            old_size = previous['stored_file_size'] if previous['stored_file_size'] is not None else previous['file_size']
            video_storage_changed.send(sender=VideoModel, video_id=video.pk, size_delta=len(archive) - old_size, using=current.db)
            transaction.on_commit(lambda: _delete_unreferenced_file(source_name))
    if not changed:
        _delete_unreferenced_file(archive_name)
        return 'skipped'
    logger.info('Replay compressed: id=%s target=%s original=%s stored=%s', video.pk, target, len(raw), len(archive))
    return 'converted'


def set_import_upload_time(video: VideoModel, upload_time: datetime | None, *, created=False):
    """新录像覆盖 auto_now_add；重复录像只保留更早的时间，并触发保存信号。"""
    if upload_time is not None and (created or upload_time < video.upload_time):
        video.upload_time = upload_time
        video.save(update_fields=['upload_time'])


@util.close_old_connections
def delete_newest_queue():
    return newest_cache.trim()


def _query_value(field, value):
    if isinstance(value, str) and len(value) > VIDEO_QUERY_MAX_VALUE_LENGTH:
        raise VideoQueryError(f'Value for {field} is too long.')
    if field in VIDEO_QUERY_DATETIME_FIELDS:
        if not isinstance(value, str):
            raise VideoQueryError(f'Invalid datetime for {field}.')
        parsed = parse_datetime(value)
        if parsed is None:
            raise VideoQueryError(f'Invalid datetime for {field}.')
        return timezone.make_aware(parsed, dt_timezone.utc) if timezone.is_naive(parsed) else parsed
    if field in VIDEO_QUERY_ENUM_FIELDS:
        allowed = {
            'state': MS_TextChoices.State.values,
            'software': MS_TextChoices.Software.values,
            'level': MS_TextChoices.Level.values,
            'mode': MS_TextChoices.Mode.values,
        }[field]
        if not isinstance(value, str) or value not in allowed:
            raise VideoQueryError(f'Invalid enum value for {field}.')
        return value
    if isinstance(value, bool):
        raise VideoQueryError(f'Invalid number for {field}.')
    try:
        number = int(value) if field in VIDEO_QUERY_INT_FIELDS else float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise VideoQueryError(f'Invalid number for {field}.') from exc
    if field in VIDEO_QUERY_FLOAT_FIELDS and not math.isfinite(number):
        raise VideoQueryError(f'Invalid number for {field}.')
    return number


def _parse_filters(raw):
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise VideoQueryError('Invalid filters JSON.') from exc
    if not isinstance(data, list):
        raise VideoQueryError('filters must be a list.')
    result = []
    seen = set()
    for item in data:
        if not isinstance(item, dict):
            raise VideoQueryError('Each filter must be an object.')
        field = item.get('field')
        if field not in VIDEO_QUERY_FILTER_FIELDS:
            raise VideoQueryError('Unknown filter field.')
        if field in seen:
            raise VideoQueryError('Each field may appear at most once.')
        seen.add(field)
        ops = {key: value for key, value in item.items() if key != 'field'}
        if not ops or set(ops) - VIDEO_QUERY_OPS:
            raise VideoQueryError('Invalid filter operator.')
        if len(set(ops) & VIDEO_QUERY_LOWER_OPS) > 1 or len(set(ops) & VIDEO_QUERY_UPPER_OPS) > 1:
            raise VideoQueryError('Conflicting range operators.')
        if 'eq' in ops and 'in' in ops:
            raise VideoQueryError('Equality operators cannot be combined.')
        if ('eq' in ops or 'in' in ops) and set(ops) & (VIDEO_QUERY_LOWER_OPS | VIDEO_QUERY_UPPER_OPS):
            raise VideoQueryError('Equality and range operators cannot be combined.')
        normalized = {'field': field}
        for op, value in ops.items():
            if op == 'in':
                if not isinstance(value, list) or len(value) > VIDEO_QUERY_MAX_IN_VALUES:
                    raise VideoQueryError('Invalid in values.')
                normalized[op] = [_query_value(field, entry) for entry in value]
            else:
                normalized[op] = _query_value(field, value)
        result.append(normalized)
    return result


def _parse_sorts(raw):
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise VideoQueryError('Invalid sorts JSON.') from exc
    if not isinstance(data, list):
        raise VideoQueryError('sorts must be a list.')
    result = []
    seen = set()
    for item in data:
        if not isinstance(item, dict):
            raise VideoQueryError('Each sort must be an object.')
        field = item.get('field')
        direction = item.get('direction', 'asc')
        if field not in VIDEO_QUERY_SORT_FIELDS:
            raise VideoQueryError('Unknown sort field.')
        if field in seen:
            raise VideoQueryError('Each field may appear at most once.')
        if direction not in ('asc', 'desc'):
            raise VideoQueryError('Invalid sort direction.')
        seen.add(field)
        result.append((field, direction))
    return result


def _level_coefficient(filters):
    for condition in filters:
        if condition['field'] != 'level':
            continue
        values = [condition['eq']] if 'eq' in condition else condition.get('in', [])
        if len(values) == 1 and values[0] in VIDEO_QUERY_STNB_LEVELS:
            return STNB_COEFFICIENTS[values[0]]
        return None
    return None


def query_videos(base_qs, filters_json, sorts_json):
    """Validate and apply filters/sorts, returning at most VIDEO_QUERY_LIMIT website metadata rows."""
    filters = _parse_filters(filters_json)
    sorts = _parse_sorts(sorts_json)
    coefficient = _level_coefficient(filters)
    uses_stnb = any(item['field'] == 'stnb' for item in filters) or any(field == 'stnb' for field, _ in sorts)
    if uses_stnb and coefficient is None:
        raise VideoQueryError('stnb requires exactly one b/i/e level filter.')
    lookups = {}
    for condition in filters:
        field = condition['field']
        mapped = 'iqg' if field == 'stnb' else field
        for op, value in condition.items():
            if op == 'field':
                continue
            if field == 'stnb':
                value = [entry / coefficient for entry in value] if op == 'in' else value / coefficient
            lookups[f'{mapped}__{VIDEO_QUERY_LOOKUPS[op]}'] = value
    order = [('-' if direction == 'desc' else '') + ('iqg' if field == 'stnb' else field) for field, direction in sorts]
    if not any(field == 'id' for field, _ in sorts):
        order.append('id')
    return list(base_qs.filter(**lookups).order_by(*order).values('id', 'upload_time', 'state', 'ongoing_tournament', 'player_id')[:VIDEO_QUERY_LIMIT])
