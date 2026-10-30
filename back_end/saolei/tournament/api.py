from datetime import datetime, timezone
from typing import Any, Literal

from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit
from ninja import Field, Form, Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.orm import create_schema

from config.text_choices import Tournament_TextChoices
from tournament.cache import TOURNAMENT_USER_CACHE_KEYS, TournamentCache
from tournament.models import GSCTournament, Tournament, TournamentParticipant, TournamentUser
from tournament.schema import ParticipantOutBase
from tournament.services import with_participant_video_status
from userprofile.decorators import admin_csrf_required, login_required_error, staff_required
from userprofile.models import UserProfile
from utils.response import HttpResponseConflict
from utils.schema import IdIn
from videomanager.models import VideoModel
from videomanager.schema import VideoBaseOut
from videomanager.view_utils import generate_file_stream

router = Router()
cache = TournamentCache()


class TournamentValidationIn(IdIn):
    valid: bool


class TournamentStaffSetIn(Schema):
    tournament_id: int
    weight: int | None = None
    host_id: int | None = None


class TournamentSetIn(IdIn):
    start_time: datetime | None = None
    end_time: datetime | None = None
    order: int | None = None
    token: str | None = None


class ParticipantListIn(Schema):
    tournament_id: int
    user_id: int


TournamentOut = create_schema(
    Tournament,
    fields=['id', 'start_time', 'end_time', 'state', 'subclass'],
    custom_fields=[
        ('host_id', int | None, None),
        ('data', Any, {}),
    ],
)

TournamentParticipantOut = create_schema(
    TournamentParticipant,
    fields=['id', 'token', 'start_time', 'end_time', 'rank', 'rank_score'],
    custom_fields=[
        ('user_id', int, 0),
        ('tournament_id', int, 0),
        ('has_videos', bool, False),
        ('arbiter_identifier__identifier', str | None, Field(None, alias='arbiter_identifier.identifier')),
    ],
    base_class=ParticipantOutBase,
)


TournamentUserOut = create_schema(
    TournamentUser,
    fields=[
        'score_current', 'last_updated', 'score_total',
        'gsc_total', 'gsc_best',
        'weekly_total', 'weekly_classic_total', 'weekly_classic_best',
    ],
    custom_fields=[('user_id', int, 0)],
)


class TournamentUserRankingOut(Schema):
    total: int
    data: list[TournamentUserOut]


class TournamentNewsItemOut(Schema):
    id: int
    start_time: datetime | None = None
    end_time: datetime | None = None


class TournamentNewsOut(Schema):
    preparing: list[TournamentNewsItemOut]
    ongoing: list[TournamentNewsItemOut]


@router.get('/get_list', response=list[TournamentOut])
def get_tournament_list(
    request: HttpRequest,
    category: Literal['normal', 'awarded', 'other', 'all'] = 'all',
):
    if category == 'normal':
        return cache.get_tournament_all()

    queryset = Tournament.objects.all()
    if category == 'awarded':
        queryset = queryset.filter(state=Tournament_TextChoices.State.AWARDED)
    elif category == 'other':
        queryset = queryset.exclude(state__in=[
            Tournament_TextChoices.State.NORMAL,
            Tournament_TextChoices.State.AWARDED,
        ])

    return list(queryset.select_subclasses())


@router.get('/get', response=TournamentOut)
def get_tournament(request: HttpRequest, tournament_id: int):
    return get_object_or_404(Tournament, id=tournament_id).select_subclass()


@router.post('/set')
@decorate_view(login_required_error, admin_csrf_required)
def set_tournament(request: HttpRequest, data: TournamentSetIn = Form(...)):  # noqa: B008
    """
    - `login_required_error`
    - `admin_csrf_required`

    主办方可修改比赛；GSC 比赛也允许管理员修改。
    """
    tournament = get_object_or_404(Tournament, id=data.id).select_subclass()
    if tournament.host != request.user and not (isinstance(tournament, GSCTournament) and request.user.is_staff):
        return HttpResponseForbidden()

    update_fields = []
    if data.start_time is not None:
        tournament.start_time = data.start_time
        update_fields.append('start_time')
    if data.end_time is not None:
        tournament.end_time = data.end_time
        update_fields.append('end_time')

    if isinstance(tournament, GSCTournament):
        if data.order is not None:
            if GSCTournament.objects.exclude(order=tournament.order).filter(order=data.order).exists():
                return HttpResponseConflict()
            tournament.order = data.order
            update_fields.append('order')
        if data.token is not None:
            if GSCTournament.objects.exclude(order=tournament.order).filter(_token=data.token).exists():
                return HttpResponseConflict()
            if TournamentParticipant.objects.filter(token=data.token).exists():
                return HttpResponseConflict()
            tournament._token = data.token
            update_fields.append('_token')

    if update_fields:
        tournament.save(update_fields=update_fields)
    return HttpResponse()


@router.post('/validate')
@decorate_view(staff_required)
def validate_tournament(request: HttpRequest, data: TournamentValidationIn = Form(...)):  # noqa: B008
    tournament = get_object_or_404(Tournament, id=data.id).select_subclass()
    if not data.valid:
        tournament.invalidate()
        return HttpResponse()
    if not tournament.can_validate():
        return {'type': 'error', 'object': 'tournament', 'category': 'invalid_time'}

    update_fields = tournament.validate()
    if update_fields:
        tournament.save(update_fields=update_fields)
    return HttpResponse()


@router.post('/allow')
@decorate_view(staff_required)
def allow_tournament(request: HttpRequest, data: IdIn = Form(...)):  # noqa: B008
    tournament = get_object_or_404(Tournament, id=data.id).select_subclass()
    if not tournament.can_validate():
        return {'type': 'error', 'object': 'tournament', 'category': 'invalid_time'}
    if datetime.now(tz=timezone.utc) > tournament.start_time:
        tournament.state = Tournament_TextChoices.State.CANCELLED
        tournament.save(update_fields=['state'])
        return {'type': 'error', 'object': 'tournament', 'category': 'missed_start_time'}

    update_fields = tournament.validate()
    if update_fields:
        tournament.save(update_fields=update_fields)
    return HttpResponse()


@router.post('/cancel')
@decorate_view(login_required_error, admin_csrf_required)
def cancel_tournament(request: HttpRequest, data: IdIn = Form(...)):  # noqa: B008
    """
    - login_required_error
    - admin_csrf_required
    """
    tournament = get_object_or_404(Tournament, id=data.id)
    if not request.user.is_staff and tournament.host != request.user:
        return HttpResponseForbidden()
    tournament.state = Tournament_TextChoices.State.CANCELLED
    tournament.save(update_fields=['state'])
    return HttpResponse()


@router.post('/set_staff', response=TournamentOut)
@decorate_view(staff_required)
def set_tournament_staff(request: HttpRequest, data: TournamentStaffSetIn = Form(...)):  # noqa: B008
    tournament = get_object_or_404(Tournament, id=data.tournament_id).select_subclass()

    update_fields = []
    if data.weight is not None:
        tournament.weight = data.weight
        update_fields.append('weight')
    if data.host_id is not None:
        tournament.host = get_object_or_404(UserProfile, id=data.host_id)
        update_fields.append('host')
    if update_fields:
        tournament.save(update_fields=update_fields)
    return tournament


@router.get('/participants', response=list[TournamentParticipantOut])
def get_participant_list(request: HttpRequest, tournament_id: int):
    get_object_or_404(Tournament, id=tournament_id)
    return with_participant_video_status(TournamentParticipant.objects.filter(tournament_id=tournament_id).select_related('arbiter_identifier'))


@router.delete('/participant/{participant_id}', response={204: None})
@decorate_view(login_required_error, admin_csrf_required, ratelimit(key='user', rate='30/m', block=True))
def delete_participant(request: HttpRequest, participant_id: int):
    """
    - `login_required_error`
    - `admin_csrf_required`
    - `ratelimit(key='user', rate='30/m', block=True)`

    Only the tournament host or staff may delete a participant.
    GSC participants cannot be deleted while the tournament state is NORMAL.
    Participants with any associated video cannot be deleted.
    """
    participant = get_object_or_404(TournamentParticipant.objects.select_related('tournament'), id=participant_id)
    if not request.user.is_staff and participant.tournament.host_id != request.user.id:
        raise HttpError(403, 'Only the tournament host or staff may delete a participant.')
    if participant.tournament.subclass == Tournament_TextChoices.Subclass.GSC and participant.tournament.state == Tournament_TextChoices.State.NORMAL:
        raise HttpError(403, 'Participants of a NORMAL GSC tournament cannot be deleted.')
    if participant.videos.exists():
        raise HttpError(409, 'Participants with tournament videos cannot be deleted.')
    participant.delete()
    return 204, None


@router.get('/user-ranking', response=TournamentUserRankingOut)
def get_tournament_user_ranking(
    request: HttpRequest,
    sort_by: str = 'score_current',
    start: int = 0, end: int = 20,
):
    if sort_by not in TOURNAMENT_USER_CACHE_KEYS:
        raise HttpError(400, 'Invalid tournament user ranking field.')
    start = max(start, 0)
    end = min(max(end, start), start + 100)
    data, total = cache.get_tournament_user_ranking(sort_by, start=start, end=end)
    return {'total': total, 'data': data}


@router.post('/video/{video_id}/reveal', response={204: None})
@decorate_view(login_required_error, ratelimit(key='user', rate='30/m', block=True))
def reveal_video(request: HttpRequest, video_id: int):
    """
    - `login_required_error`
    - `ratelimit(key='user', rate='30/m', block=True)`

    Permanently reveal an owned video without removing any tournament associations.
    """
    with transaction.atomic():
        video = get_object_or_404(VideoModel.objects.select_for_update(), id=video_id)
        if video.player_id != request.user.id:
            raise HttpError(403, 'Only the video owner may reveal it.')
        if video.ongoing_tournament:
            video.ongoing_tournament = False
            # speedranking 的保存信号在事务提交后尝试加入竞速纪录。
            video.save(update_fields=['ongoing_tournament'])
    return 204, None


@router.get('/get_videos/participant', response=list[VideoBaseOut])
def get_participant_videos(request: HttpRequest, tournament_id: int, user_id: int):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    if tournament.state != Tournament_TextChoices.State.AWARDED and request.user.id != user_id:
        return HttpResponseForbidden()
    participant = TournamentParticipant.objects.filter(user_id=user_id, tournament=tournament).first()
    return participant.videos if participant else []


@router.get('/get_videos/tournament', response=list[VideoBaseOut])
@decorate_view(ratelimit(key='ip', rate='1/5s'))
def get_tournament_videos(request: HttpRequest, tournament_id: int):
    """
    - `ratelimit(key='ip', rate='1/5s')`
    """
    tournament = get_object_or_404(Tournament, id=tournament_id)
    if tournament.state != Tournament_TextChoices.State.AWARDED:
        return HttpResponseForbidden()
    return tournament.videos.all()


@router.get('/get_news', response=TournamentNewsOut)
def get_tournament_news(request: HttpRequest):
    now = datetime.now(tz=timezone.utc)
    normal_tournaments = cache.get_tournament_all()
    return {
        'preparing': [
            {'id': tournament.id, 'start_time': tournament.start_time}
            for tournament in normal_tournaments
            if tournament.start_time is not None and tournament.start_time > now
        ],
        'ongoing': [
            {'id': tournament.id, 'end_time': tournament.end_time}
            for tournament in normal_tournaments
            if tournament.start_time is not None
            and tournament.end_time is not None
            and tournament.start_time <= now < tournament.end_time
        ],
    }


@router.get('/download')
@decorate_view(ratelimit(key='ip', rate='1/h'))
def download_all_videos(request: HttpRequest, tournament_id: int):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    if tournament.state != Tournament_TextChoices.State.AWARDED:
        return HttpResponseForbidden()
    response = StreamingHttpResponse(generate_file_stream(tournament.videos.all()), content_type='application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename="all_files_stream.bin"'
    return response


@router.get('/download/participant')
@decorate_view(ratelimit(key='ip', rate='1/m'))
def download_videos_participant(request: HttpRequest, tournament_id: int, user_id: int):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    if tournament.state != Tournament_TextChoices.State.AWARDED and request.user.id != user_id:
        return HttpResponseForbidden()
    response = StreamingHttpResponse(generate_file_stream(tournament.videos.filter(player_id=user_id)), content_type='application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename="all_files_stream.bin"'
    return response
