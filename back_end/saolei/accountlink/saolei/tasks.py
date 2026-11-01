from collections import Counter
import logging

from django.db.models import Q
from django.tasks import task, TaskResultStatus
from django_tasks_db.models import DBTaskResult

from utils.exceptions import ExceptionToResponse
from videomanager.models import VideoModel
from .client import saolei_client
from .services import import_pending_saolei_videos, pending_saolei_videos, report_saolei_sync_failure

logger = logging.getLogger('accountlink')


@task(priority=-1)
def task_import_saolei_hourly():
    """每小时最多尝试 100 条已取得 URL 的录像，不再请求目录或 video_info。"""
    sources = pending_saolei_videos(ready=True).filter(user__auto_sync=True)
    if not sources.exists():
        return {}
    if VideoModel.objects.filter(Q(original_hash__isnull=True) | Q(original_hash='')).exists():
        raise ExceptionToResponse('saolei', 'missing_original_hash', 409)
    counts = Counter()
    with saolei_client() as client:
        import_pending_saolei_videos(sources, client, counts=counts, report_failure=report_saolei_sync_failure, limit=100, automatic=True)
    logger.info('扫雷网每小时录像导入完成：%s', dict(counts))
    if counts['failed']:
        raise ExceptionToResponse('saolei', 'partial_sync', 500)
    return dict(counts)


def enqueue_saolei_hourly_import():
    """调度器是唯一生产者，上一轮仍排队或运行时不再堆积每小时任务。"""
    if not DBTaskResult.objects.filter(
        task_path=task_import_saolei_hourly.module_path, status__in=[TaskResultStatus.READY, TaskResultStatus.RUNNING],
    ).exists():
        task_import_saolei_hourly.enqueue()
