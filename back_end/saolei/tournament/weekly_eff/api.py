from datetime import timedelta

from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from ninja import Form, Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.orm import create_schema

from config.text_choices import Tournament_TextChoices
from config.tournaments import TournamentWeights
from tournament.models import WeeklyEffParticipant, WeeklyEffTournament
from tournament.schema import ParticipantOutBase
from tournament.utils import get_next_week_window, TOURNAMENT_FINISH_DELAY
from userprofile.decorators import login_required_error, staff_required
from userprofile.utils import has_identity_access
from utils.response import identity_access_required_response
from utils.schema import IdIn
from .tasks import task_weekly_eff_finish

router = Router()

WeeklyEffInfoOut = create_schema(WeeklyEffTournament, fields=['id', 'year', 'week', 'start_time', 'end_time', 'state'])
WeeklyEffScoreOut = create_schema(
    WeeklyEffParticipant,
    fields=['id', 'start_time', 'end_time', 'rank', 'rank_score', 'et', 'it', 'score'],
    custom_fields=[('user_id', int, 0)], base_class=ParticipantOutBase,
)
WeeklyEffRegisterOut = create_schema(
    WeeklyEffParticipant,
    fields=['id', 'token', 'start_time', 'end_time', 'rank', 'rank_score'],
    custom_fields=[('user_id', int, 0), ('tournament_id', int, 0), ('has_videos', bool, False)],
    base_class=ParticipantOutBase,
)


class NewWeeklyEffTournamentOut(Schema):
    data: WeeklyEffInfoOut


@router.post('/new', response=NewWeeklyEffTournamentOut)
@decorate_view(staff_required)
def new_weekly_eff_tournament(request: HttpRequest):
    """- staff_required"""
    year, week, start_time, end_time = get_next_week_window()
    tournament, created = WeeklyEffTournament.objects.get_or_create(
        year=year, week=week,
        defaults={
            'start_time': start_time, 'end_time': end_time, 'host': request.user,
            'weight': TournamentWeights.WEEKLY_EFF, 'subclass': Tournament_TextChoices.Subclass.WEEKLY_EFF,
        },
    )
    if not created:
        raise HttpError(409, 'An efficiency weekly tournament already exists for this week.')
    tournament.save(update_fields=tournament.validate())
    task_weekly_eff_finish.using(run_after=end_time + TOURNAMENT_FINISH_DELAY).enqueue(tournament.id)
    return {'data': tournament}


@router.get('/results', response=list[WeeklyEffScoreOut])
@decorate_view(ratelimit(key='ip', rate='60/m', block=True))
def get_results(request: HttpRequest, tournament_id: int):
    """- ratelimit(key='ip', rate='60/m', block=True)"""
    tournament = get_object_or_404(WeeklyEffTournament, id=tournament_id)
    if tournament.state != Tournament_TextChoices.State.AWARDED:
        raise HttpError(403, 'Results are only available after awards.')
    return WeeklyEffParticipant.objects.filter(tournament=tournament)


@router.post('/participant', response=WeeklyEffRegisterOut)
@decorate_view(login_required_error, ratelimit(key='user', rate='30/m', block=True))
def create_weekly_eff_participant(request: HttpRequest, data: IdIn = Form(...)):  # noqa: B008
    """
    - login_required_error
    - ratelimit(key='user', rate='30/m', block=True)
    """
    if not has_identity_access(request.user):
        return identity_access_required_response()
    tournament = get_object_or_404(WeeklyEffTournament, id=data.id)
    if not tournament.is_ongoing():
        raise HttpError(403, 'The tournament is not ongoing.')
    now = timezone.now()
    participant, _ = WeeklyEffParticipant.objects.get_or_create(
        user=request.user, tournament=tournament,
        defaults={'start_time': now, 'end_time': min(now + timedelta(hours=2), tournament.end_time)},
    )
    participant.has_videos = participant.videos.exists()
    return participant
