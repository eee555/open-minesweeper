from copy import deepcopy
from sys import float_info
import uuid

from django.db.models import F, Q, QuerySet, Window
from django.db.models.functions import RowNumber

from config.text_choices import MS_TextChoices
from utils.querysets import player_batches
from videomanager.models import VideoModel
from .cache import PathRankingCache
from .utils import candidate_for_video, empty_record, is_better, LEVELS, METRICS, RankStat, RECORD_FIELDS, record_scores, STAT_PARTS
from ..utils import log_update_errors

VIDEO_FIELDS = ('id', 'player_id', 'level', 'mode', 'state', 'ongoing_tournament', *METRICS)


def eligible_videos(videos: QuerySet):
    return videos.filter(level__in=LEVELS, mode=MS_TextChoices.Mode.STD, state=MS_TextChoices.State.OFFICIAL, ongoing_tournament=False)


def metric_videos(videos: QuerySet, metric: str):
    return eligible_videos(videos).filter(**{f'{metric}__gte': 0, f'{metric}__lte': float_info.max})


def best_candidate(player_id: int, level: str, metric: str):
    video = metric_videos(VideoModel.objects.filter(player_id=player_id, level=level), metric).order_by(metric, 'id').values('id', metric).first()
    return {'value': video[metric], 'video_id': video['id']} if video else None


def best_videos(videos: QuerySet, metric: str):
    return metric_videos(videos, metric).order_by().annotate(
        rn=Window(RowNumber(), partition_by=[F('player_id'), F('level')], order_by=[F(metric).asc(), F('id').asc()]),
    ).filter(rn=1).values('id', 'player_id', 'level', metric)


def prepare_video_update(video: dict | None, video_id: int, previous: dict):
    records = deepcopy(previous)
    candidates = {metric: candidate_for_video(video, metric) for metric in METRICS}
    for player_id, record in records.items():
        for stat in RECORD_FIELDS:
            level, metric = STAT_PARTS[stat]
            current = candidates[metric] if video and video['player_id'] == player_id and video['level'] == level else None
            part = record[stat]
            if part is not None and part['video_id'] == video_id:
                record[stat] = best_candidate(player_id, level, metric) if current is None or is_better(part, current) else current
            elif current is not None and is_better(current, part):
                record[stat] = current
    return records


def prepare_add_videos(videos: QuerySet, previous: dict):
    records = deepcopy(previous)
    for metric in METRICS:
        for video in best_videos(videos, metric).iterator(chunk_size=1000):
            stat = f'{video["level"]}_{metric}'
            candidate = {'value': video[metric], 'video_id': video['id']}
            if is_better(candidate, records[video['player_id']][stat]):
                records[video['player_id']][stat] = candidate
    return records


def prepare_remove_videos(videos: QuerySet, previous: dict):
    records = deepcopy(previous)
    held_ids = {part['video_id'] for record in previous.values() for part in record.values() if part is not None}
    removed_ids = set(videos.filter(id__in=held_ids).values_list('id', flat=True)) if held_ids else set()
    if not removed_ids:
        return records
    for metric in METRICS:
        query = Q()
        for level in LEVELS:
            players = []
            stat = f'{level}_{metric}'
            for player_id, record in records.items():
                part = record[stat]
                if part is not None and part['video_id'] in removed_ids:
                    players.append(player_id)
                    record[stat] = None
            if players:
                query |= Q(player_id__in=players, level=level)
        if query:
            for video in best_videos(VideoModel.objects.filter(query), metric):
                records[video['player_id']][f'{video["level"]}_{metric}'] = {'value': video[metric], 'video_id': video['id']}
    return records


def write_records(ranking: PathRankingCache, previous: dict, records: dict, force_stats: set[str] | None = None, pipe=None):
    changes = []
    for player_id, record in records.items():
        if record == previous[player_id] and not force_stats:
            continue
        old_scores = record_scores(previous[player_id])
        scores = record_scores(record)
        changes.append((player_id, record, {stat: score for stat, score in scores.items() if score != old_scores[stat] or stat in (force_stats or ())}))
    ranking.write_changes(changes, pipe)


def rebuild_player_record(player_id: int, stat: RankStat):
    with log_update_errors('path.rebuild_record', player_id=player_id, stat=stat):
        ranking = PathRankingCache()
        previous = ranking.read_records([player_id])
        records = deepcopy(previous)
        level, metric = STAT_PARTS[stat]
        if level in LEVELS:
            records[player_id][stat] = best_candidate(player_id, level, metric)
        write_records(ranking, previous, records, {stat, f'sum_{metric}'})
        return {'player_id': player_id, **records[player_id]}


def rebuild_path_ranks(batch_size: int = 1000):
    if batch_size <= 0:
        raise ValueError('batch_size must be positive')
    ranking = PathRankingCache(f'effranking:rebuild:{uuid.uuid4().hex}')
    count = 0
    with log_update_errors('path.rebuild', batch_size=batch_size):
        try:
            videos = VideoModel.objects.all()
            for players in player_batches(eligible_videos(videos), batch_size):
                previous = {player_id: empty_record() for player_id in players}
                records = prepare_add_videos(videos.filter(player_id__in=players), previous)
                write_records(ranking, previous, records)
                count += sum(any(part is not None for part in record.values()) for record in records.values())
            ranking.publish_to(PathRankingCache())
        finally:
            ranking.flush()
    return count
