from unittest.mock import patch

from tournament.weekly.services import calculate_weekly_best
from tournament.weekly.utils import WEEKLY_BEST_FIELDS, WEEKLY_SCORE_CATEGORIES, WEEKLY_TOTAL_FIELDS
from .base import (
    _task_award_tournament_impl,
    _task_weekly_finish_impl,
    _task_weekly_refresh_best_impl,
    cache,
    call_command,
    MAX_TOURNAMENT_BEST,
    MS_TextChoices,
    refresh_weekly_scores,
    StringIO,
    timedelta,
    timezone,
    Tournament_TextChoices,
    TOURNAMENT_USER_CACHE_KEYS,
    TournamentTestCaseBase,
    TournamentUser,
    VideoModel,
    weekly_encode_best,
    WeeklyParticipant,
    WeeklyTournament,
)


class TestWeeklyModes(TournamentTestCaseBase):
    def test_invalid_format_is_rejected_before_querying_participants(self):
        tournament = self.create_weekly_tournament()
        tournament.tournament_format = '?'
        with self.assertNumQueries(0), self.assertRaises(ValueError):
            refresh_weekly_scores(tournament)

    def test_scores_filter_mode_nf_state_level_and_time_limits(self):
        candidates = []
        for level in ('i', 'e'):
            for mode, right_ce, timems in [('00', 1, 10000), ('00', 0, 20000), ('06', 1, 30000), ('06', 0, 40000), ('00', None, 50000)]:
                candidates.append(self.create_video(tournament_identifier=[], level=level, mode=mode, right_ce=right_ce, timems=timems))
        rejected = [self.create_video(tournament_identifier=[], level='i', mode='05', timems=1, right_ce=0)]
        for mode in ('00', '06'):
            for level, limit in [('i', 60000), ('e', 240000)]:
                rejected.append(self.create_video(tournament_identifier=[], level=level, mode=mode, timems=limit, right_ce=0))
                frozen = self.create_video(tournament_identifier=[], level=level, mode=mode, timems=1, right_ce=0)
                VideoModel.objects.filter(pk=frozen.pk).update(state=MS_TextChoices.State.FROZEN)
                rejected.append(frozen)
            rejected.append(self.create_video(tournament_identifier=[], level='b', mode=mode, timems=1, right_ce=0))

        for tournament_format, indices in [('c', [0, 1, 4]), ('n', [1]), ('q', [2, 3]), ('f', [3])]:
            with self.subTest(tournament_format=tournament_format):
                tournament = self.create_weekly_tournament(tournament_format=tournament_format)
                participant = WeeklyParticipant.objects.create(user=self.user, tournament=tournament)
                tournament.videos.add(*candidates, *rejected)
                refresh_weekly_scores(tournament)
                participant.refresh_from_db()
                expected_i = [[candidates[index].id, candidates[index].timems] for index in indices]
                expected_e = [[candidates[index + 5].id, candidates[index + 5].timems] for index in indices[:2]]
                expected_i += [[0, 60000]] * (5 - len(expected_i))
                expected_e += [[0, 240000]] * (2 - len(expected_e))
                self.assertEqual(participant.classic_it, expected_i)
                self.assertEqual(participant.classic_et, expected_e)
                self.assertEqual(participant.classic_score, sum(value for _, value in expected_i + expected_e))
                self.assertEqual(tournament.order_by, 'classic_score')
                VideoModel.objects.filter(pk__in=[video_id for video_id, _ in expected_i + expected_e]).update(state=MS_TextChoices.State.FROZEN)
                refresh_weekly_scores(tournament)
                participant.refresh_from_db()
                self.assertGreaterEqual(participant.classic_score, sum(value for _, value in expected_i + expected_e))
                VideoModel.objects.filter(pk__in=[video.pk for video in candidates]).update(state=MS_TextChoices.State.OFFICIAL)

    def test_finish_recompute_delete_and_rebuild_keep_format_totals_and_bests_separate(self):
        records = []
        end_time = timezone.now() - timedelta(hours=2)
        for tournament_format, category in WEEKLY_SCORE_CATEGORIES.items():
            tournament = self.create_weekly_tournament(tournament_format=tournament_format, end_time=end_time, start_time=end_time - timedelta(days=7))
            participant = WeeklyParticipant.objects.create(user=self.user, tournament=tournament)
            mode = '06' if tournament_format in ('q', 'f') else '00'
            video = self.create_video(tournament_identifier=[], level='i', mode=mode, right_ce=0, timems=20000)
            tournament.videos.add(video)
            with self.captureOnCommitCallbacks(execute=True):
                _task_weekly_finish_impl(tournament.id)
                _task_award_tournament_impl(tournament.id)
                _task_award_tournament_impl(tournament.id)
                _task_weekly_refresh_best_impl(tournament.id)
                call_command('refresh_tournament_scores', tournament.id, stdout=StringIO())
            record = TournamentUser.objects.get(user=self.user)
            self.assertEqual(getattr(record, f'{category}_total'), 50)
            best = weekly_encode_best(740000, tournament.year, tournament.week)
            self.assertEqual(getattr(record, f'{category}_best'), best)
            self.assertEqual(calculate_weekly_best(self.user.id, tournament_format), best)
            self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS[f'{category}_total'], self.user.id), 50)
            self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS[f'{category}_best'], self.user.id), best)
            records.append(participant)

        self.assertEqual(record.weekly_total, 200)
        self.assertEqual(record.score_total, 200)
        records[1].refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            records[1].delete()
        record.refresh_from_db()
        self.assertEqual(record.weekly_total, 150)
        self.assertEqual(record.score_current, 150)
        self.assertEqual(record.weekly_nf_total, 0)
        self.assertEqual(record.weekly_nf_best, MAX_TOURNAMENT_BEST)
        self.assertEqual(record.weekly_classic_total, 50)
        self.assertIsNone(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_nf_total'], self.user.id))
        self.assertIsNone(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_nf_best'], self.user.id))

        TournamentUser.objects.filter(user=self.user).update(**dict.fromkeys(WEEKLY_TOTAL_FIELDS + WEEKLY_BEST_FIELDS, 999))
        call_command('refresh_tournament_user_stats', stdout=StringIO())
        record.refresh_from_db()
        self.assertEqual(record.weekly_total, sum(getattr(record, field) for field in WEEKLY_TOTAL_FIELDS))
        for tournament_format, category in WEEKLY_SCORE_CATEGORIES.items():
            expected_total = 0 if tournament_format == 'n' else 50
            self.assertEqual(getattr(record, f'{category}_total'), expected_total)
            self.assertEqual(getattr(record, f'{category}_best'), calculate_weekly_best(self.user.id, tournament_format))
        self.tournament_cache.rebuild_tournament_user_cache()
        for field in ('weekly_qwc_total', 'weekly_qwc_best', 'weekly_qwc_nf_best'):
            response = self.client.get('/api/tournament/user-ranking', {'sort_by': field, 'start': 0, 'end': 20})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['total'], 1)
            self.assertEqual(response.json()['data'][0][field], getattr(record, field))

    def test_best_regresses_only_within_deleted_participants_format(self):
        first = self.create_weekly_tournament(tournament_format='n', state=Tournament_TextChoices.State.AWARDED)
        second = self.create_weekly_tournament(tournament_format='n', state=Tournament_TextChoices.State.AWARDED)
        classic = self.create_weekly_tournament(state=Tournament_TextChoices.State.AWARDED)
        first_participant = WeeklyParticipant.objects.create(user=self.user, tournament=first, classic_score=400000)
        WeeklyParticipant.objects.create(user=self.user, tournament=second, classic_score=500000)
        WeeklyParticipant.objects.create(user=self.user, tournament=classic, classic_score=100000)
        first_participant.delete()
        record = TournamentUser.objects.get(user=self.user)
        self.assertEqual(record.weekly_nf_best, weekly_encode_best(500000, second.year, second.week))
        self.assertEqual(record.weekly_classic_best, weekly_encode_best(100000, classic.year, classic.week))

    def test_tournament_cascade_preserves_format_for_best_and_point_refund(self):
        tournament = self.create_weekly_tournament(tournament_format='f', state=Tournament_TextChoices.State.AWARDED)
        WeeklyParticipant.objects.create(user=self.user, tournament=tournament, classic_score=400000, rank=1, rank_score=50)
        record = TournamentUser.objects.get(user=self.user)
        record.add_score(50, tournament.end_time, category='weekly_qwc_nf')
        record.save(update_fields=['score_current', 'last_updated', 'score_total', 'weekly_total', 'weekly_qwc_nf_total'])
        with self.captureOnCommitCallbacks(execute=True):
            tournament.delete()
        record.refresh_from_db()
        self.assertEqual((record.weekly_qwc_nf_total, record.weekly_total, record.score_total, record.score_current), (0, 0, 0, 0))
        self.assertEqual(record.weekly_qwc_nf_best, MAX_TOURNAMENT_BEST)
        self.assertIsNone(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['weekly_qwc_nf_best'], self.user.id))

    def test_staff_selects_format_but_cannot_create_two_formats_in_one_week(self):
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)
        now = timezone.now()
        for index, tournament_format in enumerate(WEEKLY_SCORE_CATEGORIES):
            with self.subTest(tournament_format=tournament_format), patch('tournament.weekly.api.get_next_week_window', return_value=(2026, 10 + index, now, now + timedelta(days=7))):
                response = self.client.post('/api/tournament/weekly/new', {'tournament_format': tournament_format})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['data']['tournament_format'], tournament_format)
                duplicate = self.client.post('/api/tournament/weekly/new', {'tournament_format': 'f' if tournament_format != 'f' else 'c'})
                self.assertEqual(duplicate.status_code, 409)
                self.assertEqual(WeeklyTournament.objects.filter(year=2026, week=10 + index).count(), 1)
        count = WeeklyTournament.objects.count()
        invalid = self.client.post('/api/tournament/weekly/new', {'tournament_format': 'invalid'})
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(WeeklyTournament.objects.count(), count)
