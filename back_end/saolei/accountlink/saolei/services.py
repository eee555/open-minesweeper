from collections import Counter
from itertools import batched
import logging

from django.core.files import File
from django.core.files.base import ContentFile
from django.db import close_old_connections, transaction
from django.utils import timezone
from saolei_api import AuthenticationError, Client, RateLimitError, ResponseError, VideoInfo, VideoListResponse

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
from .client import saolei_client
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
    if page.cursor != cursor or ids != sorted(set(ids)) or any(value <= cursor for value in ids):
        raise ResponseError('Invalid video_list ordering or cursor')
    # 末页的上游游标为 null，表示没有下一页；有下一页时必须给出可前进的游标。
    if page.next_cursor is None:
        if page.has_more:
            raise ResponseError('video_list returned hasMore=true without a next_cursor')
        following = max([cursor, *ids])
    else:
        if page.next_cursor < max([cursor, *ids]) or (page.has_more and page.next_cursor <= cursor):
            raise ResponseError('video_list next_cursor precedes its records or does not advance')
        # cursor 是已处理的 ID，下一页返回 ID > cursor；跨过本轮上界时不能跳过 upper_bound + 1。
        following = min(page.next_cursor, upper_bound)
    records = [(item.id, video_defaults(item, account.pk)) for item in page.items if item.id <= upper_bound]
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
    while True:
        cursor, has_more = sync_saolei_page(account, client, cursor=cursor, upper_bound=upper_bound, page_size=page_size)
        if progress:
            progress(f'账号#{account.pk} 目录游标：{cursor}')
        if not has_more:
            break


def sync_saolei_page(account: AccountSaolei, client: Client, *, cursor: int, upper_bound: int, page_size=200):
    """一次请求只同步一页，前端负责决定是否继续调用下一页。"""
    if cursor >= upper_bound:
        following, has_more = cursor, False
    else:
        page = client.video_list(player_id=account.pk, cursor=cursor, size=page_size)
        following = save_catalogue_page(account, page, cursor=cursor, upper_bound=upper_bound)
        has_more = page.has_more and following < upper_bound
    if not has_more:
        with transaction.atomic():
            current = lock_account(account)
            current.video_update_time = timezone.now()
            current.save(update_fields=['video_update_time'])
    return following, has_more


def pending_saolei_videos(account=None, upper_bound=None, *, ready=False, include_rejected=False):
    videos = SaoleiApiVideo.objects.filter(import_video__isnull=True, software__in=SUPPORTED_SOFTWARE)
    if not include_rejected:
        videos = videos.filter(import_rejected=False)
    if account is not None:
        videos = videos.filter(user=account)
    if upper_bound is not None:
        videos = videos.filter(remote_id__lte=upper_bound)
    if ready:
        videos = videos.filter(file_url__isnull=False).exclude(file_url='')
    return videos


def sync_saolei_metadata(account, client, *, upper_bound, counts, report_failure, full=False, page_size=200, progress=None):
    """只更新资料、目录及文件 URL，不下载录像；每日调度与命令共用。"""
    for stage, action, kwargs in [
        ('资料', update_saolei_account_info, {}),
        ('目录', sync_saolei_catalogue, {'upper_bound': upper_bound, 'full': full, 'page_size': page_size, 'progress': progress}),
        ('详情', refresh_saolei_details, {'upper_bound': upper_bound, 'counts': counts, 'report_failure': report_failure, 'progress': progress}),
    ]:
        try:
            action(account, client, **kwargs)
        except (AuthenticationError, RateLimitError):
            raise
        except Exception as exc:
            report_failure(f'账号#{account.pk} {stage}', exc, counts)
    counts['accounts'] += 1


def refresh_saolei_details(account, client, *, upper_bound, counts, report_failure, progress=None):
    # 扫描本地未完成来源，目录游标已提交后发生的详情失败也能在下次补取。
    sources = pending_saolei_videos(account, upper_bound).order_by('remote_id').iterator(chunk_size=50)
    for batch in batched(sources, 50):
        try:
            details = client.video_info([source.remote_id for source in batch]).items
            saved = save_video_details(account, batch, details)
        except (AuthenticationError, RateLimitError):
            raise
        except Exception as exc:
            report_failure(f'账号#{account.pk} 详情批次#{batch[0].remote_id}', exc, counts)
            continue
        counts['details'] += len(saved)
        available = {source.remote_id for source in saved}
        for source in batch:
            if source.remote_id not in available:
                report_failure(f'来源录像#{source.remote_id}', ExceptionToResponse('saolei', 'detail_unavailable', 503), counts)
        if progress:
            progress(f'账号#{account.pk} 详情已更新：{len(saved)}/{len(batch)}')


def import_pending_saolei_videos(sources, client, *, counts, report_failure, limit=None, progress=None, automatic=False, ignore_rejected=False):
    """仅下载已保存 URL 的来源；上限按尝试数计算，失败也占用本轮额度。"""
    snapshots = list(sources.order_by('remote_id').values_list('pk', 'user__parent_id')[:limit])
    for source_id, parent_id in snapshots:
        rows = pending_saolei_videos(ready=True, include_rejected=ignore_rejected).filter(pk=source_id)
        if automatic:
            rows = rows.filter(user__auto_sync=True)
        source = rows.select_related('user').first()
        if source is None:
            continue
        counts['attempted'] += 1
        try:
            check_binding(source.user, parent_id)
            result = import_saolei_video(source, client, refresh_detail=False, ignore_rejected=ignore_rejected)
            counts[result] += 1
            if progress:
                progress(f'来源录像#{source.remote_id}：{result}')
        except (AuthenticationError, RateLimitError):
            raise
        except Exception as exc:
            report_failure(f'来源录像#{source.remote_id}', exc, counts)
            SaoleiApiVideo.objects.filter(pk=source_id, import_video__isnull=True).update(import_rejected=True)


def save_video_details(account, sources, details):
    requested = {source.remote_id: source.pk for source in sources}
    ids = [detail.id for detail in details]
    if len(ids) != len(set(ids)) or any(remote_id not in requested for remote_id in ids):
        raise ResponseError('Unexpected or duplicate video detail ID')
    defaults = {detail.id: {**video_defaults(detail, account.pk), 'file_url': detail.file_url} for detail in details}
    with transaction.atomic():
        current_account = lock_account(account)
        current = list(SaoleiApiVideo.objects.select_for_update().filter(pk__in=requested.values(), user=current_account))
        updated = []
        for source in current:
            if source.remote_id not in defaults:
                continue
            for field, value in defaults[source.remote_id].items():
                setattr(source, field, value)
            source.user = current_account
            updated.append(source)
        if updated:
            SaoleiApiVideo.objects.bulk_update(updated, fields=list(defaults[updated[0].remote_id]))
        return updated


def save_video_detail(source: SaoleiApiVideo, detail: VideoInfo) -> SaoleiApiVideo:
    if detail.id != source.remote_id:
        raise ResponseError('Mismatched video detail ID')
    updated, = save_video_details(source.user, [source], [detail])
    return updated


def import_saolei_video(source: SaoleiApiVideo, client: Client, *, refresh_detail=True, ignore_rejected=False) -> str:
    if source.import_video_id:
        return 'existing'
    if (source.import_rejected and not ignore_rejected) or source.software not in SUPPORTED_SOFTWARE:
        return 'skipped'
    if refresh_detail:
        details = [item for item in client.video_info(source.remote_id).items if item.id == source.remote_id]
        if len(details) != 1:
            raise ExceptionToResponse('saolei', 'detail_unavailable', status_code=503)
        source = save_video_detail(source, details[0])
    if source.software not in SUPPORTED_SOFTWARE:
        return 'skipped'
    if not source.file_url:
        raise ExceptionToResponse('saolei', 'file_unavailable', status_code=503)
    data, = client.download_videos([source.file_url])
    if len(data) > MaxSizes.VIDEOFILE:
        raise ExceptionToResponse('file', 'size', status_code=400)
    filename = source.file_url.rsplit('/', 1)[-1]
    stem, extension = filename.rsplit('.', 1)
    try:
        saolei_video_import_one(source, ContentFile(data, f'{stem}.{extension.lower()}'))
    except ExceptionToResponse as exc:
        if exc.obj == 'file' and exc.category in {'type', 'incomplete', 'level', 'review'}:
            # 导入事务已回滚；单独保留明确的文件拒收结果，避免下次同步重复下载。
            SaoleiApiVideo.objects.filter(pk=source.pk, import_video__isnull=True).update(import_rejected=True)
        raise
    return 'imported'


def report_saolei_sync_failure(target, exc, counts):
    counts['failed'] += 1
    if isinstance(exc, ExceptionToResponse):
        logger.error('扫雷网同步 %s 失败：%s/%s', target, exc.obj, exc.category)
    else:
        logger.exception('扫雷网同步 %s 失败：%s', target, type(exc).__name__)


def sync_saolei_metadata_daily():
    """由 APScheduler 直接调用，只更新元数据，不占用 Django Task worker。"""
    account_ids = list(AccountSaolei.objects.filter(auto_sync=True).order_by('pk').values_list('pk', flat=True))
    if not account_ids:
        return {}
    counts = Counter()
    with saolei_client() as client:
        upper_bound = client.stats().max_video_id
        for account_id in account_ids:
            close_old_connections()
            account = AccountSaolei.objects.filter(pk=account_id, auto_sync=True).first()
            if account is None:
                continue
            try:
                check_binding(account, account.parent_id)
            except ExceptionToResponse as exc:
                report_saolei_sync_failure(f'账号#{account.pk} 绑定', exc, counts)
                continue
            sync_saolei_metadata(account, client, upper_bound=upper_bound, counts=counts, report_failure=report_saolei_sync_failure)
    logger.info('扫雷网每日目录同步完成：%s', dict(counts))
    if counts['failed']:
        raise ExceptionToResponse('saolei', 'partial_sync', 500)
    return dict(counts)


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
        logger.info('解析扫雷网来源录像#%s account_id=%s file_url=%s', source.remote_id, account.pk, source.file_url)
        parser = MSVideoParser(file, isolate=True)
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
