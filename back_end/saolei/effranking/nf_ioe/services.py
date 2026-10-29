from copy import deepcopy
import uuid

from django.db.models import Case, F, FloatField, QuerySet, Value, When, Window
from django.db.models.functions import RowNumber

from config.text_choices import MS_TextChoices
from utils.querysets import player_batches
from videomanager.models import VideoModel
from .cache import NFIOERankingCache
from .utils import candidate_for_video, empty_record, is_better, LEVELS, MAX_TIMEMS, RankStat, record_scores
from ..utils import log_update_errors

VIDEO_FIELDS = ('id', 'player_id', 'level', 'mode', 'state', 'ongoing_tournament', 'right_ce', 'ioe', 'timems')


def eligible_videos(videos: QuerySet):
    return videos.filter(level__in=LEVELS, mode=MS_TextChoices.Mode.STD, state=MS_TextChoices.State.OFFICIAL, ongoing_tournament=False, right_ce=0, ioe__isnull=False)


def ranked_videos(videos: QuerySet):
    return eligible_videos(videos).annotate(
        ranking_score=Case(When(ioe=1, then=Value(1 + MAX_TIMEMS) - F('timems')), default=F('ioe'), output_field=FloatField()),
    )


def best_candidate(player_id: int, level: str):
    video = ranked_videos(VideoModel.objects.filter(player_id=player_id, level=level)).order_by('-ranking_score', 'id').values(*VIDEO_FIELDS).first()
    return candidate_for_video(video)


def prepare_video_update(video: dict | None, video_id: int, previous: dict):
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
    records = deepcopy(previous)
    best = ranked_videos(videos).annotate(
        rn=Window(RowNumber(), partition_by=[F('player_id'), F('level')], order_by=[F('ranking_score').desc(), F('id').asc()]),
    ).filter(rn=1).values(*VIDEO_FIELDS)
    for video in best.iterator(chunk_size=1000):
        candidate = candidate_for_video(video)
        record = records[video['player_id']]
        if candidate is not None and is_better(candidate, record[video['level']]):
            record[video['level']] = candidate
    return records


def prepare_remove_videos(videos: QuerySet, previous: dict):
    records = deepcopy(previous)
    held_ids = {part['video_id'] for record in previous.values() for part in record.values() if part is not None}
    removed_ids = set(videos.filter(id__in=held_ids).values_list('id', flat=True)) if held_ids else set()
    for player_id, record in records.items():
        for level, part in record.items():
            if part is not None and part['video_id'] in removed_ids:
                record[level] = best_candidate(player_id, level)
    return records


def write_records(ranking: NFIOERankingCache, previous: dict, records: dict, force_stats: set[str] | None = None, pipe=None):
    changes = []
    for player_id, record in records.items():
        if record == previous[player_id] and not force_stats:
            continue
        old_scores = record_scores(previous[player_id])
        scores = record_scores(record)
        changes.append((player_id, record, {stat: score for stat, score in scores.items() if score != old_scores[stat] or stat in (force_stats or ())}))
    ranking.write_changes(changes, pipe)


def rebuild_player_record(player_id: int, stat: RankStat):
    with log_update_errors('nf_ioe.rebuild_record', player_id=player_id, stat=stat):
        ranking = NFIOERankingCache()
        previous = ranking.read_records([player_id])
        records = deepcopy(previous)
        if stat in LEVELS:
            records[player_id][stat] = best_candidate(player_id, stat)
        write_records(ranking, previous, records, {stat, 'sum'})
        return {'player_id': player_id, **records[player_id]}


def rebuild_nf_ioe_ranks(batch_size: int = 1000):
    if batch_size <= 0:
        raise ValueError('batch_size must be positive')
    ranking = NFIOERankingCache(f'effranking:rebuild:{uuid.uuid4().hex}')
    count = 0
    with log_update_errors('nf_ioe.rebuild', batch_size=batch_size):
        try:
            videos = eligible_videos(VideoModel.objects.all())
            for players in player_batches(videos, batch_size):
                previous = {player_id: empty_record() for player_id in players}
                records = prepare_add_videos(videos.filter(player_id__in=players), previous)
                write_records(ranking, previous, records)
                count += sum(any(part is not None for part in record.values()) for record in records.values())
            ranking.publish_to(NFIOERankingCache())
        finally:
            ranking.flush()
    return count
