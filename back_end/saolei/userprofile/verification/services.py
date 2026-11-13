"""玩家认证的业务逻辑：短事务受理与后台任务执行。

所有改动认证树或 ``UserProfile.verified`` 的写入都先锁定同一协调行。
短 API 用 ``skip_locked`` 快速返回「处理中」，后台任务用阻塞锁串行执行，
两者不会在级联遍历期间并发加边或换根。
"""

from contextlib import contextmanager
from datetime import timedelta
import logging

from django.db import transaction
from django.tasks import TaskResultStatus
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django_tasks_db.models import DBTaskResult

from userprofile.models import UserProfile, UserVerifyCoordinator, UserVerifyTree
from userprofile.utils import has_identity_access
from utils.exceptions import ExceptionToResponse
from .utils import (APPLIED_TASK_LIMIT, COORDINATOR_ID, OPERATION_APPROVE, OPERATION_DETACH, OPERATION_GRANT,
                    OPERATIONS, REQUEST_WINDOW_HOURS, VERIFICATION_TASK_PATH)

logger = logging.getLogger('userprofile')
WINDOW = timedelta(hours=REQUEST_WINDOW_HOURS)


def verification_error(category: str, status_code: int = 409):
    return ExceptionToResponse('verification', category, status_code=status_code)


def task_kwargs(row: DBTaskResult) -> dict:
    args_kwargs = row.args_kwargs if isinstance(row.args_kwargs, dict) else {}
    kwargs = args_kwargs.get('kwargs')
    return kwargs if isinstance(kwargs, dict) else {}


def pending_tasks():
    return DBTaskResult.objects.filter(task_path=VERIFICATION_TASK_PATH, status__in=[TaskResultStatus.READY, TaskResultStatus.RUNNING])


def find_pending_task(target_id: int):
    for row in pending_tasks():
        if task_kwargs(row).get('target_id') == target_id:
            return row
    return None


def find_submitted_task(user_id: int):
    for row in pending_tasks():
        if task_kwargs(row).get('actor_id') == user_id:
            return row
    return None


def _lock_coordinator(skip_locked: bool):
    UserVerifyCoordinator.objects.get_or_create(pk=COORDINATOR_ID)
    queryset = UserVerifyCoordinator.objects.select_for_update(skip_locked=skip_locked)
    return queryset.filter(pk=COORDINATOR_ID).first()


@contextmanager
def short_coordination():
    """短 API 写入使用的协调锁；正在执行的长事务会让本次请求立即返回处理中。"""
    with transaction.atomic():
        coordinator = _lock_coordinator(skip_locked=True)
        if coordinator is None:
            raise verification_error('processing')
        yield coordinator


def _lock_user(user_id: int):
    return UserProfile.objects.select_for_update().filter(pk=user_id).first()


def _node_version(node):
    if node is None:
        return None, None, False
    return node.parent_id, node.created_at.isoformat(), node.verified


def _effective_subtree(root_id: int) -> set[int]:
    """沿已批准的入边遍历后代；待批准申请不算有效边，visited 同时防止脏数据成环。"""
    visited = {root_id}
    frontier = [root_id]
    while frontier:
        children = []
        for user_id in UserVerifyTree.objects.filter(parent_id__in=frontier, verified=True).values_list('user_id', flat=True):
            if user_id not in visited:
                visited.add(user_id)
                children.append(user_id)
        frontier = children
    return visited


def _set_subtree_verification(target_id: int, value: bool) -> int:
    user_ids = _effective_subtree(target_id)
    UserProfile.objects.filter(pk__in=user_ids).update(verified=value, date_updated=timezone.now())
    return len(user_ids)


def _write_node(target_id: int, *, parent_id, verified: bool, created_at):
    node, created = UserVerifyTree.objects.get_or_create(
        user_id=target_id,
        defaults={'parent_id': parent_id, 'verified': verified, 'created_at': created_at},
    )
    if not created:
        node.parent_id = parent_id
        node.verified = verified
        node.created_at = created_at
        node.save(update_fields=['parent', 'verified', 'created_at'])
    return node


def read_verification_status(user: UserProfile) -> dict:
    """只读取当前节点与本人已提交的任务，不在 GET 中写库，不展示认证来源。"""
    node = UserVerifyTree.objects.filter(user_id=user.pk).first()
    now = timezone.now()
    expires_at = node.created_at + WINDOW if node is not None and not node.verified else None
    has_relation = node is not None and node.parent_id is not None and node.verified
    in_cooldown = expires_at is not None and now < expires_at
    if node is None:
        state = 'none'
    elif node.verified and node.parent_id is None:
        state = 'verified_root'
    elif node.verified:
        state = 'approved'
    elif in_cooldown:
        state = 'pending' if node.parent_id is not None else 'rejected'
    else:
        state = 'expired' if node.parent_id is not None else 'unverified_root'
    processing = find_submitted_task(user.pk)
    return {
        'verified': user.verified,
        'can_submit_replays': has_identity_access(user),
        'has_relation': has_relation,
        'request_state': state,
        'request_parent_id': node.parent_id if state in ('pending', 'expired') else None,
        'created_at': node.created_at if node is not None else None,
        'expires_at': expires_at,
        'cooldown_until': expires_at if in_cooldown else None,
        'can_request': node is None or (not node.verified and not in_cooldown),
        'processing_task_id': str(processing.id) if processing is not None else None,
    }


def _ensure_no_pending(target_id: int):
    if find_pending_task(target_id) is not None:
        raise verification_error('processing')


def _check_request_writes(target_id: int):
    """申请、过期替换与拒绝共用的短检查，由调用方的协调锁事务包裹。"""
    _ensure_no_pending(target_id)
    return _lock_user(target_id)


def create_request(actor_id: int, parent_id: int) -> dict:
    """创建申请；过期未批准的当前节点在本事务内删除后重建。"""
    with short_coordination():
        if _check_request_writes(actor_id) is None:
            raise verification_error('not_found', status_code=404)
        if parent_id == actor_id:
            raise verification_error('self_request', status_code=400)
        if not UserProfile.objects.filter(pk=parent_id).exists():
            raise verification_error('not_found', status_code=404)
        if parent_id in _effective_subtree(actor_id):
            raise verification_error('cycle')
        now = timezone.now()
        node = UserVerifyTree.objects.filter(user_id=actor_id).first()
        if node is not None:
            if node.verified:
                raise verification_error('existing_relation')
            if now < node.created_at + WINDOW:
                raise verification_error('cooldown')
            node.delete()
        UserVerifyTree.objects.create(user_id=actor_id, parent_id=parent_id, created_at=now, verified=False)
        logger.info('User #%s requested verification from #%s', actor_id, parent_id)
        return read_verification_status(UserProfile.objects.get(pk=actor_id))


def reject_request(actor_id: int, applicant_id: int):
    """指定收件人拒绝未批准申请，保留 created_at 以延续七天冷却。"""
    with short_coordination():
        if _check_request_writes(applicant_id) is None:
            raise verification_error('not_found', status_code=404)
        node = UserVerifyTree.objects.filter(user_id=applicant_id).first()
        if node is None or node.verified or node.parent_id != actor_id:
            raise verification_error('not_found', status_code=404)
        node.parent_id = None
        node.save(update_fields=['parent'])
        logger.info('User #%s rejected verification request from #%s', actor_id, applicant_id)


def _dedupe_or_submit(task, coordinator, *, operation: str, actor_id: int, target_id: int,
                      expected_parent_id, expected_created_at, expected_verified: bool, accepted_at):
    pending = find_pending_task(target_id)
    kwargs = task_kwargs(pending) if pending is not None else {}
    if pending is not None:
        if kwargs.get('operation') == operation and kwargs.get('actor_id') == actor_id:
            return str(pending.id), True
        raise verification_error('processing')
    coordinator.sequence += 1
    coordinator.save(update_fields=['sequence'])
    result = task.enqueue(
        operation=operation, actor_id=actor_id, target_id=target_id,
        expected_parent_id=expected_parent_id, expected_created_at=expected_created_at,
        expected_verified=expected_verified, accepted_at=accepted_at,
        sequence=coordinator.sequence,
    )
    logger.info('Verification task %s submitted: %s by #%s on #%s', result.db_result.id, operation, actor_id, target_id)
    return str(result.db_result.id), False


def submit_approval(task, actor_id: int, applicant_id: int):
    """按申请人 ID 受理批准；服务端核对当前申请版本与七天受理期限。"""
    with short_coordination() as coordinator:
        if _lock_user(applicant_id) is None:
            raise verification_error('not_found', status_code=404)
        node = UserVerifyTree.objects.filter(user_id=applicant_id).first()
        if node is None or node.verified or node.parent_id != actor_id:
            raise verification_error('not_found', status_code=404)
        accepted_at = timezone.now()
        if accepted_at >= node.created_at + WINDOW:
            raise verification_error('expired')
        version = _node_version(node)
        return _dedupe_or_submit(
            task, coordinator, operation=OPERATION_APPROVE, actor_id=actor_id, target_id=applicant_id,
            expected_parent_id=version[0], expected_created_at=version[1], expected_verified=version[2],
            accepted_at=accepted_at.isoformat(),
        )


def submit_operation(task, operation: str, actor_id: int, target_id: int):
    """主动认证、站长取消与本人解除的受理；权限由 API 层校验。"""
    if operation not in OPERATIONS:
        raise verification_error('unknown_operation', status_code=400)
    with short_coordination() as coordinator:
        if _lock_user(target_id) is None:
            raise verification_error('not_found', status_code=404)
        node = UserVerifyTree.objects.filter(user_id=target_id).first()
        if operation == OPERATION_DETACH and (node is None or node.parent_id is None or not node.verified):
            raise verification_error('no_relation')
        version = _node_version(node)
        return _dedupe_or_submit(
            task, coordinator, operation=operation, actor_id=actor_id, target_id=target_id,
            expected_parent_id=version[0], expected_created_at=version[1], expected_verified=version[2],
            accepted_at=timezone.now().isoformat(),
        )


def _conflict(operation: str, target_id: int, reason: str) -> dict:
    logger.info('Verification task %s on #%s skipped: %s', operation, target_id, reason)
    return {'status': 'conflict', 'operation': operation, 'target_id': target_id, 'affected': 0, 'verified': None, 'reason': reason}


def _applied(operation: str, target_id: int, affected: int, verified: bool) -> dict:
    return {'status': 'applied', 'operation': operation, 'target_id': target_id, 'affected': affected, 'verified': verified, 'reason': None}


def _apply_locked(*, operation: str, actor_id: int, target_id: int, expected_parent_id,
                  expected_created_at, expected_verified: bool, accepted_at: str) -> dict:
    node = UserVerifyTree.objects.filter(user_id=target_id).first()
    if _node_version(node) != (expected_parent_id, expected_created_at, expected_verified):
        return _conflict(operation, target_id, 'state_changed')

    if operation == OPERATION_APPROVE:
        if node is None or node.verified or node.parent_id != actor_id:
            return _conflict(operation, target_id, 'request_missing')
        deadline = node.created_at + WINDOW
        try:
            accepted = parse_datetime(accepted_at)
        except (TypeError, ValueError):
            return _conflict(operation, target_id, 'invalid_accepted_at')
        if accepted is None or accepted.tzinfo is None or accepted >= deadline:
            return _conflict(operation, target_id, 'expired')
        if actor_id in _effective_subtree(target_id):
            return _conflict(operation, target_id, 'cycle')
        actor = UserProfile.objects.filter(pk=actor_id).first()
        if actor is None:
            return _conflict(operation, target_id, 'actor_missing')
        node.verified = True
        node.save(update_fields=['verified'])
        affected = _set_subtree_verification(target_id, actor.verified)
        return _applied(operation, target_id, affected, actor.verified)

    if operation == OPERATION_GRANT:
        _write_node(target_id, parent_id=None, verified=True, created_at=timezone.now())
        affected = _set_subtree_verification(target_id, True)
        return _applied(operation, target_id, affected, True)

    if operation == OPERATION_DETACH and (node is None or node.parent_id is None or not node.verified):
        return _conflict(operation, target_id, 'no_relation')
    # 站长取消作用于任意当前节点；没有节点时只确保用户状态不是已认证。
    if node is not None:
        node.parent_id = None
        node.verified = False
        node.save(update_fields=['parent', 'verified'])
    affected = _set_subtree_verification(target_id, False)
    return _applied(operation, target_id, affected, False)


def execute_verification_operation(task_id: str, *, operation: str, actor_id: int, target_id: int,
                                   expected_parent_id, expected_created_at, expected_verified: bool,
                                   accepted_at: str, sequence: int) -> dict:
    """worker 在单个事务内完成树变更、级联状态与幂等标记，失败整体回滚。"""
    if operation not in OPERATIONS:
        return _conflict(operation, target_id, 'unknown_operation')
    with transaction.atomic():
        coordinator = _lock_coordinator(skip_locked=False)
        if coordinator is None:
            raise RuntimeError('Verification coordinator row is missing.')
        applied_tasks = coordinator.applied_tasks if isinstance(coordinator.applied_tasks, dict) else {}
        if task_id in applied_tasks:
            return applied_tasks[task_id]
        result = _apply_locked(
            operation=operation, actor_id=actor_id, target_id=target_id,
            expected_parent_id=expected_parent_id, expected_created_at=expected_created_at,
            expected_verified=expected_verified, accepted_at=accepted_at,
        )
        applied_tasks[task_id] = result
        if len(applied_tasks) > APPLIED_TASK_LIMIT:
            applied_tasks = dict(list(applied_tasks.items())[-APPLIED_TASK_LIMIT:])
        coordinator.applied_tasks = applied_tasks
        coordinator.save(update_fields=['applied_tasks'])
        logger.info('Verification task %s seq=%s (%s #%s) committed: %s', task_id, sequence, operation, target_id, result['status'])
        return result


def read_task_result(user_id: int, task_id) -> dict:
    """仅任务提交者可查询，且只返回本模块任务；不返回参数或认证关系。"""
    row = DBTaskResult.objects.filter(pk=task_id, task_path=VERIFICATION_TASK_PATH).first()
    if row is None or task_kwargs(row).get('actor_id') != user_id:
        raise verification_error('not_found', status_code=404)
    result = row.return_value if row.status == TaskResultStatus.SUCCESSFUL else None
    if not isinstance(result, dict):
        result = None
    return {
        'task_id': str(row.id),
        'status': str(row.status),
        'finished_at': row.finished_at,
        'result': result,
        'error': 'task_failed' if row.status == TaskResultStatus.FAILED else None,
    }
