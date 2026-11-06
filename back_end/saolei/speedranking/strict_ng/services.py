from copy import deepcopy
import json
import uuid

from django.db.models import F, QuerySet, Window
from django.db.models.functions import RowNumber

from config.text_choices import MS_TextChoices
from utils.querysets import player_batches
from videomanager.models import VideoModel
from .cache import SpeedRankingCache
from .utils import empty_record, is_better, MINIMUM_BV, plan_strict_ng_record_update, public_record, RANK_STATS, RANKING_NAMES, RankingName, RankStat, RULES, set_stat, TOTAL_PARTS
from ..utils import log_update_errors, upload_microseconds

VIDEO_FIELDS = ('id', 'player_id', 'level', 'mode', 'state', 'ongoing_tournament', 'bv', 'timems', 'bvs', 'right_ce', 'upload_time')


def read_records(pipe, player_ids, ranking_names=RANKING_NAMES, namespace: str = 'speedranking'):
    for ranking_name in ranking_names:
        SpeedRankingCache(ranking_name, namespace=namespace).read_records(pipe, player_ids)


def unpack_records(results, player_ids, ranking_names=RANKING_NAMES):
    records = {}
    for ranking_name, rows in zip(ranking_names, results):
        for player_id, raw in zip(player_ids, rows):
            records[ranking_name, player_id] = json.loads(raw) if raw else empty_record()
    return records


def _read_strict_ng_records(player_ids, ranking_names=RANKING_NAMES, namespace: str = 'speedranking'):
    """用一个 pipeline 读取普通/NF 榜纪录，缺失项按强无猜规则补齐。"""
    player_ids = list(player_ids)
    with SpeedRankingCache.pipeline() as pipe:
        read_records(pipe, player_ids, ranking_names, namespace)
        results = pipe.execute()
    return unpack_records(results, player_ids, ranking_names)


def write_records(pipe, previous, records, namespace: str = 'speedranking', *, force: bool = False):
    """按强无猜规则确定变更，将写入加入共享 pipeline。"""
    for key, record in records.items():
        update = plan_strict_ng_record_update(previous[key], record, force=force)
        if update is not None:
            ranking_name, player_id = key
            payload, scores = update
            ranking = SpeedRankingCache(ranking_name, namespace=namespace)
            ranking.write_record(pipe, player_id, payload)
            for stat, score in scores.items():
                ranking.write_score(pipe, player_id, stat, score)


def _write_strict_ng_records(previous, records, namespace: str = 'speedranking', *, force: bool = False):
    with SpeedRankingCache.pipeline() as pipe:
        write_records(pipe, previous, records, namespace, force=force)
        pipe.execute()


def get_player_records(player_id: int):
    """一次事务读取各榜的个人纪录及从 1 开始的排名，未入榜为 None。"""
    with SpeedRankingCache.pipeline() as pipe:
        for ranking_name in RANKING_NAMES:
            ranking = SpeedRankingCache(ranking_name)
            ranking.read_records(pipe, [player_id])
            for stat in RANK_STATS:
                ranking.read_rank(pipe, player_id, stat)
        results = iter(pipe.execute())
    records = {}
    for ranking_name in RANKING_NAMES:
        raw = next(results)[0]
        record = public_record(player_id, json.loads(raw) if raw else empty_record())
        ranks = [next(results) for stat in RANK_STATS]
        record['ranks'] = {stat: rank + 1 if rank is not None else None for stat, rank in zip(RANK_STATS, ranks)}
        records[ranking_name] = record
    return records


def eligible_videos(videos: QuerySet, ranking_name: str, stat: str):
    level, _ = RULES[stat]
    videos = videos.filter(level=level, bv__isnull=False, mode=MS_TextChoices.Mode.QWC, state=MS_TextChoices.State.OFFICIAL, ongoing_tournament=False)
    if level in MINIMUM_BV:
        videos = videos.filter(bv__gte=MINIMUM_BV[level])
    if ranking_name == 'strict_ng_nf':
        videos = videos.filter(right_ce=0)
    return videos


def candidate_for_video(video: dict | None, ranking_name: str, stat: str):
    if video is None:
        return None
    level, field = RULES[stat]
    if video['level'] != level or video['bv'] is None:
        return None
    if level in MINIMUM_BV and video['bv'] < MINIMUM_BV[level]:
        return None
    if video['mode'] != MS_TextChoices.Mode.QWC or video['state'] != MS_TextChoices.State.OFFICIAL or video['ongoing_tournament']:
        return None
    if ranking_name == 'strict_ng_nf' and video['right_ce'] != 0:
        return None
    return {'id': video['id'], 'value': video[field], 'upload': upload_microseconds(video['upload_time']), 'right_ce': video['right_ce']}


def best_candidate(player_id: int, ranking_name: str, stat: str):
    """仅对需要补位的单项查询最佳录像，upload_time 是唯一成绩 tie-breaker。"""
    field = RULES[stat][1]
    order = field if field == 'timems' else f'-{field}'
    video = eligible_videos(VideoModel.objects.filter(player_id=player_id), ranking_name, stat).order_by(order, 'upload_time', 'id').values(*VIDEO_FIELDS).first()
    return candidate_for_video(video, ranking_name, stat)


def resolve_strict_ng_backfills(requests: set[tuple[str, int, str]]):
    """集中处理补位需求；普通榜最佳录像属于 NF 或为空时，复用到 NF 榜。"""
    grouped = {}
    for ranking_name, player_id, stat in requests:
        grouped.setdefault((player_id, stat), set()).add(ranking_name)
    candidates = {}
    for (player_id, stat), ranking_names in grouped.items():
        if 'strict_ng' in ranking_names:
            candidate = best_candidate(player_id, 'strict_ng', stat)
            candidates['strict_ng', player_id, stat] = candidate
            if 'strict_ng_nf' in ranking_names and (candidate is None or candidate['right_ce'] == 0):
                candidates['strict_ng_nf', player_id, stat] = candidate
                continue
        if 'strict_ng_nf' in ranking_names:
            candidates['strict_ng_nf', player_id, stat] = best_candidate(player_id, 'strict_ng_nf', stat)
    return candidates


def _apply_backfills(records, requests):
    for (ranking_name, player_id, stat), candidate in resolve_strict_ng_backfills(requests).items():
        set_stat(records[ranking_name, player_id], stat, candidate)


def rebuild_player_record(player_id: int, ranking_name: RankingName, stat: RankStat):
    """单项从数据库重建，总项只由缓存中的组成项重算，同时修复排序索引。"""
    with log_update_errors('strict_ng.rebuild_record', player_id=player_id, ranking_name=ranking_name, stat=stat):
        previous = _read_strict_ng_records([player_id], (ranking_name,))
        records = deepcopy(previous)
        record = records[ranking_name, player_id]
        if stat not in TOTAL_PARTS:
            set_stat(record, stat, best_candidate(player_id, ranking_name, stat))
        _write_strict_ng_records(previous, records, force=True)
        return public_record(player_id, record)


def prepare_video_update(video, video_id: int, previous):
    records = deepcopy(previous)
    requests = set()
    for (ranking_name, player_id), record in records.items():
        current_video = video if video and video['player_id'] == player_id else None
        for stat in RULES:
            candidate = candidate_for_video(current_video, ranking_name, stat)
            if record[f'{stat}_id'] == video_id:
                if candidate is None or (not is_better(stat, candidate, record) and (candidate['value'] != record[stat] or candidate['upload'] != record['_uploads'][stat])):
                    requests.add((ranking_name, player_id, stat))
                else:
                    set_stat(record, stat, candidate)
            elif candidate and is_better(stat, candidate, record):
                set_stat(record, stat, candidate)
    _apply_backfills(records, requests)
    return records


def _add_videos(videos: QuerySet, ranking_names=RANKING_NAMES, batch_size: int = 1000, namespace: str = 'speedranking'):
    """按玩家分段，在数据库分桶选最佳录像，再合并到 Redis。"""
    for players in player_batches(videos, batch_size):
        subset = videos.filter(player_id__in=players)
        previous = _read_strict_ng_records(players, ranking_names, namespace)
        records = prepare_add_videos(subset, previous, ranking_names)
        _write_strict_ng_records(previous, records, namespace)


def prepare_add_videos(videos, previous, ranking_names=RANKING_NAMES):
    records = deepcopy(previous)
    for ranking_name in ranking_names:
        for stat, (_, field) in RULES.items():
            order = F(field).asc() if field == 'timems' else F(field).desc()
            best = eligible_videos(videos, ranking_name, stat).annotate(
                rn=Window(RowNumber(), partition_by=[F('player_id')], order_by=[order, F('upload_time').asc(), F('id').asc()]),
            ).filter(rn=1).values(*VIDEO_FIELDS)
            for video in best:
                record = records[ranking_name, video['player_id']]
                candidate = candidate_for_video(video, ranking_name, stat)
                if is_better(stat, candidate, record):
                    set_stat(record, stat, candidate)
    return records


def prepare_remove_videos(ids_by_player, previous):
    records = deepcopy(previous)
    requests = set()
    for (ranking_name, player_id), record in records.items():
        video_ids = ids_by_player.get(player_id, set())
        for stat in RULES:
            if record[f'{stat}_id'] in video_ids:
                requests.add((ranking_name, player_id, stat))
    _apply_backfills(records, requests)
    return records


def rebuild_strict_ng_ranks(ranking_names=RANKING_NAMES, batch_size: int = 1000):
    """从录像库重建临时榜，完成后原子发布；执行期间应暂停录像写入。"""
    if batch_size <= 0:
        raise ValueError('batch_size must be positive')
    counts = {}
    for ranking_name in ranking_names:
        namespace = f'speedranking:rebuild:{uuid.uuid4().hex}'
        temporary = SpeedRankingCache(ranking_name, stats=RANK_STATS, namespace=namespace)
        with log_update_errors('strict_ng.rebuild', ranking_name=ranking_name):
            try:
                _add_videos(VideoModel.objects.all(), ranking_names=(ranking_name,), batch_size=batch_size, namespace=namespace)
                counts[ranking_name] = temporary.get_range('sumt', 0, 0)['count']
                temporary.publish_to(SpeedRankingCache(ranking_name, stats=RANK_STATS))
            finally:
                temporary.flush()
    return counts
