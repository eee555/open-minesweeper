"""认证图维护会话与写入串行化，状态只保存在 Redis 缓存中，不建历史表。"""

from contextlib import contextmanager
from datetime import datetime, timedelta
import logging
from typing import Iterator

from django.core.cache import cache
from django.utils import timezone

from .utils import GRAPH_WRITE_LOCK_KEY, GRAPH_WRITE_LOCK_SECONDS, MAINTENANCE_KEY, verification_error

logger = logging.getLogger('userprofile')


@contextmanager
def graph_write_lock() -> Iterator[None]:
    """所有认证图写入共用一把带 TTL 的短锁；进程异常退出后锁自动释放。"""
    if not cache.add(GRAPH_WRITE_LOCK_KEY, '1', timeout=GRAPH_WRITE_LOCK_SECONDS):
        raise verification_error('processing')
    try:
        yield
    finally:
        cache.delete(GRAPH_WRITE_LOCK_KEY)


def read_maintenance() -> dict | None:
    """返回当前有效会话；TTL 到期或数据损坏时按「未开启」处理并清除残留。"""
    state = cache.get(MAINTENANCE_KEY)
    if not isinstance(state, dict):
        return None
    owner_id = state.get('owner_id')
    if not isinstance(owner_id, int):
        cache.delete(MAINTENANCE_KEY)
        return None
    try:
        expires_at = datetime.fromisoformat(state.get('expires_at'))
    except (TypeError, ValueError):
        cache.delete(MAINTENANCE_KEY)
        return None
    if expires_at.tzinfo is None or expires_at <= timezone.now():
        cache.delete(MAINTENANCE_KEY)
        return None
    return {'owner_id': owner_id, 'expires_at': expires_at}


def maintenance_is_active() -> bool:
    return read_maintenance() is not None


def start_maintenance(owner_id: int, duration_seconds: int) -> dict:
    """开启独占维护会话；已有会话时拒绝，不延长或接管别人的会话。"""
    with graph_write_lock():
        if read_maintenance() is not None:
            raise verification_error('maintenance_active')
        expires_at = timezone.now() + timedelta(seconds=duration_seconds)
        state = {'owner_id': owner_id, 'expires_at': expires_at.isoformat()}
        cache.set(MAINTENANCE_KEY, state, timeout=duration_seconds)
    logger.info('Verification maintenance started by #%s for %ss', owner_id, duration_seconds)
    return {'owner_id': owner_id, 'expires_at': expires_at}


def require_owned_maintenance(owner_id: int) -> dict:
    state = read_maintenance()
    if state is None:
        raise verification_error('maintenance_required')
    if state['owner_id'] != owner_id:
        raise verification_error('maintenance_owner', status_code=403)
    return state


def end_maintenance(owner_id: int):
    with graph_write_lock():
        require_owned_maintenance(owner_id)
        cache.delete(MAINTENANCE_KEY)
    logger.info('Verification maintenance ended by #%s', owner_id)


def release_maintenance():
    """批次提交成功后释放会话；调用方持有写入锁，期间不会有新会话建立。"""
    cache.delete(MAINTENANCE_KEY)
