"""作品页后台任务：月度热度基准刷新与榜单缓存同步；见 MEDIA_PLAN.md 第 10 节。"""

from datetime import timedelta
import logging

from django.tasks import task, TaskResultStatus
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from . import cache

logger = logging.getLogger('media')

MEDIA_SYNC_MAX_ATTEMPTS = 8


class MediaCacheSyncError(RuntimeError):
    """缓存同步重试耗尽：DB 正确、Redis 可能滞后，需人工重跑同步或重启该失败任务。"""


def media_sync_retry_delay(attempt):
    """退避 5/10/20/40/60... 秒；累计约 315s，长于 300s 锁 TTL，能熬过陈旧锁。"""
    return timedelta(seconds=min(5 * 2 ** attempt, 60))


@task(priority=-1)
def task_refresh_media_hot_reference():
    """月度低频刷新，优先级低于日常请求。"""
    from .services import refresh_hot_reference  # 避免与 services -> tasks 形成模块级循环引用
    return refresh_hot_reference()


@task()
def task_sync_media_scores(media_id, author_id, attempt=0):
    """请求外同步四个 zset；与业务数据同事务入队，进程被杀也不会丢。

    缓存锁只在 worker / 管理命令之间竞争，不占请求预算。锁忙时非阻塞退出并延迟
    重排，避免 worker 被卡住，也避免持锁进程退出后留下的锁拖垮同步。重试耗尽后
    抛错，让 DBTaskResult 变成 FAILED：管理页、monitor 快照都能看到，也可一键重跑。
    DB 始终是事实来源，失败不代表数据丢失，只代表榜单可能滞后。
    """
    if cache.try_sync_media_scores(media_id, author_id):
        return True
    if attempt >= MEDIA_SYNC_MAX_ATTEMPTS:
        logger.error(
            'Media cache sync for #%s failed after %s attempts: cache lock unavailable; '
            'DB is authoritative, restart this task or run rebuild_media_rankings',
            media_id, attempt + 1,
        )
        raise MediaCacheSyncError(
            f'media #{media_id} cache sync blocked after {attempt + 1} attempts; '
            'DB is authoritative, restart this task or run rebuild_media_rankings',
        )
    task_sync_media_scores.using(run_after=timezone.now() + media_sync_retry_delay(attempt)).enqueue(
        media_id, author_id, attempt + 1,
    )
    return False


def enqueue_media_score_sync(media_id, author_id):
    """在业务 DB 事务内调用：任务行与红宝石扣除 / 审核状态一同提交或回滚。"""
    return task_sync_media_scores.enqueue(media_id, author_id)


def enqueue_media_hot_reference():
    """防堆积：已有 READY/RUNNING 的同任务时不再入队；作业失败可按幂等逻辑重跑。"""
    pending = DBTaskResult.objects.filter(
        task_path=task_refresh_media_hot_reference.module_path,
        status__in=[TaskResultStatus.READY, TaskResultStatus.RUNNING],
    )
    if pending.exists():
        return None
    return task_refresh_media_hot_reference.enqueue()
