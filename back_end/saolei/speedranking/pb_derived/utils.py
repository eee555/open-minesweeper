"""PB 衍生榜的基础配置与纯计算，不访问数据库或 Redis。"""
import math

from config.bv_frequencies import BV_FREQUENCIES

LEVELS = ('b', 'i', 'e')
MODES = ('std', 'nf')
LEVEL_KEYS = (*LEVELS, 'sum')
RANKINGS = ('collection', 'skill', 'typical_time')
COLLECTION_METRICS = ('count', 'probability', 'asb')
ZERO_TT = 999.999

# 分段端点均包含在内；BV 0 不属于任何分段。
SEGMENTS = {
    'b': ((1, 9), (10, 19), (20, 29), (30, 54)),
    'i': ((1, 39), (40, 49), (50, 59), (60, 69), (70, 79), (80, 89), (90, 99), (100, 216)),
    'e': ((1, 129), (130, 139), (140, 149), (150, 159), (160, 169), (170, 179), (180, 189), (190, 199), (200, 209), (210, 219), (220, 381)),
}


def _validate_frequencies():
    probabilities = {}
    level_weights = {}
    segment_weights = {}
    segment_mean_parts = {}
    for level in LEVELS:
        frequencies = BV_FREQUENCIES[level]
        if len(frequencies) < 2:
            raise ValueError(f'BV frequencies for {level} must contain at least one usable BV')
        values = []
        for raw in frequencies[1:]:
            value = float(raw)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f'BV frequency for {level} must be finite and nonnegative')
            values.append(value)
        total = math.fsum(values)
        if not math.isfinite(total) or total <= 0:
            raise ValueError(f'BV frequency sum for {level} must be positive')
        probabilities[level] = [0.0, *(value / total for value in values)]
        level_weights[level] = math.fsum(probabilities[level][1:])

        expected = 1
        for start, end in SEGMENTS[level]:
            if start != expected or end < start or end >= len(probabilities[level]):
                raise ValueError(f'Segments for {level} must cover every usable BV exactly once')
            expected = end + 1
        if expected != len(probabilities[level]):
            raise ValueError(f'Segments for {level} must cover every usable BV exactly once')

        segment_weights[level] = []
        segment_mean_parts[level] = []
        for start, end in SEGMENTS[level]:
            weight = math.fsum(probabilities[level][start:end + 1])
            if weight <= 0:
                raise ValueError(f'Segment {start}-{end} for {level} has zero probability mass')
            segment_weights[level].append(weight)
            segment_mean_parts[level].append(math.fsum(probabilities[level][bv] * bv for bv in range(start, end + 1)))
    return probabilities, level_weights, segment_weights, segment_mean_parts


PROBABILITIES, LEVEL_WEIGHTS, SEGMENT_WEIGHTS, SEGMENT_MEAN_PARTS = _validate_frequencies()


def segment_field(mode: str, level: str, index: int) -> str:
    return f'{mode}:{level}:s{index + 1}'


def _skill_tt_fields():
    fields = []
    for mode in MODES:
        for level in LEVELS:
            fields.extend(segment_field(mode, level, index) for index in range(len(SEGMENTS[level])))
            fields.append(f'{mode}:{level}:total')
        fields.append(f'{mode}:sum:total')
    return tuple(fields)


FIELDS = {
    'collection': tuple(f'{mode}:{level}:{metric}' for mode in MODES for level in LEVEL_KEYS for metric in COLLECTION_METRICS),
    'skill': _skill_tt_fields(),
    'typical_time': _skill_tt_fields(),
}
if sum(len(fields) for fields in FIELDS.values()) != 132:
    raise ValueError('PB derived rankings must contain exactly 132 fields')


def score(ranking: str, value: float) -> float:
    """升序读取：收集、战力取负，典型时取正。"""
    return value if ranking == 'typical_time' else -value


def validate_field(ranking: str, field: str) -> bool:
    return ranking in FIELDS and field in FIELDS[ranking]


def bvs(bv: int, timems: int) -> float:
    return 1000 * bv / timems if timems > 0 else 0.0


def _segment_index(level: str, bv: int):
    for index, (start, end) in enumerate(SEGMENTS[level]):
        if start <= bv <= end:
            return index
    return None


def segment_field_for_bv(mode: str, level: str, bv: int):
    """返回该 BV 所属分段的成绩字段名；无有效权重时返回 None。"""
    probabilities = PROBABILITIES[level]
    if not 1 <= bv < len(probabilities) or probabilities[bv] == 0:
        return None
    index = _segment_index(level, bv)
    return segment_field(mode, level, index) if index is not None else None


def apply_record_delta(values, nf: bool, level: str, bv: int, old_timems, new_timems):
    """把一个 PB 桶的变化直接加减到三大榜成绩上；values 原地修改。

    values 为 {ranking: {field: value}}，调用前须已包含该类别全部字段。
    收集与战力按 ΔW = p[bv] * ΔBvs 线性累加；分段典型时是非线性的，
    由分段战力反推 W_I = skill_I * Q_I 后重算 tt_I，再把 Δtt_I 累加到合计。
    """
    if old_timems is not None and new_timems is not None and old_timems == new_timems:
        return
    mode = 'nf' if nf else 'std'
    probabilities = PROBABILITIES[level]
    weight = probabilities[bv] if 1 <= bv < len(probabilities) and probabilities[bv] > 0 else 0.0
    old_present = old_timems is not None
    new_present = new_timems is not None
    old_value = bvs(bv, old_timems) if old_present else 0.0
    new_value = bvs(bv, new_timems) if new_present else 0.0
    delta_bvs = new_value - old_value
    delta_w = weight * delta_bvs
    delta_count = int(new_present) - int(old_present)

    collection = values['collection']
    for prefix in (f'{mode}:{level}', f'{mode}:sum'):
        collection[f'{prefix}:count'] += delta_count
        collection[f'{prefix}:probability'] = max(0.0, collection[f'{prefix}:probability'] + weight * delta_count)
        collection[f'{prefix}:asb'] = max(0.0, collection[f'{prefix}:asb'] + delta_bvs)

    skill = values['skill']
    typical_time = values['typical_time']
    delta_skill_level = delta_w / LEVEL_WEIGHTS[level]
    skill[f'{mode}:{level}:total'] = max(0.0, skill[f'{mode}:{level}:total'] + delta_skill_level)
    skill[f'{mode}:sum:total'] = max(0.0, skill[f'{mode}:sum:total'] + delta_skill_level)
    index = _segment_index(level, bv) if weight else None
    if index is not None and delta_w:
        field = segment_field(mode, level, index)
        q = SEGMENT_WEIGHTS[level][index]
        new_w = max(0.0, skill[field] * q + delta_w)
        skill[field] = new_w / q
        new_tt = SEGMENT_MEAN_PARTS[level][index] / new_w if new_w > 0 else ZERO_TT
        delta_tt = new_tt - typical_time[field]
        typical_time[field] = new_tt
        typical_time[f'{mode}:{level}:total'] += delta_tt
        typical_time[f'{mode}:sum:total'] += delta_tt


def compute(pb_values: dict, modes=None):
    """按完整 PB 映射一次算出三个大榜的全部成绩。

    pb_values 的键为 (是否 NF, 等级, BV)，值为整数毫秒用时；只依据数值计算，
    不查询录像。mode 是否入榜由该类别是否存在 PB 决定，modes 用于生成缺省展示值。
    """
    present = {('nf' if nf else 'std') for nf, _, _ in pb_values}
    selected = set(present if modes is None else (*modes, *present))
    collection = {}
    skill = {}
    typical_time = {}
    for mode in MODES:
        if mode not in selected:
            continue
        want_nf = mode == 'nf'
        by_level = {level: {} for level in LEVELS}
        for (nf, level, bv), timems in pb_values.items():
            if nf == want_nf and level in by_level:
                by_level[level][bv] = timems
        level_skill = {}
        level_tt = {}
        for level in LEVELS:
            values = by_level[level]
            probabilities = PROBABILITIES[level]
            max_bv = len(probabilities) - 1
            probability = 0.0
            asb = 0.0
            contributions = [0.0] * len(SEGMENTS[level])
            for bv, timems in values.items():
                value = bvs(bv, timems)
                asb += value
                if not 1 <= bv <= max_bv or probabilities[bv] == 0:
                    continue
                probability += probabilities[bv]
                weight = probabilities[bv] * value
                for index, (start, end) in enumerate(SEGMENTS[level]):
                    if start <= bv <= end:
                        contributions[index] += weight
                        break
            collection[f'{mode}:{level}:count'] = len(values)
            collection[f'{mode}:{level}:probability'] = probability
            collection[f'{mode}:{level}:asb'] = asb
            skill[f'{mode}:{level}:total'] = math.fsum(contributions) / LEVEL_WEIGHTS[level]
            level_skill[level] = skill[f'{mode}:{level}:total']
            level_tt[level] = 0.0
            for index, contribution in enumerate(contributions):
                key = segment_field(mode, level, index)
                skill[key] = contribution / SEGMENT_WEIGHTS[level][index]
                typical_time[key] = SEGMENT_MEAN_PARTS[level][index] / contribution if contribution > 0 else ZERO_TT
                level_tt[level] += typical_time[key]
            typical_time[f'{mode}:{level}:total'] = level_tt[level]
        for metric in COLLECTION_METRICS:
            collection[f'{mode}:sum:{metric}'] = math.fsum(collection[f'{mode}:{level}:{metric}'] for level in LEVELS)
        skill[f'{mode}:sum:total'] = math.fsum(level_skill.values())
        typical_time[f'{mode}:sum:total'] = math.fsum(level_tt.values())
    return {'collection': collection, 'skill': skill, 'typical_time': typical_time}


def defaults():
    """无对应 PB 类别时的缺省展示值，排名由 API 单独置空。"""
    return compute({}, modes=MODES)
