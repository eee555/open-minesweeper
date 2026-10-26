from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from math import floor

from config.text_choices import Medal_TextChoices, MS_TextChoices
from speedranking.saolei.utils import BVS_SCALE

SHAREHOLDER_CODE = 'shareholder.origin'
SHAREHOLDER_THRESHOLDS = [100000, 10000, 1000]
MAX_PINS = 6
CATALOG_CACHE_KEY = 'medal:catalog:v3'
CATALOG_CACHE_SECONDS = 300
STATE_CACHE_KEY = 'medal:display:v4:{user_id}'
STATE_CACHE_SECONDS = 300
STATE_ID_LIMIT = 100
GRANT_PAGE_SIZE = 20
GRANT_PAGE_SIZE_MAX = 50
REFRESH_COALESCE_DELAY = timedelta(seconds=3)
THRP_SCALE = 100000
STANDARD_LEVELS = (
    MS_TextChoices.Level.BEGINNER, MS_TextChoices.Level.INTERMEDIATE, MS_TextChoices.Level.EXPERT,
)
NOVICE_REALNAME = 'novice.realname'
NOVICE_REVIEW = 'novice.review'
NOVICE_LEVELS = 'novice.levels'
NOVICE_LEVELS_NF = 'novice.levels_nf'
NOVICE_MODES = 'novice.modes'
NOVICE_SAOLEI = 'novice.saolei'
VIDEO_ONCE_CODES = (NOVICE_REVIEW, NOVICE_LEVELS, NOVICE_LEVELS_NF, NOVICE_MODES)
TIME_SECONDS = {
    MS_TextChoices.Level.BEGINNER: (20, 15, 12, 10, 8, 6, 5, 4, 3, 2, 1),
    MS_TextChoices.Level.INTERMEDIATE: (150, 100, 80, 60, 50, 40, 30, 25, 20, 15, 12, 10),
    MS_TextChoices.Level.EXPERT: (300, 200, 150, 120, 100, 90, 80, 70, 60, 50, 40, 30),
}
BVS_THRESHOLDS = {
    MS_TextChoices.Level.BEGINNER: (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12),
    MS_TextChoices.Level.INTERMEDIATE: (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8),
    MS_TextChoices.Level.EXPERT: (1, 1.5, 2, 2.5, 3, 4, 5, 6),
}
NF_BVS_THRESHOLDS = {
    MS_TextChoices.Level.BEGINNER: (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 9),
    MS_TextChoices.Level.INTERMEDIATE: (1, 1.5, 2, 2.5, 3, 4, 5, 6, 7),
    MS_TextChoices.Level.EXPERT: (1, 1.5, 2, 2.5, 3, 4, 5),
}
STNB_THRESHOLDS = (10, 15, 20, 30, 40, 50, 60, 80, 100, 150, 200, 300)
NF_THRP_THRESHOLDS = (0.5, 0.7, 0.8, 0.9, 0.95, 1)
FL_THRP_THRESHOLDS = {
    MS_TextChoices.Level.BEGINNER: (0.5, 0.7, 0.8, 1, 1.2, 1.5, 1.8, 2, 2.3, 2.5),
    MS_TextChoices.Level.INTERMEDIATE: (0.5, 0.7, 0.8, 1, 1.2, 1.4, 1.6, 1.8, 1.9),
    MS_TextChoices.Level.EXPERT: (0.5, 0.7, 0.8, 1, 1.2, 1.4, 1.5, 1.6),
}
THREE_NF_THRP = (0.9, 0.95, 1)
THREE_FL_THRP = (1, 1.2, 1.5)


def open_modes():
    """当前开放的模式名单。全模式成就读这个列表，不读前端不完整的模式表。"""
    return [item.value for item in MS_TextChoices.Mode]


def threshold_index(thresholds, stage):
    """阶段在有序阈值里的位置。0 或不在刻度上为 -1。空刻度上的正阶段视为第 0 档。列表从易到难，靠后的一档更高。"""
    if not stage:
        return -1
    values = list(thresholds or [])
    if not values:
        return 0
    try:
        return values.index(stage)
    except ValueError:
        return -1


def reached_desc_stage(thresholds, value):
    """有序阈值从易到难，越小越难。value 严格小于阈值才算过档，返回已达到的最高档；一档都不够返回 0。"""
    reached = 0
    for threshold in thresholds or []:
        if value < threshold:
            reached = threshold
        else:
            break
    return reached


def next_threshold(thresholds, stage):
    """下一档阈值。未入档时是第一档，已经到顶则为空。"""
    values = list(thresholds or [])
    if not values:
        return None
    following = threshold_index(values, stage) + 1
    if following < len(values):
        return values[following]
    return None


def reached_asc_stage(thresholds, value):
    """有序阈值从易到难，越大越难。value 达到阈值才算过档，返回已达到的最高档；一档都不够返回 0。"""
    reached = 0
    for threshold in thresholds or []:
        if value >= threshold:
            reached = threshold
        else:
            break
    return reached


def to_units(number, scale):
    """展示档换成整数刻度。1.5 × 10000 = 15000，0.95 × 100000 = 95000。"""
    return int((Decimal(str(number)) * scale).to_integral_value(rounding=ROUND_HALF_UP))


def scale_units(value, scale):
    """把库里的浮点成绩收成同一套整数刻度。半值进一，与 speedranking 的 floor(value * scale + 0.5) 一致。"""
    if value is None:
        return None
    return floor(float(value) * scale + 0.5)


def _spec(**kwargs):
    row = {
        'subseries': '', 'level': '', 'style': '', 'scope': {}, 'depends_on': [], 'hidden': False,
        'score_by_stage': [], 'active': True, 'annotation': '',
    }
    row.update(kwargs)
    row['thresholds'] = list(row['thresholds'])
    row['scope'] = dict(row['scope'])
    row['depends_on'] = list(row['depends_on'])
    row['score_by_stage'] = list(row['score_by_stage'])
    return row


def _ability(code, series, metric, direction, level, style, thresholds):
    return _spec(code=code, series=series, kind=Medal_TextChoices.Kind.PB, metric=metric, direction=direction, level=level, style=style, thresholds=thresholds)


def basic_definitions():
    """新手和能力定义。已有行的阈值不从这里回写，系列名由 ensure_basic_definitions 对齐。"""
    rows = [
        _spec(code=NOVICE_REALNAME, series=Medal_TextChoices.Series.REGISTERED, kind=Medal_TextChoices.Kind.ONCE, metric='realname', direction=Medal_TextChoices.Direction.ASC, thresholds=[1]),
        _spec(code=NOVICE_REVIEW, series=Medal_TextChoices.Series.REVIEWED, kind=Medal_TextChoices.Kind.ONCE, metric='review', direction=Medal_TextChoices.Direction.ASC, thresholds=[1]),
        _spec(code=NOVICE_LEVELS, series=Medal_TextChoices.Series.LEVELS, kind=Medal_TextChoices.Kind.ONCE, metric='levels', direction=Medal_TextChoices.Direction.ASC, thresholds=[1]),
        _spec(code=NOVICE_LEVELS_NF, series=Medal_TextChoices.Series.LEVELS_NF, kind=Medal_TextChoices.Kind.ONCE, metric='levels_nf', direction=Medal_TextChoices.Direction.ASC, thresholds=[1]),
        _spec(
            code=NOVICE_MODES, series=Medal_TextChoices.Series.MODES, kind=Medal_TextChoices.Kind.ONCE, metric='modes', direction=Medal_TextChoices.Direction.ASC, thresholds=[1],
            scope={'modes': open_modes()},
        ),
        _spec(
            code=NOVICE_SAOLEI, series=Medal_TextChoices.Series.SAOLEI, kind=Medal_TextChoices.Kind.ONCE, metric='platform', direction=Medal_TextChoices.Direction.ASC, thresholds=[1],
            scope={'platform': 'c'},
        ),
    ]
    for level in STANDARD_LEVELS:
        rows.append(_ability(f'ability.time.{level}', Medal_TextChoices.Series.BREAKTHROUGH, 'timems', Medal_TextChoices.Direction.DESC, level, Medal_TextChoices.Style.ANY, [second * 1000 for second in TIME_SECONDS[level]]))
        rows.append(_ability(f'ability.bvs.{level}', Medal_TextChoices.Series.SPEED, 'bvs', Medal_TextChoices.Direction.ASC, level, Medal_TextChoices.Style.ANY, [to_units(item, BVS_SCALE) for item in BVS_THRESHOLDS[level]]))
        rows.append(_ability(f'ability.stnb.{level}', Medal_TextChoices.Series.MASTERY, 'stnb', Medal_TextChoices.Direction.ASC, level, Medal_TextChoices.Style.ANY, list(STNB_THRESHOLDS)))
        rows.append(_ability(f'ability.time.nf.{level}', Medal_TextChoices.Series.FLAGLESS_BREAKTHROUGH, 'timems', Medal_TextChoices.Direction.DESC, level, Medal_TextChoices.Style.NF, [second * 1000 for second in TIME_SECONDS[level]]))
        rows.append(_ability(f'ability.bvs.nf.{level}', Medal_TextChoices.Series.FLAGLESS_SPEED, 'bvs', Medal_TextChoices.Direction.ASC, level, Medal_TextChoices.Style.NF, [to_units(item, BVS_SCALE) for item in NF_BVS_THRESHOLDS[level]]))
        rows.append(_ability(f'ability.stnb.nf.{level}', Medal_TextChoices.Series.FLAGLESS_MASTERY, 'stnb', Medal_TextChoices.Direction.ASC, level, Medal_TextChoices.Style.NF, list(STNB_THRESHOLDS)))
        rows.append(_ability(f'ability.thrp.nf.{level}', Medal_TextChoices.Series.FLAGLESS_PRECISION, 'thrp', Medal_TextChoices.Direction.ASC, level, Medal_TextChoices.Style.NF, [to_units(item, THRP_SCALE) for item in NF_THRP_THRESHOLDS]))
        rows.append(_ability(f'ability.thrp.fl.{level}', Medal_TextChoices.Series.FLAGGED_PRECISION, 'thrp', Medal_TextChoices.Direction.ASC, level, Medal_TextChoices.Style.FL, [to_units(item, THRP_SCALE) for item in FL_THRP_THRESHOLDS[level]]))
    rows.append(_spec(
        code='ability.thrp.nf.three', series=Medal_TextChoices.Series.THREE_FLAGLESS_PRECISION, kind=Medal_TextChoices.Kind.COMPOSITE, metric='thrp', direction=Medal_TextChoices.Direction.ASC, style=Medal_TextChoices.Style.NF,
        thresholds=[to_units(item, THRP_SCALE) for item in THREE_NF_THRP],
        depends_on=[f'ability.thrp.nf.{level}' for level in STANDARD_LEVELS],
    ))
    rows.append(_spec(
        code='ability.thrp.fl.three', series=Medal_TextChoices.Series.THREE_FLAGGED_PRECISION, kind=Medal_TextChoices.Kind.COMPOSITE, metric='thrp', direction=Medal_TextChoices.Direction.ASC, style=Medal_TextChoices.Style.FL,
        thresholds=[to_units(item, THRP_SCALE) for item in THREE_FL_THRP],
        depends_on=[f'ability.thrp.fl.{level}' for level in STANDARD_LEVELS],
    ))
    return rows
