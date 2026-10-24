from contextlib import contextmanager
from contextvars import ContextVar
import logging
import os
from pathlib import Path
import re
from time import monotonic

from django.conf import settings
from filelock import ReadWriteLock, Timeout

from .exceptions import ExceptionToResponse

logger = logging.getLogger('speedranking')
_access = ContextVar('top_ranking_access', default=None)
_write_paths = re.compile(
    r'^/(?:common/uploadvideo/|video/(?:set/|update/|update/batch/)|'
    r'identifier/(?:add/|del/|add/staff/|del/staff/)|'
    r'api/accountlink/msgames/videos/\d+/import/?|api/tournament/video/\d+/reveal/?|'
    r'api/video/admin/delete/?|'
    r'api/tournament/gsc/history/prepare/?|api/tournament/gsc/history/participants/\d+/(?:identifier|videos)/?|'
    r'api/speedranking/top/admin/rebuild_record/?|'
    r'dangerzone/(?:create_video|bind_identifier|unbind_identifier|delete_identifier|flush_database)/?)$',
)


class RankingRefreshBusy(ExceptionToResponse):
    def __init__(self):
        super().__init__('top', 'refreshing', status_code=503)

    def response(self):
        response = super().response()
        response['Retry-After'] = '1'
        return response


@contextmanager
def ranking_access(*, exclusive=False, blocking=True, operation='top update', request=None):
    """单机共享准入；独占刷新等待业务操作及其提交回调完成。"""
    held = _access.get()
    if held and held[0] == os.getpid():
        if exclusive and not held[1]:
            raise RuntimeError('Cannot rebuild top rankings inside a shared operation')
        yield
        return
    path = Path(getattr(settings, 'TOP_RANKING_LOCK_PATH', settings.BASE_DIR / 'runtime' / 'top-lock.sqlite3'))
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = ReadWriteLock(path, is_singleton=False)
    started = monotonic()
    acquire = lock.acquire_write if exclusive else lock.acquire_read
    try:
        acquire(blocking=False)
    except Timeout:
        if not blocking:
            user = request.__dict__.get('_cached_user') if request else None
            logger.warning('top refresh rejected method=%s path=%s user_id=%s retry_after=1', request.method if request else None, request.path_info if request else None, getattr(user, 'pk', None))
            lock.close()
            raise RankingRefreshBusy() from None
        logger.info('top lock waiting operation=%s exclusive=%s', operation, exclusive)
        try:
            acquire(timeout=getattr(settings, 'TOP_RANKING_REFRESH_WAIT', 30) if exclusive else -1)
        except BaseException:
            logger.exception('top lock acquisition failed operation=%s', operation)
            lock.close()
            raise
        logger.info('top lock acquired operation=%s waited=%.3fs', operation, monotonic() - started)
    except Exception:
        logger.exception('top lock acquisition failed operation=%s', operation)
        lock.close()
        raise
    token = _access.set((os.getpid(), exclusive))
    try:
        yield
    finally:
        _access.reset(token)
        try:
            lock.release()
        finally:
            lock.close()


class TopRankingWriteMiddleware:
    """HTTP 准入位于视图及其最外层事务之外，不在提交后拒绝缓存更新。"""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in {'GET', 'HEAD', 'OPTIONS'} or not (_write_paths.fullmatch(request.path_info) or request.path_info.startswith('/admin/')):
            return self.get_response(request)
        try:
            with ranking_access(blocking=False, request=request):
                return self.get_response(request)
        except RankingRefreshBusy as exc:
            return exc.response()
