from django_ratelimit.decorators import ratelimit
from ninja import Form, Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError

from userprofile.decorators import staff_required
from userprofile.models import UserProfile
from .cache import NFIOERankingCache
from .services import rebuild_player_record
from .utils import RankStat

router = Router()


class VideoRecordOut(Schema):
    value: float
    video_id: int
    timems: int


class RecordOut(Schema):
    player_id: int
    b: VideoRecordOut | None
    i: VideoRecordOut | None
    e: VideoRecordOut | None


class PlayerRecordOut(RecordOut):
    ranks: dict[RankStat, int | None]


class RankingOut(Schema):
    count: int
    players: list[RecordOut]


@router.get('/rank', response=RankingOut)
@decorate_view(ratelimit(key='ip', rate='5/s'))
def get_ranking(request, stat: RankStat = 'sum', start: int = 0, end: int = 20):
    """
    - ratelimit(key='ip', rate='5/s')
    """
    start = max(0, start)
    end = min(max(start, end), start + 100)
    return NFIOERankingCache().get_range(stat, start, end)


@router.get('/player/{player_id}', response=PlayerRecordOut)
@decorate_view(ratelimit(key='ip', rate='5/s'))
def get_player_record(request, player_id: int):
    """
    - ratelimit(key='ip', rate='5/s')
    """
    return NFIOERankingCache().get_player(player_id)


@router.post('/admin/rebuild_record', response=RecordOut)
@decorate_view(staff_required)
def rebuild_record(request, player_id: Form[int], stat: Form[RankStat]):
    """
    - staff_required
    """
    if not UserProfile.objects.filter(pk=player_id).exists():
        raise HttpError(404, 'User not found')
    return rebuild_player_record(player_id, stat)
