from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import Client
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from config.text_choices import MS_TextChoices, Tournament_TextChoices
from tournament.cache import cache, NORMAL_PARTICIPANT_CACHE_KEY, NORMAL_TOURNAMENT_CACHE_KEY, TOURNAMENT_USER_CACHE_KEYS
from tournament.models import Tournament, TournamentUser, WeeklyEffParticipant, WeeklyEffTournament, WeeklyParticipant
from tournament.services import award_tournament_rank_scores, disqualify_participant, refresh_tournament_ranks
from tournament.utils import TOURNAMENT_FINISH_DELAY
from tournament.weekly_eff.services import calculate_weekly_eff_best, refresh_weekly_eff_best_scores, refresh_weekly_eff_scores
from tournament.weekly_eff.signals import update_best_score_on_weekly_eff_participant_save
from tournament.weekly_eff.tasks import task_weekly_eff_finish
from .base import timedelta, TournamentTestCaseBase


class TestWeeklyEff(TournamentTestCaseBase):
    def setUp(self):
        super().setUp()
        self.user.realname = 'Efficiency Player'
        self.user.save(update_fields=['_realname', 'date_updated'])
        now = timezone.now()
        self.eff = WeeklyEffTournament.objects.create(
            year=2026, week=1, subclass=Tournament_TextChoices.Subclass.WEEKLY_EFF,
            state=Tournament_TextChoices.State.NORMAL, host=self.user, weight=50,
            start_time=now - timedelta(days=1), end_time=now + timedelta(days=1),
        )
        self.tournament_cache.update_tournament(self.eff)
        with self.captureOnCommitCallbacks(execute=True):
            self.participant = WeeklyEffParticipant.objects.create(
                user=self.user, tournament=self.eff, start_time=now - timedelta(hours=1), end_time=now + timedelta(hours=1),
            )

    def video(self, level='i', timems=10000, **kwargs):
        return self.create_video(level=level, timems=timems, tournament_identifier=[self.participant.token], **kwargs)

    def award(self):
        self.eff.state = Tournament_TextChoices.State.AWARDED
        self.eff.save(update_fields=['state'])

    def test_normal_participant_save_skips_best_queries(self):
        user = self.create_user('eff_query_user')
        tournament = Tournament.objects.get(pk=self.eff.pk)
        with patch.object(TournamentUser.objects, 'get_or_create', wraps=TournamentUser.objects.get_or_create) as ensure_user:
            participant = WeeklyEffParticipant.objects.create(
                user=user, tournament=tournament, start_time=self.participant.start_time, end_time=self.participant.end_time,
            )
        ensure_user.assert_called_once_with(user_id=user.pk)
        participant = WeeklyEffParticipant.objects.select_related('tournament').get(pk=participant.pk)
        with self.assertNumQueries(0):
            update_best_score_on_weekly_eff_participant_save(
                sender=WeeklyEffParticipant, instance=participant, created=False, update_fields={'score'},
            )

    def test_floating_score_selection_and_missing_defaults(self):
        expert = [self.video('e', timems=value, bv=7) for value in (100001, 80003, 90007)]
        intermediate = [self.video('i', timems=value, bv=7) for value in (10003, 12001, 11009)]
        self.assertEqual(refresh_weekly_eff_scores(self.eff), 1)
        self.participant.refresh_from_db()
        self.assertEqual([item[0] for item in self.participant.et], [expert[1].id, expert[2].id])
        self.assertEqual([item[0] for item in self.participant.it[:3]], [intermediate[0].id, intermediate[2].id, intermediate[1].id])
        expected = sum(value * 3 / 7000 for value in (80003, 90007, 10003, 11009, 12001)) + 120
        self.assertAlmostEqual(self.participant.score, expected)
        self.assertIsInstance(self.participant.et[0][1], float)
        expert[1].delete()
        refresh_weekly_eff_scores(self.eff)
        self.participant.refresh_from_db()
        self.assertEqual([item[0] for item in self.participant.et], [expert[2].id, expert[0].id])

    def test_filters_official_standard_metric_threshold_and_not_raw_time(self):
        accepted = self.video('i', timems=90000, bv=6)
        self.video('i', timems=60000, bv=3)
        self.video('e', timems=240000, bv=3)
        self.video('b')
        self.video('i', mode=MS_TextChoices.Mode.JSW)
        frozen = self.video('i', timems=1)
        type(frozen).objects.filter(pk=frozen.id).update(state=MS_TextChoices.State.FROZEN)
        self.video('i', timems=1, bv=0)
        nf = self.video('e', timems=150000, bv=6, right_ce=0)
        refresh_weekly_eff_scores(self.eff)
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.it, [[accepted.id, 45.0], [0, 60.0], [0, 60.0], [0, 60.0], [0, 60.0]])
        self.assertEqual(self.participant.et, [[nf.id, 75.0], [0, 240.0]])

    def test_registration_is_independent_and_caps_window(self):
        weekly = self.create_weekly_tournament()
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            first = self.client.post('/api/tournament/weekly/participant', {'id': weekly.id})
            second = self.client.post('/api/tournament/weekly-eff/participant', {'id': self.eff.id})
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertNotEqual(first.json()['token'], second.json()['token'])
        self.assertEqual({item.tournament for item in self.tournament_cache.get_participant_list(self.user.id)}, {weekly.id, self.eff.id})
        self.assertEqual(second.json()['id'], self.participant.id)
        other = self.create_user('eff_window_user')
        other.realname = 'Window Player'
        other.save(update_fields=['_realname', 'date_updated'])
        self.client.force_login(other)
        now = timezone.now()
        self.eff.end_time = now + timedelta(minutes=30)
        self.eff.save(update_fields=['end_time'])
        with patch('tournament.weekly_eff.api.timezone.now', return_value=now):
            response = self.client.post('/api/tournament/weekly-eff/participant', {'id': self.eff.id})
        self.assertEqual(response.status_code, 200)
        participant = WeeklyEffParticipant.objects.get(user=other)
        self.assertEqual(participant.start_time, now)
        self.assertEqual(participant.end_time, self.eff.end_time)

    def test_same_video_can_check_in_to_both_registered_tournaments(self):
        weekly = self.create_weekly_tournament()
        self.client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/tournament/weekly/participant', {'id': weekly.id})
        video = self.create_video(tournament_identifier=[self.participant.token, response.json()['token']])
        self.assertEqual(set(video.tournaments.values_list('id', flat=True)), {self.eff.id, weekly.id})

    def test_task_awards_points_best_and_recomputation_is_idempotent(self):
        self.video('i', timems=90000, bv=6)
        with self.captureOnCommitCallbacks(execute=True):
            task_weekly_eff_finish.call(self.eff.id)
            self.eff.refresh_from_db()
            award_tournament_rank_scores(self.eff)
            award_tournament_rank_scores(self.eff)
            refresh_weekly_eff_best_scores(self.eff)
        record = TournamentUser.objects.get(user=self.user)
        self.assertEqual(record.weekly_eff_total, 50)
        self.assertEqual(record.weekly_total, 0)
        self.assertEqual(record.score_total, 50)
        self.assertEqual(record.weekly_eff_best, 765.0)
        self.assertEqual((record.weekly_eff_best_year, record.weekly_eff_best_week), (2026, 1))
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_eff_best'], self.user.id), 765.0)
        self.assertEqual(self.eff.state, Tournament_TextChoices.State.AWARDED)
        self.assertFalse(self.eff.videos.filter(ongoing_tournament=True).exists())
        self.client.force_login(self.user)
        results = self.client.get('/api/tournament/weekly-eff/results', {'tournament_id': self.eff.id})
        self.assertEqual(results.status_code, 200)
        self.assertEqual(results.json()[0]['score'], 765.0)

    def test_disqualification_after_award_does_not_restore_scores(self):
        self.video()
        refresh_weekly_eff_scores(self.eff)
        refresh_tournament_ranks(self.eff)
        self.award()
        with self.captureOnCommitCallbacks(execute=True):
            award_tournament_rank_scores(self.eff)
            refresh_weekly_eff_best_scores(self.eff)
            disqualify_participant(self.participant.id, tournament_id=self.eff.id)
            award_tournament_rank_scores(self.eff)
            refresh_weekly_eff_best_scores(self.eff)
        record = TournamentUser.objects.get(user=self.user)
        self.assertEqual(record.weekly_eff_total, 0)
        self.assertEqual(record.score_total, 0)
        self.assertEqual(calculate_weekly_eff_best(self.user.id), (None, None, None))
        self.assertIsNone(record.weekly_eff_best)
        self.assertIsNone(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_eff_best'], self.user.id))

    def test_cache_roundtrip_rebuild_and_original_float_ranking(self):
        cached = self.tournament_cache.get_tournament(self.eff.id)
        self.assertEqual(cached.data.year, 2026)
        self.assertFalse(hasattr(cached.data, 'tournament_format'))
        other = self.create_user('eff_rank_user')
        one = TournamentUser.objects.get(user=self.user)
        one.weekly_eff_best = 700.0000000002
        one.save(update_fields=['weekly_eff_best'])
        two = TournamentUser.objects.create(user=other, weekly_eff_best=700.0000000001)
        self.tournament_cache.update_tournament_users([one, two])
        ranked, total = self.tournament_cache.get_tournament_user_ranking('weekly_eff_best')
        self.assertEqual(total, 2)
        self.assertEqual([row.user_id for row in ranked], [other.id, self.user.id])
        cache.delete(NORMAL_TOURNAMENT_CACHE_KEY, NORMAL_PARTICIPANT_CACHE_KEY)
        call_command('rebuild_tournament_cache', stdout=StringIO())
        self.assertEqual(self.tournament_cache.get_tournament(self.eff.id).subclass, Tournament_TextChoices.Subclass.WEEKLY_EFF)
        self.assertEqual(self.tournament_cache.get_participant_list(self.user.id)[0].id, self.participant.id)

    def test_atomic_participant_list_retries_without_losing_another_registration(self):
        weekly = self.create_weekly_tournament()
        other = WeeklyParticipant.objects.create(user=self.user, tournament=weekly, start_time=self.participant.start_time, end_time=self.participant.end_time)
        changed = False

        def modify(participants, pipe):
            nonlocal changed
            if not changed:
                changed = True
                self.tournament_cache.update_participant(other)
            return participants

        self.tournament_cache._modify_participant_list(self.user.id, modify)
        self.assertEqual({item.tournament for item in self.tournament_cache.get_participant_list(self.user.id)}, {self.eff.id, weekly.id})
        self.tournament_cache.remove_tournament(self.eff.id)
        self.tournament_cache.update_participant(self.participant)
        self.assertEqual([item.id for item in self.tournament_cache.get_participant_list(self.user.id)], [other.id])

    def test_delete_repairs_missing_user_best_and_maintenance_rebuilds_efficiency_fields(self):
        self.participant.score = 500.125
        self.participant.save(update_fields=['score'])
        self.award()
        refresh_weekly_eff_best_scores(self.eff)
        previous = WeeklyEffTournament.objects.create(
            year=2025, week=52, subclass=Tournament_TextChoices.Subclass.WEEKLY_EFF,
            state=Tournament_TextChoices.State.AWARDED, host=self.user, weight=50,
            start_time=self.eff.start_time - timedelta(days=7), end_time=self.eff.end_time - timedelta(days=7),
        )
        WeeklyEffParticipant.objects.create(user=self.user, tournament=previous, score=600.25)
        TournamentUser.objects.filter(user=self.user).delete()
        with self.captureOnCommitCallbacks(execute=True):
            self.participant.delete()
        user = TournamentUser.objects.get(user=self.user)
        self.assertEqual((user.weekly_eff_best, user.weekly_eff_best_year, user.weekly_eff_best_week), (600.25, 2025, 52))
        self.assertEqual((user.score_current, user.score_total, user.weekly_eff_total), (0, 0, 0))
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_eff_best'], self.user.pk), 600.25)
        TournamentUser.objects.filter(pk=user.pk).update(weekly_eff_best=None, weekly_eff_best_year=None, weekly_eff_best_week=None)
        call_command('refresh_tournament_user_stats', stdout=StringIO())
        user.refresh_from_db()
        self.assertEqual((user.weekly_eff_best, user.weekly_eff_best_year, user.weekly_eff_best_week), (600.25, 2025, 52))

    def test_disqualification_before_award_does_not_restore_scores(self):
        self.video()
        refresh_weekly_eff_scores(self.eff)
        refresh_tournament_ranks(self.eff)
        self.award()
        disqualify_participant(self.participant.id, tournament_id=self.eff.id)
        award_tournament_rank_scores(self.eff)
        refresh_weekly_eff_best_scores(self.eff)
        user = TournamentUser.objects.get(user=self.user)
        self.assertEqual((user.score_total, user.weekly_eff_total, user.weekly_eff_best), (0, 0, None))

    def test_creation_requires_admin_csrf_and_schedules_one_hour_after_end(self):
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.user)
        self.assertEqual(protected.post('/api/tournament/weekly-eff/new').status_code, 403)
        self.client.force_login(self.user)
        response = self.client.post('/api/tournament/weekly-eff/new')
        self.assertEqual(response.status_code, 200, response.content)
        created = WeeklyEffTournament.objects.get(pk=response.json()['data']['id'])
        task = DBTaskResult.objects.get(task_path='tournament.weekly_eff.tasks.task_weekly_eff_finish')
        self.assertEqual(task.run_after, created.end_time + TOURNAMENT_FINISH_DELAY)
        self.assertEqual(created.weight, 50)
        self.assertEqual(self.client.post('/api/tournament/weekly-eff/new').status_code, 409)
        self.assertEqual(Tournament.objects.get(pk=created.id).select_subclass().id, created.id)
