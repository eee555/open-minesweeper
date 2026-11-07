from django_ratelimit.decorators import ratelimit
from ninja import Form, Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError

from userprofile.decorators import staff_required
from userprofile.models import UserProfile
from .cache import SpeedRankingCache
from .services import get_player_records, rebuild_player_record
from .utils import RankingName, RankStat

router = Router()


class RecordOut(Schema):
    player_id: int
    bt: int | None
    bb: float | None
    it: int | None
    ib: float | None
    et: int | None
    eb: float | None
    sumt: int
    sumb: float
    bt_id: int | None
    bb_id: int | None
    it_id: int | None
    ib_id: int | None
    et_id: int | None
    eb_id: int | None


class PlayerRecordOut(RecordOut):
    ranks: dict[RankStat, int | None]


class RankingOut(Schema):
    count: int
    players: list[RecordOut]


@router.get('/rank', response=RankingOut)
@decorate_view(ratelimit(key='ip', rate='5/s'))
def get_ranking(request, ranking_name: RankingName = 'strict_ng', stat: RankStat = 'sumt', start: int = 0, end: int = 20):
    """
    - ratelimit(key='ip', rate='5/s')
    """
    start = max(0, start)
    end = min(max(start, end), start + 100)
    return SpeedRankingCache(ranking_name).get_range(stat, start, end)


@router.get('/player/{player_id}', response=dict[RankingName, PlayerRecordOut])
@decorate_view(ratelimit(key='ip', rate='5/s'))
def get_player_record(request, player_id: int):
    """
    - ratelimit(key='ip', rate='5/s')
    """
    return get_player_records(player_id)


@router.post('/admin/rebuild_record', response=RecordOut)
@decorate_view(staff_required)
def rebuild_record(request, player_id: Form[int], ranking_name: Form[RankingName], stat: Form[RankStat]):
    """
    - staff_required

    从录像库重建用户的小榜纪录；sumt/sumb 仅使用缓存中的组成项重算。
    """
    if not UserProfile.objects.filter(pk=player_id).exists():
        raise HttpError(404, 'User not found')
    return rebuild_player_record(player_id, ranking_name, stat)
