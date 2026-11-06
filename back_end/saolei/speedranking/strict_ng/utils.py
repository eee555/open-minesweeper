from math import floor
from typing import Literal

from config.text_choices import MS_TextChoices

RankingName = Literal['strict_ng', 'strict_ng_nf']
RankStat = Literal['bt', 'bb', 'it', 'ib', 'et', 'eb', 'sumt', 'sumb']
RANKING_NAMES = ('strict_ng', 'strict_ng_nf')
# Strict NG only requires a non-null 3BV, so the rules keep the level and the
# ranking field without a lower bound on bv.
RULES = {
    'bt': (MS_TextChoices.Level.BEGINNER, 'timems'),
    'bb': (MS_TextChoices.Level.BEGINNER, 'bvs'),
    'it': (MS_TextChoices.Level.INTERMEDIATE, 'timems'),
    'ib': (MS_TextChoices.Level.INTERMEDIATE, 'bvs'),
    'et': (MS_TextChoices.Level.EXPERT, 'timems'),
    'eb': (MS_TextChoices.Level.EXPERT, 'bvs'),
}
TOTAL_PARTS = {'sumt': ('bt', 'it', 'et'), 'sumb': ('bb', 'ib', 'eb')}
RANK_STATS = (*RULES, *TOTAL_PARTS)
TIME_STATS = {'bt', 'it', 'et', 'sumt'}
MAX_RECORD_UNITS = 999999
BVS_SCALE = 10000
MISSING_TIMEMS = MAX_RECORD_UNITS
SCORE_TIME_FACTOR = 3_000_000_000


def empty_record():
    record = {'sumt': MISSING_TIMEMS * 3, 'sumb': 0, '_uploads': {'sumt': 0, 'sumb': 0}}
    for stat in RULES:
        record[stat] = None
        record[f'{stat}_id'] = None
    return record


def update_totals(record):
    for total, parts in TOTAL_PARTS.items():
        default = MISSING_TIMEMS if total == 'sumt' else 0
        record[total] = sum(record[stat] if record[stat] is not None else default for stat in parts)
        record['_uploads'][total] = max((record['_uploads'][stat] for stat in parts if record[stat] is not None), default=0)


def plan_strict_ng_record_update(previous: dict, record: dict, *, force: bool = False):
    """按强无猜规则重算总分，返回待写的个人纪录和变化的小榜 score。"""
    update_totals(record)
    if record == previous and not force:
        return None
    present = any(record[f'{stat}_id'] is not None for stat in RULES)
    previous_present = any(previous[f'{stat}_id'] is not None for stat in RULES)
    scores = {}
    for stat in RANK_STATS:
        encoded = None
        if present and record[stat] is not None:
            encoded = encode_zset_score(stat, record[stat], record['_uploads'][stat])
        previous_encoded = None
        if previous_present and previous[stat] is not None:
            previous_encoded = encode_zset_score(stat, previous[stat], previous['_uploads'][stat])
        if force or encoded != previous_encoded:
            scores[stat] = encoded
    return (record if present else None, scores)


def encode_zset_score(stat: str, value: float, upload: int) -> int | None:
    """仅 zset 排序量化成绩和微秒时间戳；超限返回 None，不影响个人纪录。"""
    scale = 1 if stat in TIME_STATS else BVS_SCALE
    upload //= 60_000_000
    limit = MAX_RECORD_UNITS * (3 if stat in TOTAL_PARTS else 1)
    if not 0 <= value <= limit / scale or not 0 <= upload < SCORE_TIME_FACTOR:
        return None
    units = floor(value * scale + 0.5)
    return (units if stat in TIME_STATS else -units) * SCORE_TIME_FACTOR + upload


def score(stat: str, value: float) -> float:
    return value if stat in TIME_STATS else -value


def is_better(stat: str, candidate: dict, record: dict) -> bool:
    if record[stat] is None:
        return True
    return (score(stat, candidate['value']), candidate['upload']) < (score(stat, record[stat]), record['_uploads'][stat])


def set_stat(record: dict, stat: str, candidate: dict | None):
    record[stat] = candidate['value'] if candidate else None
    record[f'{stat}_id'] = candidate['id'] if candidate else None
    if candidate:
        record['_uploads'][stat] = candidate['upload']
    else:
        record['_uploads'].pop(stat, None)


def public_record(player_id: int, record: dict):
    return {'player_id': player_id, **{key: value for key, value in record.items() if key != '_uploads'}}
