from datetime import datetime, timedelta
import logging
from math import ceil
import secrets

from django.conf import settings
from django.core.cache import caches
from django.utils import timezone

from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from .client import poll_mineracer_account_link, request_mineracer_account_link
from .dtos import MINERACER_STATUS_CONFIRMED, MINERACER_STATUS_EXPIRED, MINERACER_STATUS_FAILED, MINERACER_STATUS_PENDING, MineracerAccountLinkSession
from ..models import AccountMineracer, Platform
from ..services import save_verified_account_link

logger = logging.getLogger('accountlink')

MINERACER_CACHE_ALIAS = 'default'
MINERACER_SESSION_KEY_PREFIX = 'accountlink:mineracer:session'
MINERACER_USER_PENDING_KEY_PREFIX = 'accountlink:mineracer:user'
MINERACER_START_LOCK_SECONDS = 10
MINERACER_POLL_LOCK_SECONDS = 10
MINERACER_SESSION_ID_BYTES = 24
MINERACER_SESSION_GRACE_SECONDS = 60


def start_mineracer_account_link(user: UserProfile) -> MineracerAccountLinkSession:
    now = timezone.now()
    if AccountMineracer.objects.filter(parent=user).exists():
        logger.info(f'Mineracer link start rejected user_id={user.id} reason=already_linked')
        raise ExceptionToResponse('mineracer', 'already_linked', status_code=409)

    session = _get_pending_mineracer_session_for_user(user.id, now)
    if session:
        logger.info(f'Mineracer link start reused user_id={user.id} session_id={session.session_id}')
        return session

    lock_key = _mineracer_start_lock_key(user.id)
    cache = _mineracer_cache()
    if not cache.add(lock_key, '1', timeout=MINERACER_START_LOCK_SECONDS):
        session = _get_pending_mineracer_session_for_user(user.id, timezone.now())
        if session:
            logger.info(f'Mineracer link start reused user_id={user.id} session_id={session.session_id} reason=start_lock')
            return session
        logger.warning(f'Mineracer link start rejected user_id={user.id} reason=pending_start')
        raise ExceptionToResponse('mineracer', 'pending_start', status_code=409)

    try:
        session = _get_pending_mineracer_session_for_user(user.id, timezone.now())
        if session:
            logger.info(f'Mineracer link start reused user_id={user.id} session_id={session.session_id} reason=start_lock_recheck')
            return session

        remote_session = request_mineracer_account_link()
        now = timezone.now()
        if remote_session.expires_at <= now:
            logger.warning(f'Mineracer link start rejected user_id={user.id} reason=remote_expired')
            raise ExceptionToResponse('mineracer', 'expired')

        session = MineracerAccountLinkSession(
            session_id=_make_mineracer_session_id(),
            user_id=user.id,
            device_code=remote_session.device_code,
            user_code=remote_session.user_code,
            verification_uri=remote_session.verification_uri,
            verification_uri_complete=remote_session.verification_uri_complete,
            expires_at=remote_session.expires_at,
            next_poll_at=now + timedelta(milliseconds=remote_session.poll_interval_ms),
            created_at=now,
            updated_at=now,
        )
        _save_mineracer_session(session)
        _save_user_pending_mineracer_session(session)
        logger.info(f'Mineracer link started user_id={user.id} session_id={session.session_id} expires_at={session.expires_at.isoformat()}')
        return session
    finally:
        cache.delete(lock_key)


def poll_mineracer_account_link_session(user: UserProfile, session_id: str) -> MineracerAccountLinkSession | None:
    session = _get_owned_mineracer_session(user, session_id)
    if session is None:
        return None
    if session.status != MINERACER_STATUS_PENDING:
        return session

    now = timezone.now()
    if now > session.expires_at:
        return _mark_mineracer_session_expired(session)
    if session.next_poll_at and now < session.next_poll_at:
        return session

    lock_key = _mineracer_poll_lock_key(session.session_id)
    cache = _mineracer_cache()
    if not cache.add(lock_key, '1', timeout=MINERACER_POLL_LOCK_SECONDS):
        return _get_owned_mineracer_session(user, session.session_id) or session

    try:
        session = _prepare_mineracer_poll(user, session.session_id)
        if session is None or session.status != MINERACER_STATUS_PENDING:
            return session
        if session.next_poll_at and timezone.now() < session.next_poll_at:
            return session

        session.last_polled_at = timezone.now()
        session.next_poll_at = session.last_polled_at + timedelta(milliseconds=settings.MINERACER_POLL_INTERVAL_MS)
        session.error_category = ''
        _save_mineracer_session(session)
        logger.info(f'Mineracer link poll sent user_id={user.id} session_id={session.session_id}')
        poll_result = poll_mineracer_account_link(session.device_code)
        if poll_result.status == MINERACER_STATUS_PENDING:
            return _update_pending_mineracer_session(session, poll_result.retry_after_ms)
        if poll_result.status == MINERACER_STATUS_CONFIRMED:
            return complete_mineracer_account_link(user, session, poll_result.userid)
        if poll_result.status == MINERACER_STATUS_EXPIRED:
            return _mark_mineracer_session_expired(session)
        if poll_result.status == MINERACER_STATUS_FAILED:
            return _mark_mineracer_session_failed(session, poll_result.error_category or 'remote_failed')
        raise ExceptionToResponse('mineracer', 'response')
    except ExceptionToResponse as exc:
        if exc.category in ['requestexception', 'timeout']:
            return _mark_mineracer_session_poll_error(session, exc.category)
        logger.warning(f'Mineracer link poll failed user_id={user.id} session_id={session.session_id} category={exc.category}')
        raise
    finally:
        cache.delete(lock_key)


def complete_mineracer_account_link(user: UserProfile, session: MineracerAccountLinkSession, userid: str) -> MineracerAccountLinkSession | None:
    if timezone.now() > session.expires_at:
        return _mark_mineracer_session_expired(session)

    try:
        save_verified_account_link(user, Platform.MINERACER, userid)
    except ExceptionToResponse as exc:
        if exc.obj != 'accountlink' or exc.category != 'collision':
            raise
        _mark_mineracer_session_failed(session, 'identifier_conflict', remote_userid=userid)
        raise ExceptionToResponse('mineracer', 'identifier_conflict', status_code=409)
    return _mark_mineracer_session_confirmed(session, userid)


def _prepare_mineracer_poll(user: UserProfile, session_id: str) -> MineracerAccountLinkSession | None:
    session = _get_owned_mineracer_session(user, session_id)
    if session is None:
        return None
    if session.status != MINERACER_STATUS_PENDING:
        return session
    if timezone.now() > session.expires_at:
        return _mark_mineracer_session_expired(session)
    return session


def _update_pending_mineracer_session(session: MineracerAccountLinkSession, retry_after_ms: int | None = None) -> MineracerAccountLinkSession:
    if session.status == MINERACER_STATUS_PENDING and retry_after_ms is not None:
        session.next_poll_at = timezone.now() + timedelta(milliseconds=retry_after_ms)
    session.error_category = ''
    _save_mineracer_session(session)
    _save_user_pending_mineracer_session(session)
    logger.info(f'Mineracer link poll pending user_id={session.user_id} session_id={session.session_id} next_poll_at={session.next_poll_at}')
    return session


def _mark_mineracer_session_poll_error(session: MineracerAccountLinkSession, category: str) -> MineracerAccountLinkSession:
    if session.status == MINERACER_STATUS_PENDING:
        session.error_category = category
        session.next_poll_at = timezone.now() + timedelta(milliseconds=settings.MINERACER_POLL_INTERVAL_MS)
        _save_mineracer_session(session)
        _save_user_pending_mineracer_session(session)
    logger.warning(f'Mineracer link poll transient_error user_id={session.user_id} session_id={session.session_id} category={category}')
    return session


def _mark_mineracer_session_confirmed(session: MineracerAccountLinkSession, userid: str) -> MineracerAccountLinkSession:
    session.status = MINERACER_STATUS_CONFIRMED
    session.remote_userid = userid
    session.error_category = ''
    _delete_user_pending_mineracer_session(session.user_id)
    _save_mineracer_session(session, timeout=_get_mineracer_session_grace_seconds())
    logger.info(f'Mineracer link confirmed user_id={session.user_id} session_id={session.session_id} mineracer_userid={userid}')
    return session


def _mark_mineracer_session_expired(session: MineracerAccountLinkSession) -> MineracerAccountLinkSession:
    if session.status == MINERACER_STATUS_PENDING:
        session.status = MINERACER_STATUS_EXPIRED
    _delete_user_pending_mineracer_session(session.user_id)
    _save_mineracer_session(session, timeout=_get_mineracer_session_grace_seconds())
    logger.info(f'Mineracer link expired user_id={session.user_id} session_id={session.session_id}')
    return session


def _mark_mineracer_session_failed(session: MineracerAccountLinkSession, category: str, remote_userid: str = '') -> MineracerAccountLinkSession:
    if session.status == MINERACER_STATUS_PENDING:
        session.status = MINERACER_STATUS_FAILED
    session.error_category = category
    session.remote_userid = remote_userid
    _delete_user_pending_mineracer_session(session.user_id)
    _save_mineracer_session(session, timeout=_get_mineracer_session_grace_seconds())
    logger.warning(f'Mineracer link failed user_id={session.user_id} session_id={session.session_id} category={category} mineracer_userid={remote_userid}')
    return session


def _get_pending_mineracer_session_for_user(user_id: int, now: datetime) -> MineracerAccountLinkSession | None:
    session_id = _mineracer_cache().get(_mineracer_user_pending_key(user_id))
    if not session_id:
        return None
    session = _get_mineracer_session(str(session_id))
    if session is None or session.user_id != user_id:
        _delete_user_pending_mineracer_session(user_id)
        return None
    if session.status != MINERACER_STATUS_PENDING:
        _delete_user_pending_mineracer_session(user_id)
        return None
    if now > session.expires_at:
        _mark_mineracer_session_expired(session)
        return None
    return session


def _get_owned_mineracer_session(user: UserProfile, session_id: str) -> MineracerAccountLinkSession | None:
    session = _get_mineracer_session(session_id)
    if session is None or session.user_id != user.id:
        return None
    return session


def _get_mineracer_session(session_id: str) -> MineracerAccountLinkSession | None:
    value = _mineracer_cache().get(_mineracer_session_key(session_id))
    if not isinstance(value, MineracerAccountLinkSession):
        return None
    return value


def _save_mineracer_session(session: MineracerAccountLinkSession, timeout: int | None = None) -> MineracerAccountLinkSession:
    now = timezone.now()
    if session.created_at is None:
        session.created_at = now
    session.updated_at = now
    if timeout is None:
        timeout = _get_mineracer_session_timeout_seconds(session, now)
    _mineracer_cache().set(_mineracer_session_key(session.session_id), session, timeout=timeout)
    return session


def _save_user_pending_mineracer_session(session: MineracerAccountLinkSession):
    if session.status != MINERACER_STATUS_PENDING:
        return
    _mineracer_cache().set(
        _mineracer_user_pending_key(session.user_id),
        session.session_id,
        timeout=_get_mineracer_user_pending_timeout_seconds(session, timezone.now()),
    )


def _delete_user_pending_mineracer_session(user_id: int):
    _mineracer_cache().delete(_mineracer_user_pending_key(user_id))


def _mineracer_cache():
    return caches[MINERACER_CACHE_ALIAS]


def _mineracer_session_key(session_id: str) -> str:
    return f'{MINERACER_SESSION_KEY_PREFIX}:{session_id}'


def _mineracer_user_pending_key(user_id: int) -> str:
    return f'{MINERACER_USER_PENDING_KEY_PREFIX}:{user_id}:pending'


def _mineracer_start_lock_key(user_id: int) -> str:
    return f'{MINERACER_USER_PENDING_KEY_PREFIX}:{user_id}:start_lock'


def _mineracer_poll_lock_key(session_id: str) -> str:
    return f'{MINERACER_SESSION_KEY_PREFIX}:{session_id}:poll_lock'


def _make_mineracer_session_id() -> str:
    cache = _mineracer_cache()
    for _ in range(3):
        session_id = secrets.token_urlsafe(MINERACER_SESSION_ID_BYTES)
        if cache.get(_mineracer_session_key(session_id)) is None:
            return session_id
    return secrets.token_urlsafe(MINERACER_SESSION_ID_BYTES)


def _get_mineracer_session_timeout_seconds(session: MineracerAccountLinkSession, now: datetime) -> int:
    seconds_to_expiry = (session.expires_at - now).total_seconds()
    return max(1, ceil(seconds_to_expiry + _get_mineracer_session_grace_seconds()))


def _get_mineracer_user_pending_timeout_seconds(session: MineracerAccountLinkSession, now: datetime) -> int:
    return max(1, ceil((session.expires_at - now).total_seconds()))


def _get_mineracer_session_grace_seconds() -> int:
    return max(1, int(getattr(settings, 'MINERACER_SESSION_GRACE_SECONDS', MINERACER_SESSION_GRACE_SECONDS)))
