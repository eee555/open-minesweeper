"""PB 衍生成绩的重算、修复与全量重建。

正常链路只由根 speedranking.services 的 old_pb + pb_changes 触发；不新增
VideoModel receiver，也不在 PB 刷新 rank 时递归重算其他用户。
"""
from .cache import PBDerivedCache
from .utils import compute, defaults, FIELDS, LEVELS, RANKINGS
from ..cache import cache, pipeline
from ..pb.cache import PBRankingCache
from ..pb.utils import parse_field, record_from_score
from ..utils import log_update_errors


def pb_values(records):
    values = {}
    for field, record in records.items():
        nf, level, bv = parse_field(field)
        if level in LEVELS:
            values[nf, level, bv] = record['timems']
    return values


def compute_for_records(records):
    return compute(pb_values(records))


def prepare_changes(old_pb, pb_changes):
    """将本批 PB 变更覆盖到完整 PB 映射，每个受影响用户只重算一次。"""
    affected = {}
    for (player_id, field), candidate in pb_changes.items():
        affected.setdefault(player_id, {})[field] = candidate
    changes = {}
    for player_id, replacements in affected.items():
        records = dict(old_pb.get(player_id, {}))
        for field, candidate in replacements.items():
            if candidate is None:
                records.pop(field, None)
            else:
                video_id, pb_score = candidate
                records[field] = record_from_score(video_id, pb_score)
        changes[player_id] = compute_for_records(records)
    return changes


def read_pb_records(player_id: int):
    ranking = PBRankingCache()
    raw = cache.hgetall(ranking.player_key(player_id))
    return ranking.unpack_records([raw], [player_id])[player_id]


def rebuild_player(player_id: int, force=True):
    """修复后完整读取该用户的 PB hash 再重算，force 可补回丢失的索引。"""
    changes = compute_for_records(read_pb_records(player_id))
    derived = PBDerivedCache()
    previous = {} if force else {player_id: derived.get_records(player_id)}
    with pipeline() as pipe:
        derived.write_changes(pipe, previous, {player_id: changes}, force=force)
        pipe.execute()
    return changes


def remove_player(player_id: int):
    with pipeline() as pipe:
        PBDerivedCache().remove_player(pipe, player_id)
        pipe.execute()


def player_summary(player_id: int):
    """三个大榜的完整成绩及排名；未入榜类别补缺省展示值、排名置空。"""
    derived = PBDerivedCache()
    records = derived.get_records(player_id)
    ranks = derived.get_player_ranks(player_id)
    fallback = defaults()
    for ranking in RANKINGS:
        for field in FIELDS[ranking]:
            if field not in records[ranking]:
                records[ranking][field] = fallback[ranking][field]
                ranks[ranking][field] = None
    return {'records': records, 'ranks': ranks}


def _player_id_from_key(key):
    value = key.decode() if isinstance(key, bytes) else key
    return int(value.rsplit(':', 1)[1])


def _rebuild_batch(keys, derived, ranking):
    with pipeline() as pipe:
        for key in keys:
            pipe.hgetall(key)
        rows = pipe.execute()
    changes = {}
    for key, raw in zip(keys, rows):
        player_id = _player_id_from_key(key)
        records = ranking.unpack_records([raw], [player_id])[player_id]
        changes[player_id] = compute_for_records(records)
    with pipeline() as pipe:
        derived.write_changes(pipe, {}, changes)
        pipe.execute()
    return len(changes)


def rebuild_all(batch_size=100, progress=None):
    """清空后从现有 PB 用户 hash 全量重建，不重新扫描录像。

    失败会记录异常并中断，缓存可能只完成一部分，此时必须重跑本函数。
    """
    if batch_size <= 0:
        raise ValueError('batch_size must be positive')
    derived = PBDerivedCache()
    ranking = PBRankingCache()
    count = 0
    with log_update_errors('pb_derived.rebuild', batch_size=batch_size):
        derived.flush()
        keys = []
        for key in cache.scan_iter(match=f'{ranking.prefix}:player:*'):
            keys.append(key)
            if len(keys) < batch_size:
                continue
            count += _rebuild_batch(keys, derived, ranking)
            if progress:
                progress(count)
            keys.clear()
        if keys:
            count += _rebuild_batch(keys, derived, ranking)
            if progress:
                progress(count)
    return count
