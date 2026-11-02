"""95经典扫雷账号绑定与录像同步：绑定由玩家在小游戏内确认，录像由玩家勾选后对方推送。"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
import hashlib
import hmac
import json
import logging
import re

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from config.text_choices import MS_TextChoices
from identifier.models import Identifier
from msuser.models import UserMS
from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from utils.parser import MSVideoParser
from utils.ranking_lock import ranking_access
from videomanager.models import VideoModel
from videomanager.services import find_identical_video, set_import_upload_time
from videomanager.utils import calculate_original_hash
from .client import request_classic_bind, required_callback_secret, verify_classic_callback
from ..models import AccountClassicMinesweeper, AccountLinkQueue, CLASSIC_USERID_MAX, CLASSIC_USERID_MIN, ClassicBindRequest, ClassicReplay, Platform
from ..services import save_verified_account_link

logger = logging.getLogger('accountlink')

CLASSIC_CALLBACK_RESULTS = {'allow', 'deny', 'revoke'}

CLASSIC_REPLAY_EVENT = 'replay'
CLASSIC_REPLAY_FORMAT = 'evf'
CLASSIC_REPLAY_MAX_BYTES = 8 * 1024 * 1024
CLASSIC_REPLAY_KEY_PATTERN = re.compile(r'^(\d+)-(\d+)$')
CLASSIC_REPLAY_SHA256_PATTERN = re.compile(r'^[0-9a-f]{64}$')
CLASSIC_REPLAY_PLATFORMS = frozenset({'mobile', 'pc'})
CLASSIC_REPLAY_DIFFICULTIES = {'easy': 'b', 'hard': 'i', 'expert': 'e'}


@dataclass(frozen=True)
class ClassicReplayMeta:
    sync_id: int
    uid: int
    key: str
    season: int
    platform: str
    difficulty: str
    played_at: datetime
    time_ms: int
    bv3: int
    nf: bool
    sha256: str
    file_size: int


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
    now = timezone.now()
    if record.expires_at > now:
        return record
    # 只收敛仍是 pending 的记录，避免覆盖并发到达的回调结果。
    ClassicBindRequest.objects.filter(
        pk=record.pk, status=ClassicBindRequest.Status.PENDING, expires_at__lte=now,
    ).update(status=ClassicBindRequest.Status.EXPIRED, updated_at=now)
    record.refresh_from_db()
    return record


def handle_classic_callback(raw_body: bytes, timestamp: str, signature: str):
    """校验签名后按 requestId 处理回调；重复事件幂等，回调整体保持 2xx。"""
    if not verify_classic_callback(required_callback_secret(), timestamp, raw_body, signature):
        logger.warning('95经典扫雷回调签名校验失败')
        raise ExceptionToResponse('classic', 'invalid_signature', status_code=401)

    request_id, uid, account, result = _parse_callback_payload(raw_body)
    with transaction.atomic():
        # 申请行可能已被同一 UID 的新申请覆盖；必须在锁内按 requestId 命中并核对身份。
        record = _lock_classic_request(request_id, uid, account)
        if result == 'allow':
            _confirm_classic_binding(record, uid)
        elif result == 'deny':
            _deny_classic_binding(record, uid)
        else:
            _revoke_classic_binding(record, uid)


def _lock_classic_request(request_id: int, uid: int, account: str) -> ClassicBindRequest:
    record = ClassicBindRequest.objects.select_for_update().filter(request_id=request_id).first()
    if record is None:
        logger.warning(f'95经典扫雷回调找不到申请 request_id={request_id} uid={uid}')
        raise ExceptionToResponse('classic', 'request_not_found', status_code=404)
    if record.uid != uid or record.account != account:
        logger.warning(f'95经典扫雷回调与申请不一致 request_id={request_id} uid={uid}')
        raise ExceptionToResponse('classic', 'payload_mismatch', status_code=400)
    return record


def _confirm_classic_binding(record: ClassicBindRequest, uid: int):
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


def _deny_classic_binding(record: ClassicBindRequest, uid: int):
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


def _revoke_classic_binding(record: ClassicBindRequest, uid: int):
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
        if record.request_id == request_id:
            # 远端对同一 (uid, app, account) 幂等，并发的第二个请求会拿回同一个 requestId；
            # 此时必须保留已落库的 allow / deny / revoke，不能退回 pending。
            if record.userprofile_id != user.pk:
                raise ExceptionToResponse('classic', 'identifier_conflict', status_code=409)
            logger.info(f'95经典扫雷申请幂等命中 user_id={user.id} uid={uid} request_id={request_id} status={record.status}')
            return record
        if AccountClassicMinesweeper.objects.filter(parent=user).exists():
            # 网络请求期间该用户已完成绑定，不能再把申请写回 pending。
            raise ExceptionToResponse('classic', 'already_linked', status_code=409)
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


def handle_classic_replay_push(request):
    """收取玩家勾选的 EVF：先验签与文件摘要，再按 syncId / key 幂等导入。

    绑定回调与录像推送共用同一地址，由 API 层按 Content-Type 分流后进入这里。
    """
    body = _read_classic_replay_body(request)
    timestamp = request.headers.get('X-Ext-Timestamp', '')
    signature = request.headers.get('X-Ext-Signature', '')
    if not verify_classic_callback(required_callback_secret(), timestamp, body, signature):
        sync_id = request.headers.get('X-Ext-Sync-Id', '')
        logger.warning(f'95经典扫雷录像推送签名校验失败 sync_id={sync_id}')
        raise ExceptionToResponse('classic', 'invalid_signature', status_code=401)
    meta = _parse_classic_replay_meta(request.headers, len(body))
    if not hmac.compare_digest(meta.sha256, hashlib.sha256(body).hexdigest()):
        logger.warning(f'95经典扫雷录像推送摘要不匹配 sync_id={meta.sync_id} uid={meta.uid} key={meta.key}')
        raise ExceptionToResponse('classic', 'bad_checksum', status_code=400)
    _ingest_classic_replay(meta, body)


def _read_classic_replay_body(request) -> bytes:
    """流式读请求体，避免 request.body 的全局大小限制；超过 8MB 直接拒绝。"""
    content_length = request.META.get('CONTENT_LENGTH') or ''
    if content_length:
        try:
            declared = int(content_length)
        except ValueError:
            raise ExceptionToResponse('classic', 'bad_request', status_code=400) from None
        if declared > CLASSIC_REPLAY_MAX_BYTES:
            raise ExceptionToResponse('classic', 'payload_too_large', status_code=413)
    chunks, total = [], 0
    for chunk in request:
        total += len(chunk)
        if total > CLASSIC_REPLAY_MAX_BYTES:
            raise ExceptionToResponse('classic', 'payload_too_large', status_code=413)
        chunks.append(chunk)
    if not chunks:
        raise ExceptionToResponse('classic', 'bad_request', status_code=400)
    return b''.join(chunks)


def _parse_classic_replay_meta(headers, file_size: int) -> ClassicReplayMeta:
    """请求头由对方签名保护，这里只做格式与范围校验，避免脏数据入库。"""
    if headers.get('X-Ext-Event', '') != CLASSIC_REPLAY_EVENT or headers.get('X-Ext-Format', '').strip().lower() != CLASSIC_REPLAY_FORMAT:
        raise ExceptionToResponse('classic', 'bad_request', status_code=400)
    sync_id = _int_header(headers, 'X-Ext-Sync-Id', minimum=1)
    uid = _int_header(headers, 'X-Ext-Uid', minimum=CLASSIC_USERID_MIN)
    if uid > CLASSIC_USERID_MAX:
        raise ExceptionToResponse('classic', 'bad_request', status_code=400)
    key = _header(headers, 'X-Ext-Key')
    season = _int_header(headers, 'X-Ext-Season', minimum=0)
    match = CLASSIC_REPLAY_KEY_PATTERN.fullmatch(key)
    if match is None or int(match.group(1)) != season or int(match.group(2)) <= 0:
        raise ExceptionToResponse('classic', 'bad_request', status_code=400)
    platform, difficulty = _header(headers, 'X-Ext-Platform'), CLASSIC_REPLAY_DIFFICULTIES.get(_header(headers, 'X-Ext-Difficulty'))
    if platform not in CLASSIC_REPLAY_PLATFORMS or difficulty is None:
        raise ExceptionToResponse('classic', 'bad_request', status_code=400)
    played_at_ms = _int_header(headers, 'X-Ext-Played-At', minimum=1)
    try:
        played_at = datetime.fromtimestamp(played_at_ms / 1000, tz=dt_timezone.utc)
    except (OverflowError, OSError, ValueError):
        raise ExceptionToResponse('classic', 'bad_request', status_code=400) from None
    nf = _int_header(headers, 'X-Ext-Nf', minimum=0)
    if nf not in (0, 1):
        raise ExceptionToResponse('classic', 'bad_request', status_code=400)
    sha256 = _header(headers, 'X-Ext-Sha256').lower()
    if CLASSIC_REPLAY_SHA256_PATTERN.fullmatch(sha256) is None:
        raise ExceptionToResponse('classic', 'bad_request', status_code=400)
    return ClassicReplayMeta(
        sync_id=sync_id, uid=uid, key=key, season=season, platform=platform, difficulty=difficulty,
        played_at=played_at, time_ms=_int_header(headers, 'X-Ext-Time-Ms', minimum=0),
        bv3=_int_header(headers, 'X-Ext-Bv3', minimum=0),
        nf=bool(nf), sha256=sha256, file_size=file_size,
    )


def _header(headers, name: str) -> str:
    value = headers.get(name, '').strip()
    if not value:
        raise ExceptionToResponse('classic', 'bad_request', status_code=400)
    return value


def _int_header(headers, name: str, *, minimum: int) -> int:
    value = _header(headers, name)
    if not value.isascii() or not value.isdecimal():
        raise ExceptionToResponse('classic', 'bad_request', status_code=400)
    number = int(value)
    if number < minimum:
        raise ExceptionToResponse('classic', 'bad_request', status_code=400)
    return number


def _ingest_classic_replay(meta: ClassicReplayMeta, body: bytes):
    """先落同步记录再导入；导入失败保留记录，玩家再次勾选时可重试。"""
    if ClassicReplay.objects.filter(sync_id=meta.sync_id).exclude(key=meta.key).exists():
        logger.warning(f'95经典扫雷录像推送 syncId 冲突 sync_id={meta.sync_id} uid={meta.uid} key={meta.key}')
        raise ExceptionToResponse('classic', 'sync_id_conflict', status_code=400)
    replay = _store_classic_replay(meta)
    if replay.import_video_id:
        logger.info(f'95经典扫雷录像重复推送 sync_id={meta.sync_id} uid={meta.uid} key={meta.key} video_id={replay.import_video_id}')
        return
    try:
        video = _import_classic_replay(replay, body)
    except ExceptionToResponse as exc:
        ClassicReplay.objects.filter(pk=replay.pk).update(error_category=exc.category)
        logger.warning(f'95经典扫雷录像导入失败 sync_id={meta.sync_id} uid={meta.uid} key={meta.key} category={exc.obj}/{exc.category}')
        raise
    except Exception:
        ClassicReplay.objects.filter(pk=replay.pk).update(error_category='import')
        logger.exception(f'95经典扫雷录像导入异常 sync_id={meta.sync_id} uid={meta.uid} key={meta.key}')
        raise ExceptionToResponse('classic', 'import', status_code=500) from None
    if video is None:
        ClassicReplay.objects.filter(pk=replay.pk).update(error_category='unbound')
        logger.warning(f'95经典扫雷录像推送时玩家已解绑 sync_id={meta.sync_id} uid={meta.uid} key={meta.key}')
        return
    logger.info(f'95经典扫雷录像已导入 sync_id={meta.sync_id} uid={meta.uid} key={meta.key} video_id={video.pk}')


def _store_classic_replay(meta: ClassicReplayMeta) -> ClassicReplay:
    defaults = {
        'sync_id': meta.sync_id, 'season': meta.season, 'platform': meta.platform, 'difficulty': meta.difficulty,
        'played_at': meta.played_at, 'time_ms': meta.time_ms, 'bv3': meta.bv3,
        'nf': meta.nf, 'sha256': meta.sha256, 'file_size': meta.file_size, 'error_category': '',
    }
    with transaction.atomic():
        replay = ClassicReplay.objects.select_for_update().filter(key=meta.key).first()
        if replay is not None and replay.uid != meta.uid:
            logger.warning(f'95经典扫雷录像 key 属于其他玩家 key={meta.key} uid={meta.uid} owner_uid={replay.uid}')
            raise ExceptionToResponse('classic', 'key_conflict', status_code=409)
        if replay is None:
            try:
                with transaction.atomic():
                    return ClassicReplay.objects.create(uid=meta.uid, key=meta.key, **defaults)
            except IntegrityError:
                replay = ClassicReplay.objects.select_for_update().filter(key=meta.key).first()
                if replay is None:
                    raise ExceptionToResponse('classic', 'sync_id_conflict', status_code=400) from None
                if replay.uid != meta.uid:
                    raise ExceptionToResponse('classic', 'key_conflict', status_code=409) from None
        if replay.import_video_id and replay.sha256 != meta.sha256:
            logger.warning(f'95经典扫雷同一录像重复推送但文件摘要变化 key={meta.key} uid={meta.uid}')
        for field, value in defaults.items():
            setattr(replay, field, value)
        try:
            with transaction.atomic():
                replay.save(update_fields=[*defaults, 'updated_at'])
        except IntegrityError:
            raise ExceptionToResponse('classic', 'sync_id_conflict', status_code=400) from None
        return replay


@ranking_access(operation='accountlink.classic_import', blocking=False)
def _import_classic_replay(replay: ClassicReplay, data: bytes) -> VideoModel | None:
    """解析并导入 EVF；录像内容才是成绩来源，请求头只用于归属与幂等。"""
    file = ContentFile(data, f'{replay.key}.evf')
    original_hash = calculate_original_hash(file)
    with transaction.atomic():
        replay = ClassicReplay.objects.select_for_update().get(pk=replay.pk)
        if replay.import_video_id:
            return replay.import_video
        account = AccountClassicMinesweeper.objects.filter(pk=replay.uid).first()
        if account is None:
            return None
        # 与 revoke 保持「先锁用户、再删绑定」的顺序，避免两边互相等待。
        user = UserProfile.objects.select_for_update().get(pk=account.parent_id)
        if not AccountClassicMinesweeper.objects.filter(pk=replay.uid, parent=user).exists():
            return None
        collision = find_identical_video(original_hash)
        if collision is not None:
            collision = VideoModel.objects.select_for_update().get(pk=collision.pk)
            if collision.player_id != user.pk:
                raise ExceptionToResponse('file', 'collision', status_code=409)
            set_import_upload_time(collision, replay.played_at)
            replay.import_video = collision
            replay.save(update_fields=['import_video'])
            return collision
        parser = MSVideoParser(file)
        if not user.userms_id:
            user.userms = UserMS.objects.create()
            user.save(update_fields=['userms'])
        if parser.state == MS_TextChoices.State.OFFICIAL and not Identifier.verify(parser.identifier, user.userms):
            parser.state = MS_TextChoices.State.IDENTIFIER
        video = VideoModel.create_from_parser(parser, user, original_hash=original_hash, upload_time=replay.played_at)
        # 文件仍是 EVF，但来源标记为 95 经典扫雷，便于前端区分来源。
        video.software = MS_TextChoices.Software.CLASSIC
        set_import_upload_time(video, replay.played_at, created=True)
        video.update_redis()
        video.save(update_fields=['upload_time', 'ongoing_tournament', 'software'])
        replay.import_video = video
        replay.save(update_fields=['import_video'])
        logger.info(f'95经典扫雷录像 {replay.key} 已关联本站录像#{video.pk}')
        return video
