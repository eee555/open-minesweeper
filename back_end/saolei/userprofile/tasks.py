"""玩家认证后台任务：级联写入不占用 HTTP 请求时间。"""

import logging
from time import monotonic, sleep

from django.db import close_old_connections
from django.tasks import task, TaskContext, TaskResultStatus
from django_tasks_db.models import DBTaskResult

from .verification.services import execute_verification_operation, task_kwargs
from .verification.utils import ORDER_WAIT_SECONDS, VERIFICATION_TASK_PATH

logger = logging.getLogger('userprofile')


def wait_for_earlier_tasks(task_id: str, sequence: int):
    """按受理顺序串行落地；worker 停止遗留的失败任务不在 READY/RUNNING 中，不会永久阻塞。"""
    deadline = monotonic() + ORDER_WAIT_SECONDS
    while True:
        earlier = False
        for row in DBTaskResult.objects.filter(task_path=VERIFICATION_TASK_PATH, status__in=[TaskResultStatus.READY, TaskResultStatus.RUNNING]):
            if str(row.id) == task_id:
                continue
            other = task_kwargs(row).get('sequence')
            if isinstance(other, int) and 0 < other < sequence:
                earlier = True
                break
        if not earlier:
            return
        if monotonic() >= deadline:
            logger.warning('Verification task %s seq=%s proceeded after waiting for earlier tasks', task_id, sequence)
            return
        close_old_connections()
        sleep(0.2)


@task(takes_context=True)
def task_apply_verification(context: TaskContext, *, operation: str, actor_id: int, target_id: int,
                            expected_parent_id: int | None, expected_created_at: str | None,
                            expected_verified: bool, accepted_at: str, sequence: int):
    """执行一次已授权的认证写命令；树与用户状态在同一事务内完整提交。"""
    task_id = str(context.task_result.id)
    wait_for_earlier_tasks(task_id, sequence)
    return execute_verification_operation(
        task_id, operation=operation, actor_id=actor_id, target_id=target_id,
        expected_parent_id=expected_parent_id, expected_created_at=expected_created_at,
        expected_verified=expected_verified, accepted_at=accepted_at, sequence=sequence,
    )
