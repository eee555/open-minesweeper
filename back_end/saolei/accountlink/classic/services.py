"""95经典扫雷账号绑定：我方发起申请，玩家在小游戏内确认，对方回调落库。"""
from datetime import timedelta
import json
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from .client import request_classic_bind, required_callback_secret, verify_classic_callback
from ..models import AccountClassicMinesweeper, AccountLinkQueue, CLASSIC_USERID_MAX, CLASSIC_USERID_MIN, ClassicBindRequest, Platform
from ..services import save_verified_account_link

logger = logging.getLogger('accountlink')

CLASSIC_CALLBACK_RESULTS = {'allow', 'deny', 'revoke'}


def start_classic_bind(user: UserProfile, uid: int) -> ClassicBindRequest:
    """提交 8 位 UID，由对方推送给玩家确认；未确认前不建立任何绑定。"""
    if AccountClassicMinesweeper.objects.filter(parent=user).exists():
        logger.info(f'95经典扫雷绑定申请被拒绝 user_id={user.id} reason=already_linked')
        raise ExceptionToResponse('classic', 'already_linked', status_code=409)
    if isinstance(uid, bool) or not isinstance(uid, int) or not CLASSIC_USERID_MIN <= uid <= CLASSIC_USERID_MAX:
        raise ExceptionToResponse('classic', 'bad_request', status_code=400)

    now = timezone.now()
    if AccountClassicMinesweeper.objects.filter(pk=uid).exclude(parent=user).exists():
        logger.info(f'95经典扫雷绑定申请被拒绝 user_id={user.id} uid={uid} reason=identifier_conflict')
        raise ExceptionToResponse('classic', 'identifier_conflict', status_code=409)

    existing = ClassicBindRequest.objects.filter(uid=uid).first()
    if existing is not None and existing.status == ClassicBindRequest.Status.PENDING and existing.expires_at > now:
        if existing.userprofile_id == user.pk:
            # 远端对同一 (uid, app, account) 幂等，本地直接复用，避免消耗对方频率额度。
            logger.info(f'95经典扫雷绑定申请复用 user_id={user.id} uid={uid} request_id={existing.request_id}')
            return existing
        logger.info(f'95经典扫雷绑定申请被拒绝 user_id={user.id} uid={uid} reason=pending')
        raise ExceptionToResponse('classic', 'pending', status_code=409)

    request_id = request_classic_bind(uid, _classic_account_name(user), settings.CLASSIC_BIND_CALLBACK_URL, settings.CLASSIC_BIND_EXPIRES_IN)
    record = _store_classic_request(user, uid, request_id, now + timedelta(seconds=settings.CLASSIC_BIND_EXPIRES_IN))
    logger.info(f'95经典扫雷绑定申请已提交 user_id={user.id} uid={uid} request_id={record.request_id} expires_at={record.expires_at.isoformat()}')
    return record


def classic_bind_status(user: UserProfile) -> ClassicBindRequest | None:
    """当前用户最近一次申请；过期未处理的状态在读取时收敛为 expired。"""
    record = ClassicBindRequest.objects.filter(userprofile=user).order_by('-updated_at').first()
    if record is None or record.status != ClassicBindRequest.Status.PENDING:
        return record
    if record.expires_at > timezone.now():
        return record
    record.status = ClassicBindRequest.Status.EXPIRED
    record.save(update_fields=['status', 'updated_at'])
    return record


def handle_classic_callback(raw_body: bytes, timestamp: str, signature: str):
    """校验签名后按 requestId 处理回调；重复事件幂等，回调整体保持 2xx。"""
    if not verify_classic_callback(required_callback_secret(), timestamp, raw_body, signature):
        logger.warning('95经典扫雷回调签名校验失败')
        raise ExceptionToResponse('classic', 'invalid_signature', status_code=401)

    request_id, uid, account, result = _parse_callback_payload(raw_body)
    record = ClassicBindRequest.objects.filter(request_id=request_id).first()
    if record is None:
        logger.warning(f'95经典扫雷回调找不到申请 request_id={request_id} uid={uid}')
        raise ExceptionToResponse('classic', 'request_not_found', status_code=404)
    if record.uid != uid or record.account != account:
        logger.warning(f'95经典扫雷回调与申请不一致 request_id={request_id} uid={uid}')
        raise ExceptionToResponse('classic', 'payload_mismatch', status_code=400)

    if result == 'allow':
        _confirm_classic_binding(record.pk, uid)
    elif result == 'deny':
        _deny_classic_binding(record.pk, uid)
    else:
        _revoke_classic_binding(record.pk, uid)


def _confirm_classic_binding(record_id: int, uid: int):
    with transaction.atomic():
        record = ClassicBindRequest.objects.select_for_update().get(pk=record_id)
        if record.status == ClassicBindRequest.Status.ALLOWED:
            logger.info(f'95经典扫雷回调重复投递 request_id={record.request_id} uid={uid} result=allow')
            return
        if record.status in {ClassicBindRequest.Status.REVOKED, ClassicBindRequest.Status.CONFLICT}:
            logger.warning(f'95经典扫雷回调顺序异常 request_id={record.request_id} uid={uid} status={record.status} result=allow')
            return
        now = timezone.now()
        try:
            save_verified_account_link(record.userprofile, Platform.CLASSIC, str(uid))
        except ExceptionToResponse as exc:
            # 冲突重试也无法自愈，落库为 conflict 并留待人工处理，同时返回 2xx 停止对方重试。
            record.status = ClassicBindRequest.Status.CONFLICT
            record.error_category = exc.category
            record.handled_at = now
            record.save(update_fields=['status', 'error_category', 'handled_at', 'updated_at'])
            logger.error(f'95经典扫雷绑定冲突 request_id={record.request_id} uid={uid} user_id={record.userprofile_id} category={exc.category}')
            return
        record.status = ClassicBindRequest.Status.ALLOWED
        record.error_category = ''
        record.handled_at = now
        record.save(update_fields=['status', 'error_category', 'handled_at', 'updated_at'])
        logger.info(f'95经典扫雷绑定完成 request_id={record.request_id} uid={uid} user_id={record.userprofile_id}')


def _deny_classic_binding(record_id: int, uid: int):
    with transaction.atomic():
        record = ClassicBindRequest.objects.select_for_update().get(pk=record_id)
        if record.status in {ClassicBindRequest.Status.DENIED, ClassicBindRequest.Status.REVOKED}:
            logger.info(f'95经典扫雷回调重复投递 request_id={record.request_id} uid={uid} result=deny')
            return
        if record.status == ClassicBindRequest.Status.ALLOWED:
            logger.warning(f'95经典扫雷回调顺序异常 request_id={record.request_id} uid={uid} status=allow result=deny')
            return
        record.status = ClassicBindRequest.Status.DENIED
        record.error_category = ''
        record.handled_at = timezone.now()
        record.save(update_fields=['status', 'error_category', 'handled_at', 'updated_at'])
        logger.info(f'95经典扫雷玩家拒绝绑定 request_id={record.request_id} uid={uid} user_id={record.userprofile_id}')


def _revoke_classic_binding(record_id: int, uid: int):
    with transaction.atomic():
        record = ClassicBindRequest.objects.select_for_update().get(pk=record_id)
        if record.status == ClassicBindRequest.Status.REVOKED:
            logger.info(f'95经典扫雷回调重复投递 request_id={record.request_id} uid={uid} result=revoke')
            return
        _delete_classic_binding(record.userprofile_id, uid)
        record.status = ClassicBindRequest.Status.REVOKED
        record.error_category = ''
        record.handled_at = timezone.now()
        record.save(update_fields=['status', 'error_category', 'handled_at', 'updated_at'])
        logger.info(f'95经典扫雷玩家解除绑定 request_id={record.request_id} uid={uid} user_id={record.userprofile_id}')


def _delete_classic_binding(user_id: int, uid: int):
    """只由对方的 revoke 回调调用；本站不提供自助或管理员解绑。"""
    user = UserProfile.objects.select_for_update().filter(pk=user_id).first()
    if user is None:
        return
    AccountClassicMinesweeper.objects.filter(parent=user, pk=uid).delete()
    AccountLinkQueue.objects.filter(userprofile=user, platform=Platform.CLASSIC, identifier=str(uid)).delete()


def _store_classic_request(user: UserProfile, uid: int, request_id: int, expires_at) -> ClassicBindRequest:
    with transaction.atomic():
        record = ClassicBindRequest.objects.select_for_update().filter(uid=uid).first()
        if record is None:
            try:
                return ClassicBindRequest.objects.create(
                    uid=uid,
                    request_id=request_id,
                    userprofile=user,
                    account=_classic_account_name(user),
                    expires_at=expires_at,
                )
            except IntegrityError:
                raise ExceptionToResponse('classic', 'pending', status_code=409) from None
        if record.status == ClassicBindRequest.Status.PENDING and record.expires_at > timezone.now() and record.userprofile_id != user.pk:
            raise ExceptionToResponse('classic', 'pending', status_code=409)
        record.request_id = request_id
        record.userprofile = user
        record.account = _classic_account_name(user)
        record.status = ClassicBindRequest.Status.PENDING
        record.expires_at = expires_at
        record.error_category = ''
        record.handled_at = None
        record.save(update_fields=['request_id', 'userprofile', 'account', 'status', 'expires_at', 'error_category', 'handled_at', 'updated_at'])
        return record


def _classic_account_name(user: UserProfile) -> str:
    """小游戏「我的荣誉」会展示该账户名，因此只传用户名，不传邮箱等敏感信息。"""
    return user.username.strip()[:128]


def _parse_callback_payload(raw_body: bytes) -> tuple[int, int, str, str]:
    try:
        payload = json.loads(raw_body.decode('utf-8'))
    except ValueError:
        raise ExceptionToResponse('classic', 'bad_request', status_code=400)
    if not isinstance(payload, dict):
        raise ExceptionToResponse('classic', 'bad_request', status_code=400)
    request_id = payload.get('requestId')
    uid = payload.get('uid')
    account = payload.get('account')
    result = payload.get('result')
    if not _is_positive_int(request_id) or not _is_positive_int(uid):
        raise ExceptionToResponse('classic', 'bad_request', status_code=400)
    if not isinstance(account, str) or not account or result not in CLASSIC_CALLBACK_RESULTS:
        raise ExceptionToResponse('classic', 'bad_request', status_code=400)
    return request_id, uid, account, result


def _is_positive_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0
