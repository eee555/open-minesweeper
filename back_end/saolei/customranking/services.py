from django.db.models import F, Max, Min, Window
from django.db.models.functions import RowNumber
from django.db.models.query import QuerySet
from django.utils import timezone

from config.customranking import CUSTOM_PLUCK_LEVELS, CUSTOM_PLUCK_MODES
from config.text_choices import MS_TextChoices
from videomanager.models import VideoModel
from .cache import PLuckRankingCache
from .models import CustomPluckRecord


def update_custom_pluck_top_cache(record: CustomPluckRecord | None, level: str, player_id: int):
    """更新或移除单个玩家的 pluck 排行缓存。"""
    ranking_cache = PLuckRankingCache(level)
    if record is not None:
        ranking_cache.add_record(record)
    else:
        ranking_cache.remove_record(player_id)


def sync_custom_pluck_top_cache(player_id: int, level: str):
    """按提交后的当前纪录刷新缓存，兼容同一事务内删除后重建纪录。"""
    record = CustomPluckRecord.objects.filter(player_id=player_id, level=level).first()
    update_custom_pluck_top_cache(record, level, player_id)


def refresh_custom_pluck_rank(player_id: int, level: str):
    """重新计算单个玩家在某个自定义级别下的最佳 pluck 纪录。"""
    video = (
        VideoModel.objects
        .filter(
            player_id=player_id,
            level=level,
            mode__in=CUSTOM_PLUCK_MODES,
            state=MS_TextChoices.State.OFFICIAL,
            ongoing_tournament=False,
            pluck__isnull=False,
        )
        .order_by('pluck', 'timems', 'upload_time')
        .first()
    )

    if video is None:
        CustomPluckRecord.objects.filter(player_id=player_id, level=level).delete()
        return None

    record, _ = CustomPluckRecord.objects.update_or_create(
        player_id=video.player_id,
        level=video.level,
        defaults={
            'video_id': video.id,
            'pluck': video.pluck,
            'timems': video.timems,
            'upload_time': video.upload_time,
        },
    )
    return record


def add_to_custom_pluck_rank(video: VideoModel):
    """尝试将一条录像加入 pluck 排行，并在优于原纪录时刷新玩家纪录。"""
    record, created = CustomPluckRecord.objects.get_or_create(
        player=video.player,
        level=video.level,
        defaults={
            'video': video,
            'pluck': video.pluck,
            'timems': video.timems,
            'upload_time': video.upload_time,
        },
    )
    if not created:
        if record.video_id == video.id:
            return refresh_custom_pluck_rank(video.player_id, video.level)
        record.add_video(video)
    return record


def add_videos_to_custom_pluck_ranks(videos: QuerySet[VideoModel]):
    """将一批录像按 (player, level) 分组后，把每组最佳录像吸收到 pluck 个人纪录。"""
    best_videos = (
        videos
        .filter(
            level__in=CUSTOM_PLUCK_LEVELS,
            mode__in=CUSTOM_PLUCK_MODES,
            state=MS_TextChoices.State.OFFICIAL,
            ongoing_tournament=False,
            pluck__isnull=False,
        )
        .annotate(
            rn=Window(
                expression=RowNumber(),
                partition_by=[F('player_id'), F('level')],
                order_by=[F('pluck').asc(), F('timems').asc(), F('upload_time').asc()],
            ),
        )
        .filter(rn=1)
    )

    count = 0
    for video in best_videos.iterator(chunk_size=1000):
        add_to_custom_pluck_rank(video)
        count += 1

    return count


def remove_videos_from_custom_pluck_ranks(video_ids: set[int]):
    """移除一批录像对 pluck 个人纪录的影响，并刷新受影响的 (player, level)。"""
    if not video_ids:
        return 0

    records = list(CustomPluckRecord.objects.filter(video_id__in=video_ids))
    for record in records:
        refresh_custom_pluck_rank(record.player_id, record.level)

    return len(records)


def remove_from_custom_pluck_rank(video: VideoModel):
    """从 pluck 排行中移除录像影响，并用该玩家剩余录像重新计算纪录。"""
    if video.level not in CUSTOM_PLUCK_LEVELS:
        return None
    return refresh_custom_pluck_rank(video.player_id, video.level)


def refresh_custom_pluck_rank_range(startid: int, endid: int):
    """逐条确认并刷新指定玩家 id 闭区间内的自定义 pluck 排行数据库纪录。"""
    refresh_started_at = timezone.now()

    best_videos = (
        VideoModel.objects
        .filter(
            player_id__gte=startid,
            player_id__lte=endid,
            level__in=CUSTOM_PLUCK_LEVELS,
            mode__in=CUSTOM_PLUCK_MODES,
            state=MS_TextChoices.State.OFFICIAL,
            ongoing_tournament=False,
            pluck__isnull=False,
        )
        .annotate(
            rn=Window(
                expression=RowNumber(),
                partition_by=[F('player_id'), F('level')],
                order_by=[F('pluck').asc(), F('timems').asc(), F('upload_time').asc()],
            ),
        )
        .filter(rn=1)
    )

    error_list = []
    success_count = 0
    for video in best_videos.iterator(chunk_size=1000):
        try:
            CustomPluckRecord.objects.update_or_create(
                player_id=video.player_id,
                level=video.level,
                defaults={
                    'video_id': video.id,
                    'pluck': video.pluck,
                    'timems': video.timems,
                    'upload_time': video.upload_time,
                },
            )
            success_count += 1
        except Exception:
            error_list.append(video.player_id)

    stale_records = CustomPluckRecord.objects.filter(
        player_id__gte=startid,
        player_id__lte=endid,
        updated_at__lt=refresh_started_at,
    )
    if error_list:
        stale_records = stale_records.exclude(player_id__in=error_list)
    stale_records.delete()

    return {
        'errorList': error_list,
        'successCount': success_count,
    }


def refresh_all_custom_pluck_ranks(player_batch_size: int = 1000):
    """按玩家 id 分段逐条确认并刷新全部自定义 pluck 排行数据库纪录。"""
    if player_batch_size <= 0:
        raise ValueError('player_batch_size must be positive')

    base_videos = (
        VideoModel.objects
        .filter(
            level__in=CUSTOM_PLUCK_LEVELS,
            mode__in=CUSTOM_PLUCK_MODES,
            state=MS_TextChoices.State.OFFICIAL,
            ongoing_tournament=False,
            pluck__isnull=False,
        )
    )
    player_bounds = base_videos.aggregate(
        min_player_id=Min('player_id'),
        max_player_id=Max('player_id'),
    )
    min_player_id = player_bounds['min_player_id']
    max_player_id = player_bounds['max_player_id']

    count = 0
    if min_player_id is not None and max_player_id is not None:
        player_id_start = min_player_id
        while player_id_start <= max_player_id:
            player_id_end = player_id_start + player_batch_size - 1
            result = refresh_custom_pluck_rank_range(player_id_start, player_id_end)
            count += result['successCount']
            player_id_start = player_id_end + 1

    return count


def rebuild_custom_pluck_cache(levels=None, batch_size: int = 1000):
    """用数据库中的 CustomPluckRecord 全量重建 Redis 排行缓存。"""
    if batch_size <= 0:
        raise ValueError('batch_size must be positive')

    levels = CUSTOM_PLUCK_LEVELS if levels is None else levels
    counts = {}
    for level in levels:
        ranking_cache = PLuckRankingCache(level)
        ranking_cache.flush()

        batch = []
        count = 0
        records = (
            CustomPluckRecord.objects
            .filter(level=level)
            .select_related('video')
            .order_by('pluck', 'timems', 'upload_time')
            .iterator(chunk_size=batch_size)
        )
        for record in records:
            batch.append(record)
            if len(batch) < batch_size:
                continue
            ranking_cache.add_record_batch(batch)
            count += len(batch)
            batch = []

        if batch:
            ranking_cache.add_record_batch(batch)
            count += len(batch)
        counts[level] = count

    return counts
