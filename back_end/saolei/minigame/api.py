from datetime import datetime

from django.http import HttpResponse
from django_ratelimit.decorators import ratelimit
from ninja import Form, Router, Schema
from ninja.decorators import decorate_view
from ninja.orm import create_schema
from pydantic import Json

from userprofile.decorators import banned_blocked, login_required_error
from userprofile.models import UserProfile
from .models import MiniGameBestScore
from .services import get_player_scores, get_ranking, get_replay, submit_score
from .utils import GAME_RANKINGS, MiniGameError, ranking_definitions, RANKINGS

router = Router()
BestScoreOut = create_schema(MiniGameBestScore, fields=['id', 'ranking_key', 'score', 'achieved_at'], custom_fields=[('player_id', int, ...)])


class SubmissionOut(Schema):
    improved: bool
    record: BestScoreOut


class ScoreOut(Schema):
    score: int
    achieved_at: datetime


class RankedScoreOut(ScoreOut):
    rank: int | None


class RankingRowOut(Schema):
    player_id: int
    rank: int
    records: dict[str, ScoreOut | None]


class RankingOut(Schema):
    count: int
    players: list[RankingRowOut]


class PlayerOut(Schema):
    player_id: int
    records: dict[str, RankedScoreOut | None]


def require_game(game):
    if game not in GAME_RANKINGS:
        raise MiniGameError(404, 'unknown_game', 'Unknown game')


def require_ranking(ranking_key):
    if ranking_key not in RANKINGS:
        raise MiniGameError(404, 'unknown_ranking', 'Unknown ranking')


@router.get('/rankings')
@decorate_view(ratelimit(group='minigame.rankings', key='ip', rate='5/s'))
def get_rankings(request):
    """
    - ratelimit(group='minigame.rankings', key='ip', rate='5/s')
    """
    return ranking_definitions()


# decorate_view 的最后一个参数最先执行：先检查登录，再读取封禁状态。
@router.post('/{ranking_key}/score', response=SubmissionOut)
@decorate_view(ratelimit(group='minigame.submit.user', key='user', rate='60/m'), banned_blocked, login_required_error)
def post_score(request, ranking_key: str, score: Form[int], replay: Form[Json[dict]]):
    """
    - login_required_error
    - banned_blocked
    - ratelimit(group='minigame.submit.user', key='user', rate='60/m')
    """
    require_ranking(ranking_key)
    return submit_score(request.user, ranking_key, score, replay)


@router.get('/{game}/replay')
@decorate_view(ratelimit(group='minigame.replay', key='ip', rate='5/s'))
def player_replay(request, game: str, player: int, key: str):
    """
    - ratelimit(group='minigame.replay', key='ip', rate='5/s')
    """
    require_game(game)
    ranking_key = f'{game}-{key}'
    require_ranking(ranking_key)
    score, archive = get_replay(ranking_key, player)
    return HttpResponse(archive, content_type='application/x-7z-compressed', headers={
        # The stored 7z is already compressed; skip GZipMiddleware.
        'Content-Encoding': 'identity', 'Content-Length': str(len(archive)),
        'Cache-Control': 'no-transform', 'X-Minigame-Score': str(score),
        'Access-Control-Expose-Headers': 'X-Minigame-Score',
    })


@router.get('/{game}/rank', response=RankingOut)
@decorate_view(ratelimit(group='minigame.rank', key='ip', rate='5/s'))
def game_ranking(request, game: str, sort: str | None = None, start: int = 0, end: int = 20):
    """
    - ratelimit(group='minigame.rank', key='ip', rate='5/s')
    """
    require_game(game)
    sort = sort or GAME_RANKINGS[game][0].key
    require_ranking(sort)
    if RANKINGS[sort].game != game:
        raise MiniGameError(422, 'invalid_sort', 'Sort ranking must belong to this game')
    start = max(0, start)
    end = min(max(start, end), start + 100)
    return get_ranking(game, sort, start, end)


@router.get('/{game}/player/{player_id}', response=PlayerOut)
@decorate_view(ratelimit(group='minigame.player', key='ip', rate='5/s'))
def player_scores(request, game: str, player_id: int):
    """
    - ratelimit(group='minigame.player', key='ip', rate='5/s')
    """
    require_game(game)
    if not UserProfile.objects.filter(pk=player_id).exists():
        raise MiniGameError(404, 'unknown_player', 'Unknown player')
    return get_player_scores(game, player_id)
