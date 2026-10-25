import logging
import os
from pathlib import Path
import tempfile
import time
from urllib.parse import urlsplit

from django.conf import settings
from django.db import DatabaseError
from django.db.models import Sum
from django.tasks import TaskResultStatus
from django.utils import timezone
from django_tasks_db.models import DBTaskResult
import psutil
from pydantic import ValidationError
from redis.exceptions import RedisError

from config.text_choices import MS_TextChoices
from userprofile.models import UserProfile
from utils.db import get_choice_counts_filtered
from videomanager.models import VideoModel
from .cache import collect_redis_memory
from .schema import DiskUsageOut, MemoryUsageOut, MonitorSnapshotOut, TaskSummaryOut, VideoSummaryOut
from .server_metrics import check_deadline, collect_process_memory, COLLECTION_SECONDS, CollectionError, process_memory_metric
from .utils import get_db_size, get_snapshot_path

logger = logging.getLogger(__name__)


def publish_monitor_snapshot():
    path = get_snapshot_path()
    try:
        snapshot = MonitorSnapshotOut.model_validate_json(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        snapshot = MonitorSnapshotOut()
    except ValidationError:
        logger.warning('Discarding invalid monitor snapshot.')
        snapshot = MonitorSnapshotOut()

    for name, collector, schema in (
        ('videosummary', get_video_summary, VideoSummaryOut),
        ('tasksummary', get_task_summary, TaskSummaryOut),
        ('diskusage', get_disk_usage, DiskUsageOut),
        ('memoryusage', get_memory_usage, MemoryUsageOut),
    ):
        try:
            result = collector()
            if name != 'memoryusage':
                result['sampled_at'] = timezone.now()
            value = schema.model_validate(result)
            previous = getattr(snapshot, name)
            if name == 'memoryusage' and previous is not None:
                for section in ('memory', 'redis'):
                    if getattr(value, section).status != 'ready' and getattr(previous, section).status == 'ready':
                        setattr(value, section, getattr(previous, section))
            setattr(snapshot, name, value)
        except Exception:
            logger.exception('Monitor sampling failed: section=%s; keeping previous sample.', name)

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, prefix='.monitor-', suffix='.tmp', delete=False) as file:
            temporary_path = file.name
            file.write(snapshot.model_dump_json())
        os.chmod(temporary_path, 0o644)  # Nginx workers need read access to the published file.
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            Path(temporary_path).unlink(missing_ok=True)
    logger.info('Monitor snapshot published.')


def get_video_summary():
    total = VideoModel.objects.count()
    software = get_choice_counts_filtered(VideoModel, 'software', MS_TextChoices.Software)
    level = get_choice_counts_filtered(VideoModel, 'level', MS_TextChoices.Level)
    mode = get_choice_counts_filtered(VideoModel, 'mode', MS_TextChoices.Mode)
    state = get_choice_counts_filtered(VideoModel, 'state', MS_TextChoices.State)
    return {'total': total, 'software': software, 'level': level, 'mode': mode, 'state': state}


def get_task_summary():
    total = DBTaskResult.objects.count()
    status = get_choice_counts_filtered(DBTaskResult, 'status', TaskResultStatus)
    return {'total': total, 'status': status}


def get_disk_usage():
    disk = psutil.disk_usage('.')
    video_size = VideoModel.objects.aggregate(s=Sum('file_size'))['s']
    db_size = get_db_size()
    return {'total': disk.total, 'used': disk.used, 'free': disk.free, 'video': video_size, 'db': db_size}


def _player_ids(deadline):
    last_id = 0
    while True:
        check_deadline(deadline)
        batch = list(UserProfile.objects.filter(pk__gt=last_id).order_by('pk').values_list('pk', flat=True)[:1000])
        check_deadline(deadline)
        if not batch:
            return
        yield from batch
        last_id = batch[-1]


def _check_local_services():
    locations = settings.CACHES['saolei_website']['LOCATION']
    if isinstance(locations, str):
        locations = [locations]
    local_hosts = {'', 'localhost', '127.0.0.1', '::1'}
    for location in locations:
        url = urlsplit(location)
        if url.scheme != 'unix' and url.hostname not in local_hosts:
            raise CollectionError('unsupported_scope')
    mysql_host = settings.DATABASES['default'].get('HOST', '')
    if mysql_host not in local_hosts and not mysql_host.startswith('/'):
        raise CollectionError('unsupported_scope')


def get_memory_usage():
    deadline = time.monotonic() + COLLECTION_SECONDS
    result = {}
    for name in ('memory', 'redis'):
        try:
            if name == 'memory':
                _check_local_services()
                result[name] = collect_process_memory(settings.BASE_DIR, deadline)
            else:
                result[name] = collect_redis_memory(_player_ids(deadline), deadline)
            continue
        except CollectionError as error:
            reason = error.reason
            unreadable = error.unreadable_processes
        except psutil.AccessDenied:
            reason, unreadable = 'permission_denied', 1
        except RedisError:
            reason, unreadable = 'redis_unavailable', 0
        except DatabaseError:
            reason, unreadable = 'database_unavailable', 0
        except Exception as error:
            # Publish a safe error code, never process arguments or Redis key names.
            logger.warning('Memory collection failed: section=%s exception=%s', name, type(error).__name__)
            reason, unreadable = 'collection_failed', 0
        logger.warning('Memory section unavailable: section=%s reason=%s unreadable=%s', name, reason, unreadable)
        result[name] = {'status': 'unavailable', 'reason': reason, 'sampled_at': None, 'total_bytes': None, 'groups': None}
        if name == 'memory':
            result[name].update(metric=process_memory_metric(), host=None, unreadable_processes=unreadable)
        else:
            result[name].update(metric='redis_allocated', estimated=True, samples=5)
    return result
