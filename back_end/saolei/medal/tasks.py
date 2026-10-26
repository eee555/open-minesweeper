from django.db import transaction
from django.tasks import task, TaskResultStatus
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from userprofile.models import UserProfile
from .services import evaluate_player, refresh_player_medals
from .utils import REFRESH_COALESCE_DELAY


@task(priority=1)
def task_refresh_player_medals(user_id: int, video_ids=None, degrade_levels=None, invalidate_once=False, full=False):
    """重算该玩家已经接上的勋章。同一条任务覆盖这一名玩家。"""
    refresh_player_medals(
        user_id, video_ids=video_ids, degrade_levels=degrade_levels, invalidate_once=invalidate_once, full=full,
    )
    return user_id


def enqueue_player_refresh(user_id, video_ids=None, degrade_levels=None, invalidate_once=False, full=False):
    """同一玩家合并 READY 刷新；新任务延迟 3 秒，合并不推迟原时间，异常过晚的时间提前到当前延迟上限。"""
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
    """同一玩家已有一条 READY 的补发任务时不再插入。"""
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


def _enqueue_player_task(player_task, user_id, defer=False, **kwargs):
    # Serialize producers for this player, including the empty-queue case.
    run_after = timezone.now() + REFRESH_COALESCE_DELAY if defer else timezone.now()
    with transaction.atomic():
        if not UserProfile.objects.select_for_update().filter(pk=user_id).exists():
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
