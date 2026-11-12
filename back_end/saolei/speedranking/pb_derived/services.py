"""PB 衍生成绩的差量重算、修复与全量重建。

正常链路只由根 speedranking.services 的 old_pb + pb_changes + old_derived 触发；
不新增 VideoModel receiver，也不在 PB 刷新 rank 时递归重算其他用户。
"""
from .cache import PBDerivedCache
from .utils import apply_record_delta, compute, defaults, FIELDS, LEVELS, MODES, RANKINGS
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


def compute_for_records(records, modes=None):
    return compute(pb_values(records), modes)


def _overlay(records, replacements):
    result = dict(records)
    for field, candidate in replacements.items():
        if candidate is None:
            result.pop(field, None)
        else:
            result[field] = record_from_score(candidate[0], candidate[1])
    return result


def _modes(records):
    return {field.split(':', 1)[0] for field in records if field.split(':', 1)[0] in MODES}


def _cached_modes(old_values):
    return {mode for mode in MODES if f'{mode}:sum:asb' in old_values.get('collection', {})}


def _initial_values(old_values, old_modes, new_modes):
    values = {ranking: dict(old_values.get(ranking, {})) for ranking in RANKINGS}
    entering = new_modes - old_modes
    if entering:
        fallback = defaults()
        for mode in entering:
            for ranking in RANKINGS:
                for field in FIELDS[ranking]:
                    if field.startswith(f'{mode}:'):
                        values[ranking][field] = fallback[ranking][field]
    for mode in old_modes - new_modes:
        for ranking in RANKINGS:
            for field in FIELDS[ranking]:
                if field.startswith(f'{mode}:'):
                    values[ranking].pop(field, None)
    return values


def prepare_changes(old_pb, pb_changes, old_derived=None):
    """把本批 PB 变化直接加减到已存成绩上，每个受影响用户只处理一次。"""
    affected = {}
    for (player_id, field), candidate in pb_changes.items():
        affected.setdefault(player_id, {})[field] = candidate
    changes = {}
    for player_id, replacements in affected.items():
        records = old_pb.get(player_id, {})
        updated = _overlay(records, replacements)
        old_values = (old_derived or {}).get(player_id) or {}
        old_modes = _modes(records)
        if not any(old_values.values()) or _cached_modes(old_values) != old_modes:
            changes[player_id] = compute_for_records(updated)
            continue
        new_modes = _modes(updated)
        values = _initial_values(old_values, old_modes, new_modes)
        for field, candidate in replacements.items():
            if field.split(':', 1)[0] not in new_modes:
                continue
            nf, level, bv = parse_field(field)
            old_record = records.get(field)
            old_timems = old_record['timems'] if old_record else None
            new_timems = record_from_score(candidate[0], candidate[1])['timems'] if candidate is not None else None
            apply_record_delta(values, nf, level, bv, old_timems, new_timems)
        changes[player_id] = values
    return changes


def read_pb_records(player_id: int):
    ranking = PBRankingCache()
    raw = cache.hgetall(ranking.player_key(player_id))
    return ranking.unpack_records([raw], [player_id])[player_id]


def rebuild_player(player_id: int, force=True):
    """修复后完整读取该用户的 PB hash 再重算，force 可补回丢失的索引。"""
    values = compute_for_records(read_pb_records(player_id))
    derived = PBDerivedCache()
    previous = {} if force else {player_id: derived.get_records(player_id)}
    with pipeline() as pipe:
        derived.write_changes(pipe, previous, {player_id: values}, force=force)
        pipe.execute()
    return values


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
