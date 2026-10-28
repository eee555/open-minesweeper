from copy import deepcopy
import uuid

from django.db.models import F, QuerySet, Window
from django.db.models.functions import RowNumber

from config.text_choices import MS_TextChoices
from utils.querysets import player_batches
from videomanager.models import VideoModel
from .cache import ThrpRankingCache
from .nf_services import refresh_expert_nf_records
from .utils import candidate_for_video, empty_record, is_better, LEVELS, NF_STAT, RankStat, record_scores
from ..utils import log_update_errors

VIDEO_FIELDS = ('id', 'player_id', 'level', 'mode', 'state', 'ongoing_tournament', 'right_ce', 'thrp', 'upload_time')


def eligible_videos(videos: QuerySet):
    return videos.filter(level__in=LEVELS, mode=MS_TextChoices.Mode.STD, state=MS_TextChoices.State.OFFICIAL, ongoing_tournament=False, thrp__isnull=False)


def best_candidate(player_id: int, level: str):
    """只查询需要补位的玩家和级别。"""
    video = eligible_videos(VideoModel.objects.filter(player_id=player_id, level=level)).order_by('-thrp', 'upload_time', 'id').values(*VIDEO_FIELDS).first()
    return candidate_for_video(video)


def write_records(ranking: ThrpRankingCache, previous: dict, records: dict, force_stats: set[str] | None = None):
    """先计算变动，再一次写入原始纪录及需要刷新的小榜。"""
    changes = []
    for player_id, record in records.items():
        if record == previous[player_id] and not force_stats:
            continue
        old_scores = record_scores(previous[player_id])
        scores = record_scores(record)
        changed = {stat: score for stat, score in scores.items() if score != old_scores[stat] or stat in (force_stats or ())}
        changes.append((player_id, record, changed))
    if not changes:
        return
    with ranking.pipeline() as pipe:
        for player_id, record, scores in changes:
            ranking.write_record(pipe, player_id, record)
            for stat, score in scores.items():
                ranking.write_score(pipe, player_id, stat, score)
        pipe.execute()


def prepare_video_update(video: dict | None, video_id: int, previous: dict):
    """改善直接比较；原纪录失效或变差时才查询数据库补位。"""
    records = deepcopy(previous)
    candidate = candidate_for_video(video)
    for player_id, record in records.items():
        for level in LEVELS:
            current = candidate if video and video['player_id'] == player_id and video['level'] == level else None
            part = record[level]
            if part is not None and part['video_id'] == video_id:
                record[level] = best_candidate(player_id, level) if current is None or is_better(part, current) else current
            elif current is not None and is_better(current, part):
                record[level] = current
    return records


def prepare_add_videos(videos: QuerySet, previous: dict):
    """按玩家和级别在数据库分桶取最佳，再吸收到个人纪录。"""
    records = deepcopy(previous)
    best = eligible_videos(videos).annotate(
        rn=Window(RowNumber(), partition_by=[F('player_id'), F('level')], order_by=[F('thrp').desc(), F('upload_time').asc(), F('id').asc()]),
    ).filter(rn=1).values(*VIDEO_FIELDS)
    for video in best.iterator(chunk_size=1000):
        candidate = candidate_for_video(video)
        record = records[video['player_id']]
        if candidate is not None and is_better(candidate, record[video['level']]):
            record[video['level']] = candidate
    return records


def prepare_remove_videos(videos: QuerySet, previous: dict):
    """只定位这批录像保持的纪录，不加载每个玩家全部录像 id。"""
    records = deepcopy(previous)
    held_ids = {part['video_id'] for record in previous.values() for level in LEVELS if (part := record[level]) is not None}
    removed_ids = set(videos.filter(id__in=held_ids).values_list('id', flat=True)) if held_ids else set()
    for player_id, record in records.items():
        for level in LEVELS:
            part = record[level]
            if part is not None and part['video_id'] in removed_ids:
                record[level] = best_candidate(player_id, level)
    return records


def rebuild_player_record(player_id: int, stat: RankStat):
    """单项回源修复，sum 只使用缓存中三项的原始值重算。"""
    with log_update_errors('thrp.rebuild_record', player_id=player_id, stat=stat):
        ranking = ThrpRankingCache()
        previous = ranking.read_records([player_id])
        records = deepcopy(previous)
        if stat in LEVELS:
            records[player_id][stat] = best_candidate(player_id, stat)
        elif stat == NF_STAT:
            refresh_expert_nf_records(records, [player_id])
        write_records(ranking, previous, records, {stat} if stat == NF_STAT else {stat, 'sum'})
        return {'player_id': player_id, **records[player_id]}


def rebuild_thrp_ranks(batch_size: int = 1000):
    """按玩家分段构建临时榜，成功后原子发布，不先清空正式榜。"""
    if batch_size <= 0:
        raise ValueError('batch_size must be positive')
    ranking = ThrpRankingCache(f'effranking:rebuild:{uuid.uuid4().hex}')
    count = 0
    with log_update_errors('thrp.rebuild', batch_size=batch_size):
        try:
            videos = eligible_videos(VideoModel.objects.all())
            for players in player_batches(videos, batch_size):
                previous = {player_id: empty_record() for player_id in players}
                records = prepare_add_videos(videos.filter(player_id__in=players), previous)
                refresh_expert_nf_records(records, players)
                write_records(ranking, previous, records)
                count += sum(any(part is not None for part in record.values()) for record in records.values())
            ranking.publish_to(ThrpRankingCache())
        finally:
            ranking.flush()
    return count
