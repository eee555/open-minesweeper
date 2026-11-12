from typing import Literal

from django_ratelimit.decorators import ratelimit
from ninja import Form, Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError

from userprofile.decorators import staff_required
from userprofile.models import UserProfile
from .cache import PBDerivedCache
from .services import player_summary, rebuild_player
from .utils import validate_field
from ..pb.api import PBPlayerRecordOut
from ..pb.cache import PBRankingCache

router = Router()
DerivedRankingName = Literal['collection', 'skill', 'typical_time']


class DerivedRankingRowOut(Schema):
    player_id: int
    records: dict[str, dict[str, float]]


class DerivedRankingOut(Schema):
    count: int
    rows: list[DerivedRankingRowOut]


class DerivedSummaryOut(Schema):
    pb: list[PBPlayerRecordOut]
    records: dict[str, dict[str, float]]
    ranks: dict[str, dict[str, int | None]]


class DerivedRebuildOut(Schema):
    player_id: int
    fields: int


@router.get('/rank', response=DerivedRankingOut)
@decorate_view(ratelimit(key='ip', rate='5/s'))
def get_ranking(request, ranking: DerivedRankingName, field: str, start: int = 0, end: int = 20):
    """
    - ratelimit(key='ip', rate='5/s')

    由一个小榜 zset 取用户区间，再用同一 pipeline 读取该页所需的成绩 hash。
    """
    if not validate_field(ranking, field):
        raise HttpError(422, 'Unknown derived ranking field')
    start = max(0, start)
    end = min(max(start, end), start + 100)
    names = ('collection',) if ranking == 'collection' else ('skill', 'typical_time')
    data = PBDerivedCache().get_range(names, ranking, field, start, end)
    rows = [{'player_id': player_id, 'records': {name: data['records'][name][player_id] for name in names}} for player_id in data['players']]
    return {'count': data['count'], 'rows': rows}


@router.get('/summary', response=DerivedSummaryOut)
@decorate_view(ratelimit(key='ip', rate='5/s'))
def get_summary(request, player_id: int):
    """
    - ratelimit(key='ip', rate='5/s')

    一次取得原 PB、三个衍生大榜的全部成绩及 132 项排名；缓存未命中不重建。
    """
    summary = player_summary(player_id)
    return {
        'pb': PBRankingCache().get_player_records(player_id),
        'records': summary['records'],
        'ranks': summary['ranks'],
    }


@router.post('/admin/rebuild_player', response=DerivedRebuildOut)
@decorate_view(staff_required)
def rebuild_player_record(request, player_id: Form[int]):
    """
    - staff_required

    从完整 PB hash 重算并强制补回某用户的全部衍生索引。
    """
    if not UserProfile.objects.filter(pk=player_id).exists():
        raise HttpError(404, 'User not found')
    records = rebuild_player(player_id)
    return {'player_id': player_id, 'fields': sum(len(values) for values in records.values())}
