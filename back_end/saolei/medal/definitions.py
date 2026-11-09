from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from config.text_choices import Medal_TextChoices
from .utils import basic_definitions, SHAREHOLDER_CODE, SHAREHOLDER_THRESHOLDS


@dataclass(frozen=True)
class MedalRule:
    code: str
    series: str
    kind: str
    metric: str
    direction: str
    thresholds: tuple[int, ...] = ()
    subseries: str = ''
    level: str = ''
    style: str = ''
    scope: Mapping | None = None
    depends_on: tuple[str, ...] = ()
    hidden: bool = False
    active: bool = True
    annotation: str = ''
    bv_min: int | None = None

    def __post_init__(self):
        object.__setattr__(self, 'thresholds', tuple(self.thresholds))
        object.__setattr__(self, 'depends_on', tuple(self.depends_on))
        scope = {
            key: tuple(value) if isinstance(value, (list, tuple)) else value
            for key, value in (self.scope or {}).items()
        }
        object.__setattr__(self, 'scope', MappingProxyType(scope))


_rows = [MedalRule(**row) for row in basic_definitions()]
_rows.append(MedalRule(
    code=SHAREHOLDER_CODE, series=Medal_TextChoices.Series.SHAREHOLDER,
    kind=Medal_TextChoices.Kind.MIN_VIDEO_ID, metric='video_id', direction=Medal_TextChoices.Direction.DESC,
    thresholds=tuple(SHAREHOLDER_THRESHOLDS),
))
DEFINITIONS = MappingProxyType({row.code: row for row in _rows})


def all_definitions():
    return tuple(sorted(DEFINITIONS.values(), key=lambda row: (row.series, row.subseries, row.code)))


def get_definition(code):
    return DEFINITIONS.get(code)
