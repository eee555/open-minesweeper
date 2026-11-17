from contextlib import contextmanager
import logging

from django.db import connection, DatabaseError, transaction
from django.tasks import task, TaskResultStatus
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from userprofile.models import UserProfile
from .services import evaluate_player, refresh_player_medals
from .utils import QUEUE_LOCK_TIMEOUT, REFRESH_COALESCE_DELAY

logger = logging.getLogger(__name__)


@task(priority=1)
def task_refresh_player_medals(user_id: int, video_ids=None, degrade_levels=None, invalidate_once=False, full=False):
    """重算该玩家已经接上的勋章。同一条任务覆盖这一名玩家。"""
    refresh_player_medals(
        user_id, video_ids=video_ids, degrade_levels=degrade_levels, invalidate_once=invalidate_once, full=full,
    )
    return user_id


def enqueue_player_refresh(user_id, video_ids=None, degrade_levels=None, invalidate_once=False, full=False):
    """
    同一玩家合并 READY 刷新；新任务延迟 3 秒，合并不推迟原时间，异常过晚的时间提前到当前延迟上限。
    不能在事务内直接调用（入队事务为 durable，会抛 RuntimeError）；业务事务内须经 transaction.on_commit 调用。
    """
    ids = sorted({int(video_id) for video_id in (video_ids or []) if video_id is not None})
    levels = sorted({level for level in (degrade_levels or []) if level})
    if full or not (ids or levels or invalidate_once):
        return _enqueue_player_task(task_refresh_player_medals, user_id, defer=True, full=True)
    kwargs = {'video_ids': ids}
    if levels:
        kwargs['degrade_levels'] = levels
    if invalidate_once:
        kwargs['invalidate_once'] = True
    return _enqueue_player_task(task_refresh_player_medals, user_id, defer=True, **kwargs)


@task(priority=0)
def task_backfill_player_medals(user_id: int):
    """按当前规则补发这一名玩家。优先级低于上传后的刷新。"""
    evaluate_player(user_id)
    return user_id


def enqueue_player_backfill(user_id: int):
    """
    同一玩家已有一条 READY 的补发任务时不再插入。
    不能在事务内直接调用（入队事务为 durable，会抛 RuntimeError）；业务事务内须经 transaction.on_commit 调用。
    """
    return _enqueue_player_task(task_backfill_player_medals, user_id)


def player_refresh_pending(user_id: int):
    """只检查当前玩家的未完成任务，不触发入队或勋章计算。"""
    return DBTaskResult.objects.filter(
        task_path__in=[task_refresh_player_medals.module_path, task_backfill_player_medals.module_path],
        status__in=[TaskResultStatus.READY, TaskResultStatus.RUNNING], args_kwargs__args=[user_id],
    ).exists()


def _merge_refresh_kwargs(row, incoming):
    current = dict((row.args_kwargs or {}).get('kwargs') or {})
    if current.get('full') or incoming.get('full'):
        merged = {'full': True}
    else:
        merged = {
            'video_ids': sorted(set(current.get('video_ids') or []) | set(incoming.get('video_ids') or [])),
            'degrade_levels': sorted(set(current.get('degrade_levels') or []) | set(incoming.get('degrade_levels') or [])),
        }
        if current.get('invalidate_once') or incoming.get('invalidate_once'):
            merged['invalidate_once'] = True
        merged = {key: value for key, value in merged.items() if value not in (None, [], False)}
    if merged == current:
        return []
    row.args_kwargs = {'args': list((row.args_kwargs or {}).get('args') or []), 'kwargs': merged}
    return ['args_kwargs']


def _uses_named_lock():
    return connection.vendor == 'mysql'


def _queue_lock_name(user_id):
    # 命名锁是 MySQL 实例级的，加库名避免同一实例上的多个库互相等待；MySQL 锁名上限 64 字符，截断只会落在库名上。
    return f'medal-queue:{user_id}:{connection.settings_dict["NAME"]}'[:64]


def _release_queue_lock(name):
    """释放失败时关闭连接：持久连接上遗留的会话锁会让后续入队白等超时。"""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT RELEASE_LOCK(%s)', [name])
            released = cursor.fetchone()[0] == 1
    except DatabaseError:
        released = False
    if not released:
        logger.warning('Medal queue lock %s was not released; closing the connection.', name)
        connection.close()


@contextmanager
def _queue_lock(user_id):
    """
    同一玩家的入队串行化。不锁玩家行，评估任务整轮持有该行锁。命名锁按会话持有，须在入队事务提交后释放。
    只有 MySQL 使用命名锁；其他数据库由入队事务锁玩家行串行化。
    """
    if not _uses_named_lock():
        yield
        return
    name = _queue_lock_name(user_id)
    with connection.cursor() as cursor:
        cursor.execute('SELECT GET_LOCK(%s, %s)', [name, QUEUE_LOCK_TIMEOUT])
        acquired = cursor.fetchone()[0] == 1
    if not acquired:
        logger.warning('Medal queue lock %s was not acquired within %s seconds; enqueueing anyway.', name, QUEUE_LOCK_TIMEOUT)
    try:
        # 拿不到锁也照常入队：重复任务只会多算一次，丢任务则勋章不更新。
        yield
    finally:
        if acquired:
            _release_queue_lock(name)


def _enqueue_player_task(player_task, user_id, defer=False, **kwargs):
    run_after = timezone.now() + REFRESH_COALESCE_DELAY if defer else timezone.now()
    players = UserProfile.objects.filter(pk=user_id)
    if not _uses_named_lock():
        players = players.select_for_update()
    # durable：嵌在外层事务里时命名锁会早于提交释放，直接报错，调用方应改用 on_commit。
    with _queue_lock(user_id), transaction.atomic(durable=True):
        if not players.exists():
            return None
        ready = DBTaskResult.objects.filter(
            task_path=player_task.module_path, status=TaskResultStatus.READY, args_kwargs__args=[user_id],
        )
        if ready.exists():
            row = DBTaskResult.objects.select_for_update().filter(
                task_path=player_task.module_path, status=TaskResultStatus.READY, args_kwargs__args=[user_id],
            ).first()
            if row is not None:
                changed = _merge_refresh_kwargs(row, kwargs) if kwargs else []
                if row.run_after is not None and row.run_after > run_after:
                    row.run_after = run_after
                    changed.append('run_after')
                if changed:
                    row.save(update_fields=changed)
                return None
            # Worker 可以在 exists() 后领取任务；已运行的任务不再可合并，必须另排一次。
        queued = player_task.using(run_after=run_after) if defer else player_task
        if kwargs:
            return queued.enqueue(user_id, **kwargs)
        return queued.enqueue(user_id)
