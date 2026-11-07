from collections import Counter
import logging

from django.db.models import Q
from django.tasks import task, TaskResultStatus
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from utils.exceptions import ExceptionToResponse
from videomanager.models import VideoModel
from .client import saolei_client
from .services import import_pending_saolei_videos, pending_saolei_videos, report_saolei_sync_failure, sync_saolei_metadata
from ..models import AccountSaolei

logger = logging.getLogger('accountlink')


@task(priority=-1)
def task_import_saolei_hourly():
    """每小时最多尝试 100 条已取得 URL 的录像，失败的来源不再自动重试；不再请求目录或 video_info。"""
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


@task(priority=-1)
def task_saolei_initial_full_sync(account_id: int):
    """绑定审核通过后的一次性全量同步：目录从 0 扫到当前上界并集中补取详情，文件导入仍由每小时任务消化。

    以 initial_sync_at 原子占坑保证每个绑定生命周期只自动执行一次（绑定审核接口重试、重复入队或每日
    兜底产生的并发任务都只会放行首个执行者）；绑定失效时目录阶段自行报错终止，资料与游标已有进度保留，
    修复绑定后每日增量调度会从保存的游标继续完成等价的目录同步。
    """
    account = AccountSaolei.objects.filter(pk=account_id).first()
    if account is None:
        return {}
    if not AccountSaolei.objects.filter(pk=account.pk, initial_sync_at__isnull=True).update(initial_sync_at=timezone.now()):
        return {}
    counts = Counter()
    with saolei_client() as client:
        upper_bound = client.stats().max_video_id
        sync_saolei_metadata(account, client, upper_bound=upper_bound, counts=counts, report_failure=report_saolei_sync_failure, full=True)
    logger.info('扫雷网账号#%s 绑定后全量同步完成：%s', account_id, dict(counts))
    return dict(counts)


def enqueue_saolei_initial_sync(account_id: int):
    """绑定成功后入队一次性全量同步；入队失败不撤销已提交的绑定，由每日兜底调度补队。"""
    try:
        task_saolei_initial_full_sync.enqueue(account_id)
    except Exception:
        logger.exception('扫雷网账号#%s 初始全量同步入队失败，将由每日兜底调度补队', account_id)


def enqueue_missing_initial_sync():
    """每日兜底：为 initial_sync_at 仍为空的在管账号补队（覆盖功能上线前的存量绑定与入队失败场景）。

    任务内以 initial_sync_at 原子占坑，重复入队的任务会立即退出，无需按任务状态查重。
    """
    pending = AccountSaolei.objects.filter(initial_sync_at__isnull=True, auto_sync=True).order_by('pk').values_list('pk', flat=True)
    for account_id in list(pending):
        enqueue_saolei_initial_sync(account_id)


def enqueue_saolei_hourly_import():
    """调度器是唯一生产者，上一轮仍排队或运行时不再堆积每小时任务。"""
    if not DBTaskResult.objects.filter(
        task_path=task_import_saolei_hourly.module_path, status__in=[TaskResultStatus.READY, TaskResultStatus.RUNNING],
    ).exists():
        task_import_saolei_hourly.enqueue()
