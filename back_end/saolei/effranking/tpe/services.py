from copy import deepcopy
import uuid

from django.db.models import ExpressionWrapper, F, FloatField, Q, QuerySet, Value, Window
from django.db.models.functions import Power, RowNumber

from config.text_choices import MS_TextChoices
from utils.querysets import player_batches
from videomanager.models import VideoModel
from .cache import TPERankingCache
from .utils import candidate_for_video, empty_record, is_better, LEVELS, POWERS, RankStat, RECORD_FIELDS, record_scores, STAT_PARTS
from ..utils import log_update_errors

VIDEO_FIELDS = ('id', 'player_id', 'level', 'mode', 'state', 'ongoing_tournament', 'ioe', 'timems')


def eligible_videos(videos: QuerySet):
    return videos.filter(
        level__in=LEVELS, mode=MS_TextChoices.Mode.STD,
        state=MS_TextChoices.State.OFFICIAL, ongoing_tournament=False, ioe__gt=0,
    )


def tpe_expression(power: int):
    denominator = F('ioe') if power == 1 else Power(F('ioe'), power)
    return ExpressionWrapper(F('timems') / denominator / Value(1000.0), output_field=FloatField())


def ranked_videos(videos: QuerySet, power: int = 1):
    return eligible_videos(videos).annotate(tpe_value=tpe_expression(power))


def best_candidate(player_id: int, level: str, power: int = 1):
    video = ranked_videos(VideoModel.objects.filter(player_id=player_id, level=level), power).order_by('tpe_value', 'id').values('id', 'tpe_value').first()
    return {'value': video['tpe_value'], 'video_id': video['id']} if video else None


def prepare_video_update(video: dict | None, video_id: int, previous: dict):
    records = deepcopy(previous)
    candidates = {power: candidate_for_video(video, power) for power in POWERS.values()}
    for player_id, record in records.items():
        for stat in RECORD_FIELDS:
            level, power = STAT_PARTS[stat]
            current = candidates[power] if video and video['player_id'] == player_id and video['level'] == level else None
            part = record[stat]
            if part is not None and part['video_id'] == video_id:
                record[stat] = best_candidate(player_id, level, power) if current is None or is_better(part, current) else current
            elif current is not None and is_better(current, part):
                record[stat] = current
    return records


def prepare_add_videos(videos: QuerySet, previous: dict):
    records = deepcopy(previous)
    best = eligible_videos(videos).annotate(**{f'tpe_{power}': tpe_expression(power) for power in POWERS.values()})
    best = best.annotate(**{
        f'rn_{power}': Window(RowNumber(), partition_by=[F('player_id'), F('level')], order_by=[F(f'tpe_{power}').asc(), F('id').asc()])
        for power in POWERS.values()
    }).filter(Q(rn_1=1) | Q(rn_2=1) | Q(rn_3=1)).order_by().values(
        'id', 'player_id', 'level', *[f'tpe_{power}' for power in POWERS.values()], *[f'rn_{power}' for power in POWERS.values()],
    )
    for video in best.iterator(chunk_size=1000):
        record = records[video['player_id']]
        for suffix, power in POWERS.items():
            if video[f'rn_{power}'] != 1:
                continue
            stat = f'{video["level"]}{suffix}'
            candidate = {'value': video[f'tpe_{power}'], 'video_id': video['id']}
            if is_better(candidate, record[stat]):
                record[stat] = candidate
    return records


def prepare_remove_videos(videos: QuerySet, previous: dict):
    records = deepcopy(previous)
    held_ids = {part['video_id'] for record in previous.values() for part in record.values() if part is not None}
    removed_ids = set(videos.filter(id__in=held_ids).values_list('id', flat=True)) if held_ids else set()
    for player_id, record in records.items():
        for stat, part in record.items():
            if part is not None and part['video_id'] in removed_ids:
                level, power = STAT_PARTS[stat]
                record[stat] = best_candidate(player_id, level, power)
    return records


def write_records(ranking: TPERankingCache, previous: dict, records: dict, force_stats: set[str] | None = None, pipe=None):
    changes = []
    for player_id, record in records.items():
        if record == previous[player_id] and not force_stats:
            continue
        old_scores = record_scores(previous[player_id])
        scores = record_scores(record)
        changes.append((player_id, record, {stat: score for stat, score in scores.items() if score != old_scores[stat] or stat in (force_stats or ())}))
    ranking.write_changes(changes, pipe)


def rebuild_player_record(player_id: int, stat: RankStat):
    with log_update_errors('tpe.rebuild_record', player_id=player_id, stat=stat):
        ranking = TPERankingCache()
        previous = ranking.read_records([player_id])
        records = deepcopy(previous)
        level, power = STAT_PARTS[stat]
        sum_stat = stat
        if level in LEVELS:
            records[player_id][stat] = best_candidate(player_id, level, power)
            sum_stat = f'sum{stat[1:]}'
        write_records(ranking, previous, records, {stat, sum_stat})
        return {'player_id': player_id, **records[player_id]}


def rebuild_tpe_ranks(batch_size: int = 1000):
    if batch_size <= 0:
        raise ValueError('batch_size must be positive')
    ranking = TPERankingCache(f'effranking:rebuild:{uuid.uuid4().hex}')
    count = 0
    with log_update_errors('tpe.rebuild', batch_size=batch_size):
        try:
            videos = VideoModel.objects.all()
            for players in player_batches(eligible_videos(videos), batch_size):
                previous = {player_id: empty_record() for player_id in players}
                records = prepare_add_videos(videos.filter(player_id__in=players), previous)
                write_records(ranking, previous, records)
                count += sum(any(part is not None for part in record.values()) for record in records.values())
            ranking.publish_to(TPERankingCache())
        finally:
            ranking.flush()
    return count
