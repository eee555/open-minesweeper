from datetime import datetime

from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Field, File, Form, Router, Schema
from ninja.decorators import decorate_view
from ninja.files import UploadedFile
from ninja.orm import create_schema
from pydantic import PositiveInt

from config.text_choices import Tournament_TextChoices
from config.tournaments import TournamentWeights
from identifier.models import Identifier
from identifier.services import bind_identifier
from identifier.utils import verify_identifier
from tournament.gsc.decorators import GSC_admin_required
from tournament.models import GSCParticipant, GSCTournament
from tournament.schema import ParticipantOutBase
from userprofile.decorators import admin_csrf_required, login_required_error
from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from utils.response import HttpResponseConflict, realname_required_response
from utils.schema import DBTaskOut, MySQLPositiveInteger
from videomanager.schema import VideoBaseOut
from .services import bind_gsc_history_identifier, get_gsc_scores, import_gsc_history_scores, prepare_gsc_history_videos, upload_gsc_history_video
from .tasks import helper_gsc_finish_tournament

router = Router()


class NewGSCTournamentIn(Schema):
    id: int
    start_time: datetime | None = None
    end_time: datetime | None = None


class RegisterGSCParticipantIn(Schema):
    identifier: str
    order: int


class GSCOrderIn(Schema):
    order: int


GSCInfoOut = create_schema(
    GSCTournament,
    fields=['id', 'order', 'start_time', 'end_time', 'state'],
    custom_fields=[
        ('token', str, ''),
    ],
)


GSCScoreOut = create_schema(
    GSCParticipant,
    fields=[
        'id',
        'start_time', 'end_time',
        'rank', 'rank_score',
        'bt1st', 'bt20th', 'bt20sum',
        'it1st', 'it12th', 'it12sum',
        'et1st', 'et5th', 'et5sum',
        'manual_scores',
    ],
    custom_fields=[
        ('user_id', int, 0),
        ('has_videos', bool, False),
        ('arbiter_identifier', str | None, Field(None, alias='arbiter_identifier.identifier')),
    ],
    base_class=ParticipantOutBase,
)


class HistoryPrepareIn(Schema):
    order: PositiveInt
    user_id: PositiveInt


class HistoryIdentifierIn(Schema):
    identifier: str = Field(max_length=80)


class IdentifierBindingOut(Schema):
    identifier: str
    bound: bool


class HistoryScoreIn(Schema):
    bt1st: MySQLPositiveInteger
    bt20th: MySQLPositiveInteger
    bt20sum: MySQLPositiveInteger
    it1st: MySQLPositiveInteger
    it12th: MySQLPositiveInteger
    it12sum: MySQLPositiveInteger
    et1st: MySQLPositiveInteger
    et5th: MySQLPositiveInteger
    et5sum: MySQLPositiveInteger


class HistoryUserScoreIn(HistoryScoreIn):
    user_id: PositiveInt


class HistoryAnonymousScoreIn(HistoryScoreIn):
    arbiter_identifier: str = Field(min_length=1, max_length=80)


class HistoryUserBatchIn(Schema):
    order: PositiveInt
    rows: list[HistoryUserScoreIn] = Field(min_length=1, max_length=10)


class HistoryAnonymousBatchIn(Schema):
    order: PositiveInt
    rows: list[HistoryAnonymousScoreIn] = Field(min_length=1, max_length=10)


def _get_history_tournament(request: HttpRequest, order: int):
    tournament = get_object_or_404(GSCTournament.objects.select_for_update(), order=order)
    if not request.user.is_staff and tournament.host_id != request.user.pk:
        raise ExceptionToResponse('tournament', 'permission', status_code=403)
    if tournament.state != Tournament_TextChoices.State.AWARDED or tournament.end_time is None:
        raise ExceptionToResponse('tournament', 'not_awarded', status_code=409)
    return tournament


def _get_history_video_participant(request: HttpRequest, participant_id: int):
    participant = get_object_or_404(GSCParticipant.objects.select_related('user', 'tournament__gsctournament'), pk=participant_id)
    _get_history_tournament(request, participant.tournament.gsctournament.order)
    if participant.manual_scores or participant.user_id is None:
        raise ExceptionToResponse('participant', 'not_video_source', status_code=409)
    return participant


@router.post('/history/prepare', response=GSCScoreOut)
@decorate_view(login_required_error, admin_csrf_required)
def create_history_participant(request: HttpRequest, data: HistoryPrepareIn):
    """
    - `login_required_error`
    - `admin_csrf_required`

    获取或创建录像来源参赛者，已有非手工记录原样返回，手工来源拒绝。
    """
    with transaction.atomic():
        tournament = _get_history_tournament(request, data.order)
        user = get_object_or_404(UserProfile.objects.select_for_update(), pk=data.user_id)
        return prepare_gsc_history_videos(tournament, user)


@router.post('/history/participants/{participant_id}/identifier', response=IdentifierBindingOut)
@decorate_view(login_required_error, admin_csrf_required)
def bind_history_identifier(request: HttpRequest, participant_id: int, data: HistoryIdentifierIn):
    """
    - `login_required_error`
    - `admin_csrf_required`
    """
    with transaction.atomic():
        participant = _get_history_video_participant(request, participant_id)
        return bind_gsc_history_identifier(participant, data.identifier)


@router.post('/history/participants/{participant_id}/videos', response=VideoBaseOut)
@decorate_view(login_required_error, admin_csrf_required)
def upload_history_video(request: HttpRequest, participant_id: int, upload_time: datetime = Form(...), file: UploadedFile = File(...)):  # noqa: B008
    """
    - `login_required_error`
    - `admin_csrf_required`
    """
    try:
        with transaction.atomic():
            participant = _get_history_video_participant(request, participant_id)
            return upload_gsc_history_video(participant, file, upload_time)
    except ExceptionToResponse as exc:
        status = exc.status_code if exc.status_code >= 400 else 400
        raise ExceptionToResponse(exc.obj, exc.category, status_code=status) from exc


@router.post('/history/scores/users', response=int)
@decorate_view(login_required_error, admin_csrf_required)
def import_history_user_scores(request: HttpRequest, data: HistoryUserBatchIn):
    """
    - `login_required_error`
    - `admin_csrf_required`
    """
    with transaction.atomic():
        tournament = _get_history_tournament(request, data.order)
        return import_gsc_history_scores(tournament, data.rows)


@router.post('/history/scores/anonymous', response=int)
@decorate_view(login_required_error, admin_csrf_required)
def import_history_anonymous_scores(request: HttpRequest, data: HistoryAnonymousBatchIn):
    """
    - `login_required_error`
    - `admin_csrf_required`
    """
    with transaction.atomic():
        tournament = _get_history_tournament(request, data.order)
        return import_gsc_history_scores(tournament, data.rows, anonymous=True)


def task_response(task):
    return {
        'type': 'success',
        'data': {
            'task_id': str(task.id),
        },
    }


@router.post('/new')
@decorate_view(GSC_admin_required)
def new_GSC_tournament(request: HttpRequest, data: NewGSCTournamentIn = Form(...)):  # noqa: B008
    """
    - `GSC_admin_required`

    GSC 主办方或管理员可创建比赛。
    """
    if GSCTournament.objects.filter(order=data.id).exists():
        return HttpResponseConflict()

    GSCTournament.objects.create(
        start_time=data.start_time,
        end_time=data.end_time,
        state=Tournament_TextChoices.State.PENDING,
        host=request.user,
        weight=TournamentWeights.GSC,
        order=data.id,
    )

    return HttpResponse()


@router.get('/admin-info', response=GSCInfoOut)
def get_GSC_tournament(request: HttpRequest, order: int):
    return get_object_or_404(GSCTournament, order=order)


@router.get('/results', response=list[GSCScoreOut])
def get_results(request: HttpRequest, tournament_id: int):
    tournament = get_object_or_404(GSCTournament, tournament_ptr_id=tournament_id)
    if tournament.state != Tournament_TextChoices.State.AWARDED:
        return HttpResponseForbidden()
    return list(get_gsc_scores(tournament))


@router.post('/participant')
@decorate_view(login_required_error)
def create_gsc_participant(request: HttpRequest, data: GSCOrderIn = Form(...)):  # noqa: B008
    user = request.user
    if not user.has_realname():
        return realname_required_response()
    tournament = get_object_or_404(GSCTournament, order=data.order)
    if tournament.state != Tournament_TextChoices.State.NORMAL or tournament.end_time is None or timezone.now() >= tournament.end_time:
        return HttpResponseForbidden()
    if not tournament._token:
        return HttpResponseForbidden()

    GSCParticipant.objects.get_or_create(
        tournament=tournament,
        user=user,
        defaults={
            'token': tournament._token,
            'start_time': tournament.start_time,
            'end_time': tournament.end_time,
        },
    )
    return {'type': 'success'}


@router.post('/participant/identifier')
@decorate_view(login_required_error)
def register_gsc_participant_identifier(request: HttpRequest, data: RegisterGSCParticipantIn = Form(...)):  # noqa: B008
    user: UserProfile = request.user
    tournament = get_object_or_404(GSCTournament, order=data.order)
    if not tournament.is_ongoing():
        return HttpResponseForbidden()
    if not tournament.token:
        return HttpResponseForbidden()
    participant = get_object_or_404(GSCParticipant, tournament=tournament, user=user)
    if not data.identifier.endswith(tournament.token):
        raise ExceptionToResponse('identifier', 'suffix')

    if not verify_identifier(data.identifier):
        raise ExceptionToResponse('identifier', 'invalid')
    identifier = Identifier.objects.get(identifier=data.identifier)
    if identifier.userms_id and identifier.userms_id != user.userms_id:
        raise ExceptionToResponse('identifier', 'collision')
    if participant.arbiter_identifier:
        raise ExceptionToResponse('participant', 'registered')
    participant.arbiter_identifier = identifier
    participant.save(update_fields=['arbiter_identifier'])
    if not identifier.userms:
        bind_identifier(identifier, user.userms)
    return {'type': 'success'}


@router.get('/task', response=DBTaskOut | None)
@decorate_view(GSC_admin_required)
def get_gsc_task(request: HttpRequest, order: int):
    """
    - `GSC_admin_required`

    GSC 主办方或管理员可查看结算任务。
    """
    return get_object_or_404(GSCTournament, order=order).task


@router.post('/task/finish')
@decorate_view(GSC_admin_required)
def finish_gsc_task(request: HttpRequest, data: GSCOrderIn = Form(...)):  # noqa: B008
    """
    - `GSC_admin_required`

    GSC 主办方或管理员可启动已结束比赛的结算任务。
    """
    tournament = get_object_or_404(GSCTournament, order=data.order)
    if not tournament.is_ended():
        return HttpResponseForbidden()

    return task_response(helper_gsc_finish_tournament(tournament))
