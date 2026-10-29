import logging

from django.core.files import File
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from saolei_api import Client, ResponseError, VideoInfo, VideoListResponse

from config.global_settings import MaxSizes
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
from .utils import SUPPORTED_SOFTWARE, video_defaults
from ..models import AccountLinkQueue, AccountSaolei, Platform, SaoleiApiVideo

logger = logging.getLogger('accountlink')


def check_binding(account: AccountSaolei, parent_id: int):
    """同步期间绑定必须仍指向入参中的同一用户；不校验操作者权限。"""
    if account.parent_id == parent_id:
        identifiers = AccountLinkQueue.objects.filter(platform=Platform.SAOLEI, verified=True, userprofile_id=parent_id).values_list('identifier', flat=True)
        if any(value.isascii() and value.isdecimal() and int(value) == account.pk for value in identifiers):
            return
    raise ExceptionToResponse('saolei', 'binding_changed', status_code=409)


def lock_account(account: AccountSaolei) -> AccountSaolei:
    current = AccountSaolei.objects.select_for_update().get(pk=account.pk)
    check_binding(current, account.parent_id)
    return current


def update_saolei_account_info(account: AccountSaolei, client: Client):
    profiles = [profile for profile in client.user_info(account.pk).users if profile.id == account.pk]
    if len(profiles) != 1 or len(profiles[0].name) > AccountSaolei._meta.get_field('name').max_length:
        raise ResponseError('Missing or invalid user profile')
    profile = profiles[0]
    with transaction.atomic():
        current = lock_account(account)
        current.name, current.banned = profile.name, profile.banned
        current.update_time = timezone.now()
        current.save(update_fields=['name', 'banned', 'update_time'])


def save_catalogue_page(account: AccountSaolei, page: VideoListResponse, *, cursor: int, upper_bound: int) -> int:
    ids = [item.id for item in page.items]
    if page.cursor != cursor or ids != sorted(set(ids)) or any(value < cursor for value in ids):
        raise ResponseError('Invalid video_list ordering or cursor')
    if page.next_cursor < cursor or ((page.has_more or ids) and page.next_cursor <= max([cursor, *ids])):
        raise ResponseError('video_list cursor did not advance past its records')
    records = [(item.id, video_defaults(item, account.pk)) for item in page.items if item.id <= upper_bound]
    following = min(page.next_cursor, upper_bound + 1)
    with transaction.atomic():
        current = lock_account(account)
        for remote_id, defaults in records:
            source, created = SaoleiApiVideo.objects.select_for_update().get_or_create(remote_id=remote_id, defaults={'user': current, **defaults})
            if source.user_id != current.pk:
                raise ExceptionToResponse('saolei', 'source_collision', status_code=409)
            if not created:
                for field, value in defaults.items():
                    setattr(source, field, value)
                source.save(update_fields=list(defaults))
        current.video_sync_cursor = max(current.video_sync_cursor, following)
        current.save(update_fields=['video_sync_cursor'])
    return following


def sync_saolei_catalogue(account: AccountSaolei, client: Client, *, upper_bound: int, full=False, page_size=200, progress=None):
    current = AccountSaolei.objects.get(pk=account.pk)
    check_binding(current, account.parent_id)
    cursor = 0 if full else current.video_sync_cursor
    while cursor <= upper_bound:
        page = client.video_list(player_id=account.pk, cursor=cursor, size=page_size)
        cursor = save_catalogue_page(account, page, cursor=cursor, upper_bound=upper_bound)
        if progress:
            progress(f'账号#{account.pk} 目录游标：{cursor}')
        if not page.has_more:
            break
    with transaction.atomic():
        current = lock_account(account)
        current.video_update_time = timezone.now()
        current.save(update_fields=['video_update_time'])


def save_video_detail(source: SaoleiApiVideo, detail: VideoInfo) -> SaoleiApiVideo:
    if detail.id != source.remote_id:
        raise ResponseError('Mismatched video detail ID')
    defaults = video_defaults(detail, source.user_id)
    defaults['file_url'] = detail.file_url
    with transaction.atomic():
        account = lock_account(source.user)
        current = SaoleiApiVideo.objects.select_for_update().get(pk=source.pk, user=account)
        for field, value in defaults.items():
            setattr(current, field, value)
        current.save(update_fields=list(defaults))
        current.user = account
        return current


def import_saolei_video(source: SaoleiApiVideo, client: Client) -> str:
    if source.import_video_id:
        return 'existing'
    if source.software not in SUPPORTED_SOFTWARE:
        return 'skipped'
    details = [item for item in client.video_info(source.remote_id).items if item.id == source.remote_id]
    if len(details) != 1:
        raise ExceptionToResponse('saolei', 'detail_unavailable', status_code=503)
    detail = details[0]
    source = save_video_detail(source, detail)
    if source.software not in SUPPORTED_SOFTWARE:
        return 'skipped'
    if not source.file_url:
        raise ExceptionToResponse('saolei', 'file_unavailable', status_code=503)
    data, = client.download_videos([source.file_url])
    if len(data) > MaxSizes.VIDEOFILE:
        raise ExceptionToResponse('file', 'size', status_code=400)
    filename = source.file_url.rsplit('/', 1)[-1]
    stem, extension = filename.rsplit('.', 1)
    saolei_video_import_one(source, ContentFile(data, f'{stem}.{extension.lower()}'))
    return 'imported'


@ranking_access(operation='accountlink.saolei_import')
def saolei_video_import_one(source: SaoleiApiVideo, file: File) -> VideoModel:
    """只处理已取得的文件，网络请求在排行锁和数据库事务之外。"""
    original_hash = calculate_original_hash(file)
    with transaction.atomic():
        account = lock_account(source.user)
        source = SaoleiApiVideo.objects.select_for_update().get(pk=source.pk, user=account)
        if source.software not in SUPPORTED_SOFTWARE:
            raise ExceptionToResponse('saolei', 'unsupported_software', status_code=400)
        user = UserProfile.objects.select_for_update().get(pk=account.parent_id)
        if source.import_video_id:
            existing = VideoModel.objects.select_for_update().get(pk=source.import_video_id)
            if existing.player_id != user.pk:
                raise ExceptionToResponse('file', 'collision', status_code=409)
            set_import_upload_time(existing, source.upload_time)
            return existing
        collision = find_identical_video(original_hash)
        if collision is not None:
            collision = VideoModel.objects.select_for_update().get(pk=collision.pk)
            if collision.player_id != user.pk:
                raise ExceptionToResponse('file', 'collision', status_code=409)
            set_import_upload_time(collision, source.upload_time)
            source.import_video = collision
            source.save(update_fields=['import_video'])
            return collision
        parser = MSVideoParser(file)
        if not user.userms_id:
            user.userms = UserMS.objects.create()
            user.save(update_fields=['userms'])
        if parser.state == MS_TextChoices.State.OFFICIAL and not Identifier.verify(parser.identifier, user.userms):
            parser.state = MS_TextChoices.State.IDENTIFIER
        video = VideoModel.create_from_parser(parser, user, original_hash=original_hash, upload_time=source.upload_time)
        set_import_upload_time(video, source.upload_time, created=True)
        video.update_redis()
        video.save(update_fields=['upload_time', 'ongoing_tournament'])
        source.import_video = video
        source.save(update_fields=['import_video'])
        logger.info('扫雷网来源录像#%s 已关联本站录像#%s', source.remote_id, video.pk)
        return video
