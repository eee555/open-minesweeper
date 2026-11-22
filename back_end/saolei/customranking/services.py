from functools import partial
from itertools import batched

from django.db import transaction
from django.db.models import F, Q, Window
from django.db.models.functions import RowNumber
from django.db.models.query import QuerySet

from config.customranking import CUSTOM_PLUCK_LEVELS, CUSTOM_PLUCK_MODES
from config.text_choices import MS_TextChoices
from utils.querysets import player_batches
from videomanager.models import VideoModel
from .cache import PLuckRankingCache, read_records
from .utils import log_update_errors

VIDEO_FIELDS = ('id', 'player_id', 'level', 'mode', 'state', 'ongoing_tournament', 'pluck', 'timems', 'upload_time')


def eligible_videos(videos):
    return videos.filter(
        level__in=CUSTOM_PLUCK_LEVELS, mode__in=CUSTOM_PLUCK_MODES,
        state=MS_TextChoices.State.OFFICIAL, ongoing_tournament=False, pluck__isnull=False,
    ).select_related(None).only(*VIDEO_FIELDS)


def best_videos(videos):
    return eligible_videos(videos).order_by().annotate(
        rn=Window(
            expression=RowNumber(), partition_by=[F('player_id'), F('level')],
            order_by=[F('pluck').asc(), F('timems').asc(), F('upload_time').asc()],
        ),
    ).filter(rn=1)


def is_eligible(video):
    return (
        video is not None and video.level in CUSTOM_PLUCK_LEVELS and video.mode in CUSTOM_PLUCK_MODES
        and video.state == MS_TextChoices.State.OFFICIAL and not video.ongoing_tournament and video.pluck is not None
    )


def better_than(video, record):
    return record is None or (video.pluck, video.timems, video.upload_time) < (record['pluck'], record['timems'], record['upload_time'])


def _write_records(records):
    if not records:
        return
    with PLuckRankingCache.pipeline() as pipe:
        for level in CUSTOM_PLUCK_LEVELS:
            ranking = PLuckRankingCache(level)
            videos = []
            for (player_id, record_level), video in records.items():
                if record_level != level:
                    continue
                if video is None:
                    ranking.remove_record(player_id, pipe=pipe)
                else:
                    videos.append(video)
            ranking.add_record_batch(videos, pipe=pipe)
        pipe.execute()


def _replacement_records(categories):
    records = dict.fromkeys(categories)
    if not records:
        return records
    query = Q()
    for level in CUSTOM_PLUCK_LEVELS:
        players = [player for player, category_level in records if category_level == level]
        if players:
            query |= Q(player_id__in=players, level=level)
    for video in best_videos(VideoModel.objects.filter(query)):
        records[video.player_id, video.level] = video
    return records


def _sync_video(video_id, previous_category):
    with log_update_errors('sync_video', video_id=video_id, previous_category=previous_category):
        video = VideoModel.objects.only(*VIDEO_FIELDS).filter(pk=video_id).first()
        category = (video.player_id, video.level) if video is not None else None
        categories = {item for item in (previous_category, category) if item is not None and item[1] in CUSTOM_PLUCK_LEVELS}
        previous = read_records(categories)
        replacements = set()
        for key, record in previous.items():
            if record is None or record['video_id'] != video_id:
                continue
            if key != category or not is_eligible(video) or (video.pluck, video.timems, video.upload_time) > (record['pluck'], record['timems'], record['upload_time']):
                replacements.add(key)
        updates = _replacement_records(replacements)
        if is_eligible(video) and category not in replacements and better_than(video, previous.get(category)):
            updates[category] = video
        _write_records(updates)


def sync_video(video_id: int, previous_category: tuple[int, str], *, using=None):
    transaction.on_commit(partial(_sync_video, video_id, previous_category), using=using, robust=True)


def _update_videos(videos, remove):
    with log_update_errors('remove_videos' if remove else 'add_videos'):
        videos = videos.filter(level__in=CUSTOM_PLUCK_LEVELS)
        for players in player_batches(videos, 100):
            subset = videos.filter(player_id__in=players)
            if remove:
                rows = list(subset.values_list('id', 'player_id', 'level'))
                previous = read_records({(player, level) for _, player, level in rows})
                video_ids = {pk for pk, _, _ in rows}
                categories = {key for key, record in previous.items() if record is not None and record['video_id'] in video_ids}
                updates = _replacement_records(categories)
            else:
                candidates = list(best_videos(subset))
                previous = read_records({(video.player_id, video.level) for video in candidates})
                updates = {}
                for video in candidates:
                    key = (video.player_id, video.level)
                    if better_than(video, previous[key]):
                        updates[key] = video
            _write_records(updates)


def add_videos_to_custom_pluck_ranks(videos: QuerySet[VideoModel]):
    """提交后分组吸收录像；queryset 应使用固定 id 或稳定的范围。"""
    transaction.on_commit(partial(_update_videos, videos.all(), False), using=videos.db, robust=True)


def remove_videos_from_custom_pluck_ranks(videos: QuerySet[VideoModel]):
    """批量失效后的补位，传入固定录像 id 定位、仍有录像行的 queryset。"""
    transaction.on_commit(partial(_update_videos, videos.all(), True), using=videos.db, robust=True)


def refresh_custom_pluck_rank_range(startid: int, endid: int):
    """重算玩家 id 闭区间；也清除区间内已无候选的缓存纪录。"""
    with log_update_errors('refresh_range', startid=startid, endid=endid):
        records = {}
        # 管理员修复需同时扫描两侧，才能清掉半缺失和已删用户的陈旧项。
        with PLuckRankingCache.pipeline() as pipe:
            for level in CUSTOM_PLUCK_LEVELS:
                ranking = PLuckRankingCache(level)
                pipe.zrange(ranking.rank_key, 0, -1)
                pipe.hkeys(ranking.detail_key)
            cached = pipe.execute()
        for index, level in enumerate(CUSTOM_PLUCK_LEVELS):
            for member in cached[index * 2] + cached[index * 2 + 1]:
                player_id = int(member)
                if startid <= player_id <= endid:
                    records.setdefault(player_id, {})[player_id, level] = None
        for video in best_videos(VideoModel.objects.filter(player_id__gte=startid, player_id__lte=endid)):
            records.setdefault(video.player_id, {})[video.player_id, video.level] = video

        errors = []
        count = 0
        for player_id, updates in records.items():
            try:
                with log_update_errors('refresh_player', player_id=player_id):
                    _write_records(updates)
                count += sum(video is not None for video in updates.values())
            except Exception:
                errors.append(player_id)
        return {'errorList': errors, 'successCount': count}


def rebuild_custom_pluck_cache(levels=None, batch_size: int = 1000):
    """直接从录像库重建排行；仅主动修复时使用，不在部署时自动调用。"""
    if batch_size <= 0:
        raise ValueError('batch_size must be positive')
    levels = CUSTOM_PLUCK_LEVELS if levels is None else levels
    counts = {}
    with log_update_errors('rebuild'):
        for level in levels:
            ranking = PLuckRankingCache(level)
            ranking.flush()
            count = 0
            videos = best_videos(VideoModel.objects.filter(level=level)).iterator(chunk_size=batch_size)
            for batch in batched(videos, batch_size):
                ranking.add_record_batch(batch)
                count += len(batch)
            counts[level] = count
    return counts
