import json

from django.db import transaction
from django.db.models import BigIntegerField, F
from django.db.models.functions import Coalesce
from django.tasks import TaskResultStatus
from django.utils import timezone as django_timezone
from django_tasks_db.models import DBTaskResult

from accountlink.models import AccountLinkQueue, Platform
from config.common import TASK_CLEANUP_CONFIGS
from config.customranking import CUSTOM_PLUCK_LEVELS
from config.text_choices import MS_TextChoices
from customranking.cache import PLuckRankingCache
from identifier.models import Identifier
from identifier.services import bind_identifier
from identifier.utils import verify_identifier
from msuser.models import UserMS
from speedranking.pb.cache import PBRankingCache
from speedranking.pb.utils import encode_score, member, record_field
from speedranking.saolei.cache import SpeedRankingCache
from speedranking.saolei.utils import RANKING_NAMES, RULES
from userprofile.models import UserProfile
from userprofile.schema import UserDirectoryQuery
from utils.exceptions import ExceptionToResponse
from utils.parser import MSVideoParser
from utils.ranking_lock import ranking_access
from videomanager.models import VideoModel
from videomanager.services import find_identical_video, set_import_upload_time
from videomanager.utils import calculate_original_hash


TASK_CLEANUP_BATCH_SIZE = 200


def query_user_directory_page(filters: UserDirectoryQuery):
    users = UserProfile.objects.select_related('userms').only(
        'id', 'date_joined', 'is_memorial',
        'userms__id', 'userms__video_num_total', 'userms__video_num_tournament', 'userms__video_num_all',
        'userms__video_size_total', 'userms__video_size_tournament', 'userms__video_size_all',
    )
    links = AccountLinkQueue.objects.filter(verified=True)
    if filters.id:
        if filters.platform:
            users = users.filter(id__in=links.filter(platform=filters.platform, identifier=filters.id).values('userprofile_id'))
        else:
            users = users.filter(id=filters.id)
    if filters.sort == 'id':
        users = users.order_by('-id' if filters.reverse else 'id')
    else:
        # Missing UserMS records display and sort as zero, including pending-recount negatives.
        users = users.alias(
            video_num_total=Coalesce('userms__video_num_total', 0, output_field=BigIntegerField()),
            video_num_tournament=Coalesce('userms__video_num_tournament', 0, output_field=BigIntegerField()),
            video_num_all=Coalesce('userms__video_num_all', 0, output_field=BigIntegerField()),
            video_size_total=Coalesce('userms__video_size_total', 0, output_field=BigIntegerField()),
            video_size_tournament=Coalesce('userms__video_size_tournament', 0, output_field=BigIntegerField()),
            video_size_all=Coalesce('userms__video_size_all', 0, output_field=BigIntegerField()),
        )
        if filters.reverse:
            users = users.order_by(F(filters.sort).desc(), 'id')
        else:
            users = users.order_by(filters.sort, 'id')
    count = users.count()
    start = (filters.page - 1) * filters.page_size
    page = list(users[start:start + filters.page_size])
    if page:
        accounts = {user.id: {} for user in page}
        for user_id, platform, identifier in links.filter(
            userprofile_id__in=accounts, platform__in=[Platform.SAOLEI, Platform.MSGAMES, Platform.WOM, Platform.MINERACER],
        ).values_list('userprofile_id', 'platform', 'identifier'):
            accounts[user_id][platform] = identifier
        for user in page:
            user.accounts = accounts[user.id]
    return {'count': count, 'users': page}


@ranking_access(operation='common.import_identifier')
@transaction.atomic
def bind_import_identifier(user: UserProfile, identifier_text: str):
    if not user.userms_id:
        user.userms = UserMS.objects.create()
        user.save(update_fields=['userms'])
    identifier, _ = Identifier.objects.select_for_update().get_or_create(identifier=identifier_text, defaults={'safe': True})
    if identifier.userms_id is not None and identifier.userms_id != user.userms_id:
        return {'identifier': identifier.identifier, 'bound': False}
    if not identifier.safe:
        raise ExceptionToResponse('identifier', 'invalid', status_code=400)
    bind_identifier(identifier, user.userms)
    return {'identifier': identifier.identifier, 'bound': True}


@ranking_access(operation='common.import_video')
@transaction.atomic
def import_video_by_file(user: UserProfile, file, upload_time):
    if django_timezone.is_naive(upload_time):
        raise ExceptionToResponse('upload_time', 'timezone_required', status_code=422)
    try:
        encode_score(0, upload_time)
    except (ValueError, OverflowError) as error:
        raise ExceptionToResponse('upload_time', 'invalid', status_code=422) from error
    original_hash = calculate_original_hash(file)
    video = find_identical_video(original_hash)
    if video is not None:
        if video.player_id != user.pk:
            raise ExceptionToResponse('file', 'collision', status_code=409)
        set_import_upload_time(video, upload_time)
        return video
    try:
        parser = MSVideoParser(file)
    except ExceptionToResponse as error:
        error.status_code = max(error.status_code, 400)
        raise
    if not user.userms_id:
        user.userms = UserMS.objects.create()
        user.save(update_fields=['userms'])
    if not verify_identifier(parser.identifier):
        raise ExceptionToResponse('identifier', 'verify', status_code=400)
    if not Identifier.verify(parser.identifier, user.userms) and parser.state == MS_TextChoices.State.OFFICIAL:
        parser.state = MS_TextChoices.State.IDENTIFIER
    video = VideoModel.create_from_parser(parser, user, original_hash=original_hash, upload_time=upload_time)
    set_import_upload_time(video, upload_time, created=True)
    video.save(update_fields=['ongoing_tournament'])
    video.update_redis()
    return video


@ranking_access(operation='common.upload_video')
def new_video_by_file(user, file):
    original_hash = calculate_original_hash(file)
    if find_identical_video(original_hash) is not None:
        raise ExceptionToResponse('file', 'collision')
    parser = MSVideoParser(file)
    if not user.userms_id:
        user.userms = UserMS.objects.create()
        user.save(update_fields=['userms'])
    if not verify_identifier(parser.identifier):
        raise ExceptionToResponse('identifier', 'verify')
    if not Identifier.verify(parser.identifier, user.userms) and parser.state == MS_TextChoices.State.OFFICIAL:
        parser.state = MS_TextChoices.State.IDENTIFIER

    video = VideoModel.create_from_parser(parser, user, original_hash=original_hash)
    video.save(update_fields=['ongoing_tournament'])
    video.update_redis()
    return video


def cleanup_expired_tasks(*, delete_all=False):
    """按配置分批清理过期的成功任务，默认每种任务只删除一批。"""
    deleted_count = 0
    now = django_timezone.now()

    for config in TASK_CLEANUP_CONFIGS:
        deadline = now - config['expires']
        queryset = DBTaskResult.objects.filter(
            task_path=config['task_path'],
            status=TaskResultStatus.SUCCESSFUL,
            finished_at__lt=deadline,
        )

        while True:
            with transaction.atomic():
                task_ids = list(
                    queryset
                    .select_for_update(skip_locked=True)
                    .values_list('id', flat=True)[:TASK_CLEANUP_BATCH_SIZE],
                )
                count, _ = DBTaskResult.objects.filter(id__in=task_ids).delete()

            deleted_count += count
            if not delete_all or len(task_ids) < TASK_CLEANUP_BATCH_SIZE:
                break

    return deleted_count


def get_video_rankings(video: VideoModel):
    """只读现有 Redis 排行榜；玩家缓存的纪录必须属于当前录像。"""
    rankings = []
    with SpeedRankingCache.pipeline() as pipe:
        for ranking_name in RANKING_NAMES:
            ranking = SpeedRankingCache(ranking_name)
            pipe.hget(ranking.detail_key, video.player_id)
            for stat in RULES:
                ranking.read_rank(pipe, video.player_id, stat)
        speed_results = iter(pipe.execute())
    for ranking_name in RANKING_NAMES:
        raw = next(speed_results)
        record = json.loads(raw) if raw else {}
        for stat in RULES:
            rank = next(speed_results)
            if record.get(f'{stat}_id') == video.id and rank is not None:
                rankings.append({'ranking': 'saolei', 'stat': stat, 'nf': ranking_name == 'saolei_nf', 'rank': rank + 1})

    if video.level in ('b', 'i', 'e') and video.bv is not None:
        pb = PBRankingCache()
        with SpeedRankingCache.pipeline() as pipe:
            for nf in (False, True):
                pipe.zrank(pb.rank_key(record_field(nf, video.level, video.bv)), member(video.player_id, video.id))
            pb_ranks = pipe.execute()
        for nf, rank in zip((False, True), pb_ranks):
            if rank is not None:
                rankings.append({'ranking': 'pb', 'stat': 'time', 'nf': nf, 'rank': rank + 1})

    if video.level in CUSTOM_PLUCK_LEVELS:
        pluck = PLuckRankingCache(video.level)
        with pluck.client.pipeline() as pipe:
            pipe.zrank(pluck.rank_key, video.player_id)
            pipe.hget(pluck.detail_key, video.player_id)
            rank, raw = pipe.execute()
        if rank is not None and raw and json.loads(raw).get('video_id') == video.id:
            rankings.append({'ranking': 'pluck', 'stat': 'pluck', 'nf': False, 'rank': rank + 1})
    return rankings
