from datetime import datetime, timedelta
from io import StringIO
import json

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from config.text_choices import MS_TextChoices, Tournament_TextChoices
from config.tournaments import GSC_Defaults
from identifier.models import Identifier
from msuser.models import UserMS
from speedranking.pb.cache import PBRankingCache
from speedranking.saolei.cache import SpeedRankingCache
from speedranking.saolei.utils import RANK_STATS
from speedranking.top.cache import TopRankingCache
from tournament.gsc.utils import gsc_encode_best
from tournament.utils import MAX_TOURNAMENT_BEST, tournament_score_decay_factor
from tournament.weekly.utils import weekly_encode_best
from userprofile.models import UserProfile
from videomanager.models import ExpandVideoModel, VideoModel
from ..cache import (
    cache,
    CachedNormalParticipant,
    NORMAL_PARTICIPANT_CACHE_KEY,
    NORMAL_TOURNAMENT_CACHE_KEY,
    TOURNAMENT_USER_CACHE_KEYS,
    TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY,
    TournamentCache,
)
from ..gsc.services import refresh_gsc_scores
from ..gsc.tasks import _task_gsc_finish_impl, _task_gsc_refresh_best_impl
from ..models import (
    GSCParticipant,
    GSCTournament,
    Tournament,
    TournamentParticipant,
    TournamentUser,
    WeeklyParticipant,
    WeeklyTournament,
)
from ..services import (
    award_tournament_rank_scores,
    refresh_tournament_ranks,
    reveal_videos_for_tournament,
)
from ..tasks import _task_award_tournament_impl
from ..weekly.services import refresh_weekly_best_scores, refresh_weekly_classic_scores
from ..weekly.tasks import _task_weekly_finish_impl, _task_weekly_refresh_best_impl


class TournamentTestCaseBase(TestCase):
    def setUp(self):
        pb = PBRankingCache()
        pb.flush()
        self.addCleanup(pb.flush)
        top = TopRankingCache()
        top.flush()
        self.addCleanup(top.flush)
        for ranking_name in ('saolei', 'saolei_nf'):
            ranking = SpeedRankingCache(ranking_name, stats=RANK_STATS)
            ranking.flush()
            self.addCleanup(ranking.flush)
        cache.delete(
            NORMAL_TOURNAMENT_CACHE_KEY,
            NORMAL_PARTICIPANT_CACHE_KEY,
            *TOURNAMENT_USER_CACHE_KEYS.values(),
            TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY,
        )
        self.tournament_cache = TournamentCache()
        self.addCleanup(self.tournament_cache.clear_tournament_user_cache)
        userms = UserMS.objects.create()
        self.user = UserProfile.objects.create_user(
            username='tournament_user',
            email='tournament@example.com',
            password='password',
            userms=userms,
        )
        now = timezone.now()
        self.tournament = GSCTournament.objects.create(
            order=1,
            _token='G12345',
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            state=Tournament_TextChoices.State.NORMAL,
        )
        self.tournament_cache.update_tournament(self.tournament)

    def create_user(self, username):
        return UserProfile.objects.create_user(
            username=username,
            email=f'{username}@example.com',
            password='password',
            userms=UserMS.objects.create(),
        )

    def assert_cached_current_score(self, tournament_user):
        score_time = datetime.fromisoformat(cache.get(TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY).decode())
        expected = tournament_user.score_current * tournament_score_decay_factor(tournament_user.last_updated, score_time)
        self.assertAlmostEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['score_current'], tournament_user.user_id), expected)

    def create_video(
        self,
        *,
        user=None,
        tournament_identifier=None,
        identifier=None,
        software=MS_TextChoices.Software.EVF,
        level=MS_TextChoices.Level.BEGINNER,
        mode=MS_TextChoices.Mode.STD,
        timems=1000,
        bv=10,
        right_ce=1,
    ):
        video_index = ExpandVideoModel.objects.count() + 1
        tournament_identifier = tournament_identifier if tournament_identifier is not None else [self.tournament.token]
        expand_video = ExpandVideoModel.objects.create(
            identifier=identifier or f'gsc-video-{video_index}',
            tournament_identifier=tournament_identifier,
        )
        video = VideoModel(
            player=user or self.user,
            file=f'videos/test-{video_index}.evf',
            file_size=1,
            video=expand_video,
            state=MS_TextChoices.State.OFFICIAL,
            software=software,
            level=level,
            mode=mode,
            timems=timems,
            bv=bv,
            left=1,
            right=1,
            double=1,
            left_ce=1,
            right_ce=right_ce,
            double_ce=1,
            path=1.0,
            flag=1,
            op=1,
            isl=1,
        )
        video.save()  # noqa: DJM100
        return video

    def create_cached_gsc_participant(self, *, user=None, tournament=None, token=None):
        tournament = tournament or self.tournament
        participant = GSCParticipant.objects.create(
            user=user or self.user,
            tournament=tournament,
            token=token or tournament.token,
            start_time=tournament.start_time,
            end_time=tournament.end_time,
        )
        self.tournament_cache.update_participant(participant)
        return participant

    def create_weekly_tournament(self, **kwargs):
        now = timezone.now()
        defaults = {
            'year': 2026,
            'week': 1,
            'subclass': Tournament_TextChoices.Subclass.WEEKLY,
            'start_time': now - timedelta(hours=1),
            'end_time': now + timedelta(hours=1),
            'state': Tournament_TextChoices.State.NORMAL,
            'host': self.user,
            'weight': 50,
            'tournament_format': Tournament_TextChoices.WeeklyFormat.CLASSIC,
        }
        defaults.update(kwargs)
        return WeeklyTournament.objects.create(**defaults)


__all__ = (
    'TournamentTestCaseBase',
    'timedelta',
    'StringIO',
    'json',
    'call_command',
    'timezone',
    'DBTaskResult',
    'MS_TextChoices',
    'Tournament_TextChoices',
    'GSC_Defaults',
    'Identifier',
    'UserMS',
    'gsc_encode_best',
    'MAX_TOURNAMENT_BEST',
    'weekly_encode_best',
    'UserProfile',
    'ExpandVideoModel',
    'VideoModel',
    'cache',
    'CachedNormalParticipant',
    'NORMAL_PARTICIPANT_CACHE_KEY',
    'NORMAL_TOURNAMENT_CACHE_KEY',
    'TOURNAMENT_USER_CACHE_KEYS',
    'TournamentCache',
    'refresh_gsc_scores',
    '_task_gsc_finish_impl',
    '_task_gsc_refresh_best_impl',
    'GSCParticipant',
    'GSCTournament',
    'Tournament',
    'TournamentParticipant',
    'TournamentUser',
    'WeeklyParticipant',
    'WeeklyTournament',
    'award_tournament_rank_scores',
    'refresh_tournament_ranks',
    'reveal_videos_for_tournament',
    '_task_award_tournament_impl',
    'refresh_weekly_best_scores',
    'refresh_weekly_classic_scores',
    '_task_weekly_finish_impl',
    '_task_weekly_refresh_best_impl',
)
