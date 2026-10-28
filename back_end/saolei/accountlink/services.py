from datetime import datetime, timezone as datetime_timezone
import logging

from asgiref.sync import async_to_sync
from django.core.files import File
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from config.text_choices import MS_TextChoices, Saolei_TextChoices
from identifier.models import Identifier
from msuser.models import UserMS
from userprofile.models import UserProfile
from userprofile.services import grant_name_privacy
from utils.exceptions import ExceptionToResponse
from utils.parser import MSVideoParser
from utils.ranking_lock import ranking_access
from utils.saolei import SaoleiVideoInfo
from videomanager.models import VideoModel
from videomanager.services import set_import_upload_time
from .models import AccountLinkQueue, AccountMinesweeperGames, AccountSaolei, AccountWorldOfMinesweeper, Platform, VideoMSGames, VideoSaolei
from .msgames.client import download_replay as download_msgames_replay, fetch_profile as fetch_msgames_profile, fetch_replays as fetch_msgames_replays
from .msgames.utils import upload_date_upper_bound
from .utils import delete_account, link_account, update_bilibili_account
from .wom.client import fetch_wom_profile

logger = logging.getLogger('accountlink')

SAOLEI_VIDEO_IMPORT_TASK_PATH = 'accountlink.tasks.task_saolei_video_import'
SAOLEI_VIDEO_IMPORT_BULK_TASK_PATH = 'accountlink.tasks.task_saolei_video_import_bulk'


@transaction.atomic
def verify_account_link(user_id: int, platform: str, identifier: str, actor_id: int) -> tuple[UserProfile, bool]:
    user = UserProfile.objects.select_for_update().filter(pk=user_id).first()
    if user is None:
        raise ExceptionToResponse('user', 'not_found', status_code=404)
    if platform == Platform.MINERACER:
        raise ExceptionToResponse('mineracer', 'manual_link_not_supported', status_code=400)
    if platform not in Platform.values:
        raise ExceptionToResponse('platform', 'invalid', status_code=400)
    links = list(AccountLinkQueue.objects.select_for_update().filter(platform=platform, identifier=identifier).order_by('pk'))
    for link in links:
        if link.verified:
            if link.userprofile_id == user.pk:
                return user, False
            raise ExceptionToResponse('accountlink', 'collision', status_code=409)
    link = next((link for link in links if link.userprofile_id == user.pk), None)
    if link is None:
        raise ExceptionToResponse('accountlink', 'not_found', status_code=404)
    link_account(platform, identifier, user)
    link.verified = True
    link.save(update_fields=['verified'])
    if platform == Platform.MSGAMES:
        grant_name_privacy(user, f'Staff #{actor_id}, MSGames #{identifier}')
    return user, True


@transaction.atomic
def unverify_account_link(user_id: int, platform: str, identifier: str):
    user = UserProfile.objects.select_for_update().filter(pk=user_id).first()
    if user is None:
        raise ExceptionToResponse('user', 'not_found', status_code=404)
    if platform == Platform.MINERACER:
        raise ExceptionToResponse('mineracer', 'unlink_not_supported', status_code=409)
    if platform not in Platform.values or not identifier:
        raise ExceptionToResponse('platform', 'invalid', status_code=400)
    link = AccountLinkQueue.objects.select_for_update().filter(userprofile=user, platform=platform, identifier=identifier).first()
    if link is None:
        raise ExceptionToResponse('accountlink', 'not_found', status_code=404)
    if link.verified:
        delete_account(user, platform)
    link.delete()


def update_account(platform: Platform, user: UserProfile):
    if platform == Platform.SAOLEI:
        raise ExceptionToResponse('saolei', 'crawling_disabled', status_code=410)
    elif platform == Platform.MSGAMES:
        update_msgames_account(user.account_msgames)
    elif platform == Platform.WOM:
        update_wom_account(user.account_wom)
    elif platform == Platform.BILIBILI:
        update_bilibili_account(user.account_bilibili)
    elif platform == Platform.MINERACER:
        raise ExceptionToResponse('mineracer', 'update_not_supported', status_code=400)


def update_wom_account(account: AccountWorldOfMinesweeper):
    data = async_to_sync(fetch_wom_profile)(account.id)
    for field, value in data.items():
        setattr(account, field, value)
    account.save(update_fields=[*data, 'update_time'])


def update_msgames_account(account: AccountMinesweeperGames):
    data = fetch_msgames_profile(account.id)
    for field, value in data.items():
        setattr(account, field, value)
    account.save(update_fields=[*data, 'update_time'])


def update_msgames_video_list(account: AccountMinesweeperGames) -> list[int]:
    data = fetch_msgames_replays(account.id)
    new_ids = []
    with transaction.atomic():
        account = AccountMinesweeperGames.objects.select_for_update().get(pk=account.pk)
        for info in data:
            key = info['source_key']
            defaults = {field: value for field, value in info.items() if field != 'source_key'}
            video, created = VideoMSGames.objects.update_or_create(user=account, source_key=key, defaults=defaults)
            if created:
                new_ids.append(video.id)
        account.video_update_time = timezone.now()
        account.save(update_fields=['video_update_time'])
    return new_ids


@ranking_access(operation='accountlink.msgames_import')
def msgames_video_import_one(source: VideoMSGames):
    if source.import_video_id:
        return source.import_video
    if not source.can_import:
        raise ExceptionToResponse('file', 'type', status_code=400)
    data = download_msgames_replay(source.url)
    filename = source.filename.rsplit('.', 1)[0] + '.' + source.filename.rsplit('.', 1)[1].lower()
    parser = MSVideoParser(ContentFile(data, filename))
    with transaction.atomic():
        source = VideoMSGames.objects.select_for_update().select_related('user__parent').get(pk=source.pk)
        if source.import_video_id:
            return source.import_video
        if not source.can_import:
            raise ExceptionToResponse('file', 'type', status_code=400)
        source_time = upload_date_upper_bound(source.upload_date) if source.upload_date else None
        for collision in VideoModel.objects.filter(file_size=len(data)).order_by('id'):
            try:
                with collision.file.open('rb') as file:
                    same_file = file.read() == data
            except OSError:
                continue
            if same_file:
                set_import_upload_time(collision, source_time)
                source.import_video = collision
                source.save(update_fields=['import_video'])
                return collision
        user = source.user.parent
        if not user.userms_id:
            user.userms = UserMS.objects.create()
            user.save(update_fields=['userms'])
        if parser.state == MS_TextChoices.State.OFFICIAL and not Identifier.verify(parser.identifier, user.userms):
            parser.state = MS_TextChoices.State.IDENTIFIER
        video = VideoModel.create_from_parser(parser, user, upload_time=source_time)
        set_import_upload_time(video, source_time, created=True)
        video.update_redis()
        video.save(update_fields=['upload_time', 'ongoing_tournament'])
        source.import_video = video
        source.save(update_fields=['import_video'])
        return video


def restart_accountlink_task(db_task: DBTaskResult, args: list, kwargs: dict):
    if db_task.task_path in {
        SAOLEI_VIDEO_IMPORT_TASK_PATH, SAOLEI_VIDEO_IMPORT_BULK_TASK_PATH,
        'accountlink.tasks.task_saolei_profile',
    }:
        raise ExceptionToResponse('saolei', 'crawling_disabled', status_code=410)
    return None


def update_saolei_account_info(account: AccountSaolei, profile: dict):
    """写入已取得的扫雷网资料，不访问外站。"""
    account.name = profile['name']
    account.total_views = profile['total_views']

    account.b_t_ms = profile['timems']['b']
    account.i_t_ms = profile['timems']['i']
    account.e_t_ms = profile['timems']['e']
    account.s_t_ms = profile['timems']['s']

    account.b_b_cent = profile['bvs_cent']['b']
    account.i_b_cent = profile['bvs_cent']['i']
    account.e_b_cent = profile['bvs_cent']['e']
    account.s_b_cent = profile['bvs_cent']['s']

    account.beg_count = profile['count']['b']
    account.int_count = profile['count']['i']
    account.exp_count = profile['count']['e']

    account.update_time = datetime.now(tz=datetime_timezone.utc)

    account.save(update_fields=[
        'name', 'total_views',
        'b_t_ms', 'i_t_ms', 'e_t_ms', 's_t_ms',
        'b_b_cent', 'i_b_cent', 'e_b_cent', 's_b_cent',
        'beg_count', 'int_count', 'exp_count',
        'update_time',
    ])


def update_saolei_user_video_one_page(account: AccountSaolei, video_list: list[SaoleiVideoInfo]):
    """写入一批已取得的录像元数据，返回新增记录，不抓取页面。"""
    existing_video_ids = list(VideoSaolei.objects.filter(id__in=[info.id for info in video_list]).values_list('id', flat=True))

    new_video_list: list[VideoSaolei] = []
    for video_info in video_list:
        if video_info.id not in existing_video_ids:
            new_video = VideoSaolei.objects.create(id=video_info.id, user=account, upload_time=video_info.upload_time, level=video_info.level, bv=video_info.bv, timems=video_info.timems, nf=video_info.nf)
            new_video_list.append(new_video)

    logger.info(f'扫雷网用户#{account.id}的录像元数据入库完成，共{len(video_list)}个录像，其中{len(new_video_list)}个新录像')
    return new_video_list


# 导入一个扫雷网录像
@ranking_access(operation='accountlink.saolei_import')
def saolei_video_import_one(saolei_video: VideoSaolei, file: File, state: str):
    """导入已取得的录像文件及来源状态，保留查重、审核、上传时间和排行更新。"""
    logger.info(f'开始导入扫雷网录像#{saolei_video.id}')
    try:
        saolei_video.state = state
        saolei_video.save(update_fields=['state'])

        if state == Saolei_TextChoices.SaoleiVideoState.NOTEXIST:
            logger.warning(f'扫雷网 录像#{saolei_video.id} 不存在，可能已被删除')
            return

        file.seek(0)
        content = file.read()
        collisions = VideoModel.objects.filter(file_size=len(content))
        for collision in collisions:
            with collision.file.open('rb') as collision_file:
                same_file = collision_file.read() == content
            if same_file:
                set_import_upload_time(collision, saolei_video.upload_time)
                saolei_video.import_video = collision
                saolei_video.save(update_fields=['import_video'])
                return

        parser = MSVideoParser(ContentFile(content, file.name))
        user = saolei_video.user.parent

        if not user.userms:
            user.userms = UserMS.objects.create()
        if not Identifier.verify(parser.identifier, user.userms) and parser.state == MS_TextChoices.State.OFFICIAL:
            parser.state = MS_TextChoices.State.IDENTIFIER

        video = VideoModel.create_from_parser(parser, user, upload_time=saolei_video.upload_time)
        set_import_upload_time(video, saolei_video.upload_time, created=True)
        video.update_redis()
        video.save(update_fields=['upload_time', 'ongoing_tournament'])
        saolei_video.import_video = video
        saolei_video.save(update_fields=['import_video'])
    except BaseException:
        logger.exception(f'扫雷网录像#{saolei_video.id} 导入失败')
        raise
