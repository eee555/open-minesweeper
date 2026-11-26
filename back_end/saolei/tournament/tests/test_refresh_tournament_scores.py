from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError

from config.text_choices import MS_TextChoices, Tournament_TextChoices
from tournament.cache import cache, TOURNAMENT_USER_CACHE_KEYS
from tournament.gsc.utils import gsc_encode_best
from tournament.models import GSCParticipant, GSCTournament, Tournament, TournamentUser, WeeklyParticipant
from tournament.weekly.utils import weekly_encode_best
from videomanager.models import VideoModel
from .base import timedelta, timezone, TournamentTestCaseBase


class RefreshTournamentScoresTests(TournamentTestCaseBase):
    def test_recalculates_historical_scores_ranks_and_decayed_points_idempotently(self):
        last_updated = timezone.now()
        end_time = last_updated - timedelta(days=365 * 2)
        tournament = self.create_weekly_tournament(
            state=Tournament_TextChoices.State.AWARDED,
            start_time=end_time - timedelta(days=7),
            end_time=end_time,
        )
        other_user = self.create_user('weekly_recalculate_other')
        first = WeeklyParticipant.objects.create(user=self.user, tournament=tournament, classic_score=100000, rank=2, rank_score=25)
        second = WeeklyParticipant.objects.create(user=other_user, tournament=tournament, classic_score=200000, rank=1, rank_score=50)
        later_tournament = self.create_weekly_tournament(week=2, state=Tournament_TextChoices.State.AWARDED, end_time=last_updated)
        WeeklyParticipant.objects.create(user=self.user, tournament=later_tournament, classic_score=700000)
        TournamentUser.objects.filter(user_id__in=[self.user.id, other_user.id]).update(
            score_current=100, last_updated=last_updated, score_total=100, weekly_total=100, weekly_classic_total=100,
        )
        first_video = self.create_video(tournament_identifier=[], level=MS_TextChoices.Level.EXPERT, timems=100000)
        second_video = self.create_video(user=other_user, tournament_identifier=[], level=MS_TextChoices.Level.EXPERT, timems=110000)
        tournament.videos.add(first_video, second_video)
        VideoModel.objects.filter(pk=first_video.pk).update(ongoing_tournament=True)
        output = StringIO()

        for _ in range(2):
            with self.captureOnCommitCallbacks(execute=True):
                call_command('refresh_tournament_scores', tournament.id, batch_size=1, stdout=output)
            first.refresh_from_db()
            second.refresh_from_db()
            self.assertEqual((first.classic_score, first.rank, first.rank_score), (640000, 1, 50))
            self.assertEqual((second.classic_score, second.rank, second.rank_score), (650000, 2, 25))
            for user, current, total, best in (
                (self.user, 112.5, 125, 640000),
                (other_user, 87.5, 75, 650000),
            ):
                record = TournamentUser.objects.get(user=user)
                self.assertEqual(record.last_updated, last_updated)
                self.assertEqual(record.score_current, current)
                self.assertEqual((record.score_total, record.weekly_total, record.weekly_classic_total), (total, total, total))
                self.assertEqual(record.weekly_classic_best, weekly_encode_best(best, tournament.year, tournament.week))
                self.assert_cached_current_score(record)
                self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_total'], user.id), total)
                self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_classic_best'], user.id), record.weekly_classic_best)

        first_video.state = MS_TextChoices.State.FROZEN
        first_video.save(update_fields=['state'])
        with self.captureOnCommitCallbacks(execute=True):
            call_command('refresh_tournament_scores', tournament.id, stdout=StringIO())
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.classic_score, first.rank, first.rank_score), (780000, 2, 25))
        self.assertEqual((second.classic_score, second.rank, second.rank_score), (650000, 1, 50))
        for user in (self.user, other_user):
            record = TournamentUser.objects.get(user=user)
            self.assertEqual((record.score_current, record.score_total), (100, 100))
            self.assertEqual(record.last_updated, last_updated)
        record = TournamentUser.objects.get(user=self.user)
        self.assertEqual(record.weekly_classic_best, weekly_encode_best(700000, later_tournament.year, later_tournament.week))
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_classic_best'], self.user.id), record.weekly_classic_best)
        first_video.refresh_from_db()
        tournament.refresh_from_db()
        self.assertTrue(first_video.ongoing_tournament)
        self.assertEqual(tournament.state, Tournament_TextChoices.State.AWARDED)
        self.assertIn('重算完成', output.getvalue())

    def test_recalculates_gsc_by_tournament_id_and_rebuilds_best_when_scores_worsen(self):
        last_updated = timezone.now()
        end_time = last_updated - timedelta(days=365 * 2)
        tournament = GSCTournament.objects.create(
            order=99, weight=50, state=Tournament_TextChoices.State.AWARDED,
            start_time=end_time - timedelta(days=1), end_time=end_time,
        )
        self.assertNotEqual(tournament.id, tournament.order)
        other_user = self.create_user('gsc_recalculate_other')
        first = GSCParticipant.objects.create(user=self.user, tournament=tournament, et5sum=1000000, rank=2, rank_score=25)
        second = GSCParticipant.objects.create(user=other_user, tournament=tournament, et5sum=1100000, rank=1, rank_score=50)
        later_tournament = GSCTournament.objects.create(order=100, state=Tournament_TextChoices.State.AWARDED, end_time=last_updated)
        GSCParticipant.objects.create(user=self.user, tournament=later_tournament, et5sum=1100000)
        TournamentUser.objects.filter(user_id__in=[self.user.id, other_user.id]).update(
            score_current=100, last_updated=last_updated, score_total=100, gsc_total=100,
        )
        first_video = self.create_video(tournament_identifier=[], level=MS_TextChoices.Level.EXPERT, bv=100, timems=100000)
        second_video = self.create_video(user=other_user, tournament_identifier=[], level=MS_TextChoices.Level.EXPERT, bv=100, timems=110000)
        tournament.videos.add(first_video, second_video)
        VideoModel.objects.filter(pk=first_video.pk).update(ongoing_tournament=True)
        output = StringIO()

        for _ in range(2):
            with self.captureOnCommitCallbacks(execute=True):
                call_command('refresh_tournament_scores', tournament.id, batch_size=1, stdout=output)
            first.refresh_from_db()
            second.refresh_from_db()
            self.assertEqual((first.t37, first.rank, first.rank_score), (1980000, 1, 50))
            self.assertEqual((second.t37, second.rank, second.rank_score), (1990000, 2, 25))
            for user, current, total, best in (
                (self.user, 112.5, 125, 1980000),
                (other_user, 87.5, 75, 1990000),
            ):
                record = TournamentUser.objects.get(user=user)
                self.assertEqual(record.last_updated, last_updated)
                self.assertEqual(record.score_current, current)
                self.assertEqual((record.score_total, record.gsc_total), (total, total))
                self.assertEqual((record.weekly_total, record.weekly_classic_total), (0, 0))
                self.assertEqual(record.gsc_best, gsc_encode_best(best, tournament.order))
                self.assert_cached_current_score(record)
                self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['gsc_total'], user.id), total)
                self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['gsc_best'], user.id), record.gsc_best)

        VideoModel.objects.filter(pk=first_video.pk).update(state=MS_TextChoices.State.FROZEN)
        with self.captureOnCommitCallbacks(execute=True):
            call_command('refresh_tournament_scores', tournament.id, stdout=StringIO())
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.t37, first.rank, first.rank_score), (2120000, 2, 25))
        self.assertEqual((second.t37, second.rank, second.rank_score), (1990000, 1, 50))
        for user in (self.user, other_user):
            record = TournamentUser.objects.get(user=user)
            self.assertEqual((record.score_current, record.score_total, record.gsc_total), (100, 100, 100))
            self.assertEqual(record.last_updated, last_updated)
        record = TournamentUser.objects.get(user=self.user)
        self.assertEqual(record.gsc_best, gsc_encode_best(2020000, later_tournament.order))
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['gsc_best'], self.user.id), record.gsc_best)
        first_video.refresh_from_db()
        tournament.refresh_from_db()
        self.assertTrue(first_video.ongoing_tournament)
        self.assertEqual(tournament.state, Tournament_TextChoices.State.AWARDED)
        self.assertIsNone(tournament.task_id)
        self.assertIn('GSC#99', output.getvalue())

    def test_rejects_invalid_requests_before_recalculating(self):
        tournament = self.create_weekly_tournament()
        participant = WeeklyParticipant.objects.create(user=self.user, tournament=tournament, classic_score=123456)
        for tournament_id, options in (
            (tournament.id, {}),
            (self.tournament.id, {}),
            (-1, {}),
            (tournament.id, {'batch_size': 0}),
            (tournament.id, {'batch_size': -1}),
        ):
            with self.subTest(tournament_id=tournament_id, options=options), self.assertRaises(CommandError):
                call_command('refresh_tournament_scores', tournament_id, stdout=StringIO(), **options)
        tournament.state = Tournament_TextChoices.State.AWARDED
        tournament.end_time = None
        tournament.save(update_fields=['state', 'end_time'])
        with self.assertRaisesMessage(CommandError, '只能重算已颁奖且有结束时间的比赛'):
            call_command('refresh_tournament_scores', tournament.id, stdout=StringIO())
        participant.refresh_from_db()
        self.assertEqual(participant.classic_score, 123456)
        self.assertIsNone(participant.rank)
        self.assertEqual(participant.rank_score, 0)

    def test_rejects_unsupported_tournament_types_and_weekly_formats(self):
        tournament = Tournament.objects.create(state=Tournament_TextChoices.State.AWARDED, end_time=timezone.now())
        with self.assertRaisesMessage(CommandError, '当前只支持 GSC、竞速及效率打卡赛'):
            call_command('refresh_tournament_scores', tournament.id, stdout=StringIO())
        weekly = self.create_weekly_tournament(state=Tournament_TextChoices.State.AWARDED, tournament_format='?')
        with self.assertRaisesMessage(CommandError, '不支持的竞速打卡赛赛制'):
            call_command('refresh_tournament_scores', weekly.id, stdout=StringIO())

    def test_failure_rolls_back_database_changes(self):
        tournament = self.create_weekly_tournament(state=Tournament_TextChoices.State.AWARDED)
        participant = WeeklyParticipant.objects.create(user=self.user, tournament=tournament, classic_score=123456, rank=2, rank_score=25)
        with patch('tournament.management.commands.refresh_tournament_scores.award_tournament_rank_scores', side_effect=RuntimeError('award failed')):
            with self.assertRaisesMessage(RuntimeError, 'award failed'):
                call_command('refresh_tournament_scores', tournament.id, stdout=StringIO())
        participant.refresh_from_db()
        self.assertEqual((participant.classic_score, participant.rank, participant.rank_score), (123456, 2, 25))

    def test_gsc_failure_rolls_back_database_changes(self):
        tournament = GSCTournament.objects.create(order=99, state=Tournament_TextChoices.State.AWARDED, end_time=timezone.now())
        participant = GSCParticipant.objects.create(user=self.user, tournament=tournament, et5sum=123456, rank=2, rank_score=25)
        with patch('tournament.management.commands.refresh_tournament_scores.award_tournament_rank_scores', side_effect=RuntimeError('award failed')):
            with self.assertRaisesMessage(RuntimeError, 'award failed'):
                call_command('refresh_tournament_scores', tournament.id, stdout=StringIO())
        participant.refresh_from_db()
        self.assertEqual((participant.et5sum, participant.rank, participant.rank_score), (123456, 2, 25))

    def test_zero_point_history_preserves_latest_ended_tournament_time(self):
        end_time = timezone.now() - timedelta(days=1)
        tournament = self.create_weekly_tournament(state=Tournament_TextChoices.State.AWARDED, end_time=end_time)
        WeeklyParticipant.objects.create(user=self.user, tournament=tournament, rank=1, rank_score=0)
        record = TournamentUser.objects.get(user=self.user)

        record.add_score(50, end_time - timedelta(days=365 * 2), category='weekly_classic')

        self.assertEqual(record.last_updated, end_time)
        self.assertEqual(record.score_current, 25)
        self.assertEqual((record.score_total, record.weekly_total, record.weekly_classic_total), (50, 50, 50))
