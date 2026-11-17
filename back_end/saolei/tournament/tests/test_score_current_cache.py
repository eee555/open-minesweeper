from datetime import datetime, timezone as datetime_timezone
from unittest.mock import patch

from django.core.management import CommandError
from django.test import SimpleTestCase

from tournament.cache import TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY, TournamentCache
from tournament.utils import tournament_score_decay_factor, tournament_score_reference_time
from .base import award_tournament_rank_scores, cache, call_command, StringIO, timedelta, TOURNAMENT_USER_CACHE_KEYS, TournamentTestCaseBase, TournamentUser, WeeklyParticipant


class ScoreReferenceTimeTests(SimpleTestCase):
    def test_decay_factor_supports_both_time_directions(self):
        start = datetime(2026, 1, 1, tzinfo=datetime_timezone.utc)
        end = start + timedelta(days=730)
        self.assertEqual(tournament_score_decay_factor(start, end), 0.5)
        self.assertEqual(tournament_score_decay_factor(end, start), 2)
        self.assertEqual(tournament_score_decay_factor(start, start), 1)

    def test_reference_year_uses_utc_instead_of_local_year(self):
        local_time = datetime(2027, 1, 1, 7, tzinfo=datetime_timezone(timedelta(hours=8)))
        with patch('tournament.utils.timezone.now', return_value=local_time):
            self.assertEqual(tournament_score_reference_time(), datetime(2026, 1, 1, tzinfo=datetime_timezone.utc))


class ScoreCurrentCacheTests(TournamentTestCaseBase):
    def setUp(self):
        super().setUp()
        self.anchor = datetime(2026, 1, 1, tzinfo=datetime_timezone.utc)
        self.now = self.anchor + timedelta(days=180)
        self.old_time = self.now - timedelta(days=730)
        self.key = TOURNAMENT_USER_CACHE_KEYS['score_current']
        self.scale = 2 ** (180 / 730)
        reference_patch = patch('tournament.cache.tournament_score_reference_time', return_value=self.anchor)
        self.reference_clock = reference_patch.start()
        self.addCleanup(reference_patch.stop)

    def reference_time(self):
        return datetime.fromisoformat(cache.get(TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY).decode())

    def test_batch_uses_annual_anchor_and_api_pages_by_normalized_scores(self):
        other = self.create_user('current_score_new')
        older = TournamentUser.objects.create(user=self.user, score_current=100, last_updated=self.old_time, score_total=100)
        newer = TournamentUser.objects.create(user=other, score_current=80, last_updated=self.now, score_total=80)
        self.tournament_cache.update_tournament_users([older, newer])

        self.assertEqual(self.reference_time(), self.anchor)
        self.assertAlmostEqual(cache.zscore(self.key, self.user.id), 50 * self.scale)
        self.assertAlmostEqual(cache.zscore(self.key, other.id), 80 * self.scale)
        for start, expected in ((0, newer), (1, older)):
            response = self.client.get('/api/tournament/user-ranking', {'sort_by': 'score_current', 'start': start, 'end': start + 1})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['total'], 2)
            self.assertEqual(response.json()['data'][0]['user_id'], expected.user_id)
            self.assertEqual(response.json()['data'][0]['score_current'], expected.score_current)
            self.assertEqual(response.json()['data'][0]['score_total'], expected.score_total)
        older.refresh_from_db()
        self.assertEqual((older.score_current, older.last_updated), (100, self.old_time))

    def test_incremental_updates_do_not_advance_anchor_or_rescale_other_members(self):
        other = self.create_user('current_score_update')
        older = TournamentUser(user_id=self.user.id, score_current=100, last_updated=self.old_time, score_total=100)
        newer = TournamentUser(user_id=other.id, score_current=80, last_updated=self.now, score_total=80)
        self.tournament_cache.update_tournament_user(older)
        pipe = cache.pipeline()
        with patch.object(cache, 'pipeline', return_value=pipe), patch.object(pipe, 'zunionstore', wraps=pipe.zunionstore) as rescale:
            self.tournament_cache.update_tournament_user(newer)
            self.tournament_cache.update_tournament_user(newer)
        rescale.assert_not_called()
        self.assertEqual(self.reference_time(), self.anchor)
        self.assertAlmostEqual(cache.zscore(self.key, self.user.id), 50 * self.scale)
        self.assertAlmostEqual(cache.zscore(self.key, other.id), 80 * self.scale)
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['score_total'], self.user.id), 100)

    def test_default_scores_and_unrelated_fields_leave_anchor_unchanged(self):
        record = TournamentUser(user_id=self.user.id, score_current=100, last_updated=self.old_time)
        self.tournament_cache.update_tournament_user(record)
        record.last_updated = self.now
        record.score_total = 100
        self.tournament_cache.update_tournament_user(record, fields=['score_total'])
        self.assertEqual(self.reference_time(), self.anchor)
        self.assertAlmostEqual(cache.zscore(self.key, self.user.id), 50 * self.scale)

        record.score_current = 0
        self.tournament_cache.update_tournament_user(record, fields=['score_current'])
        self.assertEqual(self.reference_time(), self.anchor)
        self.assertIsNone(cache.zscore(self.key, self.user.id))
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['score_total'], self.user.id), 100)

    def test_awards_and_historical_recalculation_keep_annual_anchor(self):
        other = self.create_user('current_score_award')
        older = TournamentUser.objects.create(user=self.user, score_current=120, last_updated=self.old_time, score_total=120)
        self.tournament_cache.update_tournament_user(older)
        tournament = self.create_weekly_tournament(end_time=self.now)
        WeeklyParticipant.objects.create(user=other, tournament=tournament, rank=1)
        with self.captureOnCommitCallbacks(execute=True):
            award_tournament_rank_scores(tournament)
        self.assertEqual(self.reference_time(), self.anchor)
        self.assertAlmostEqual(cache.zscore(self.key, self.user.id), 60 * self.scale)
        self.assertAlmostEqual(cache.zscore(self.key, other.id), 50 * self.scale)

        next_tournament = self.create_weekly_tournament(week=2, end_time=self.now + timedelta(days=730))
        WeeklyParticipant.objects.create(user=other, tournament=next_tournament, rank=1)
        with self.captureOnCommitCallbacks(execute=True):
            award_tournament_rank_scores(next_tournament)
            award_tournament_rank_scores(tournament)
        self.assertEqual(self.reference_time(), self.anchor)
        self.assertAlmostEqual(cache.zscore(self.key, self.user.id), 60 * self.scale)
        self.assertAlmostEqual(cache.zscore(self.key, other.id), 150 * self.scale)
        older.refresh_from_db()
        self.assertEqual((older.score_current, older.last_updated), (120, self.old_time))

    def test_annual_refresh_catches_up_missed_years_once_and_keeps_other_fields(self):
        record = TournamentUser.objects.create(user=self.user, score_current=100, last_updated=self.old_time, score_total=100)
        self.tournament_cache.update_tournament_user(record)
        self.reference_clock.return_value = datetime(2028, 1, 1, tzinfo=datetime_timezone.utc)

        # 定时任务延迟时，普通写入仍沿用旧锚点，不能自行切换年份。
        self.tournament_cache.update_tournament_user(record)
        self.assertEqual(self.reference_time(), self.anchor)
        self.assertTrue(self.tournament_cache.refresh_tournament_score_reference())
        self.assertFalse(self.tournament_cache.refresh_tournament_score_reference())
        self.assertEqual(self.reference_time(), self.reference_clock.return_value)
        self.assertAlmostEqual(cache.zscore(self.key, self.user.id), 25 * self.scale)
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['score_total'], self.user.id), 100)
        record.refresh_from_db()
        self.assertEqual((record.score_current, record.last_updated), (100, self.old_time))

    def test_concurrent_annual_rotation_retries_incremental_update_with_new_anchor(self):
        record = TournamentUser(user_id=self.user.id, score_current=100, last_updated=self.old_time)
        self.tournament_cache.update_tournament_user(record)
        update = self.tournament_cache._update_tournament_users_in_pipeline
        interrupted = False

        def rotate_during_update(pipe, records, fields, **kwargs):
            nonlocal interrupted
            update(pipe, records, fields, **kwargs)
            if not interrupted:
                interrupted = True
                self.reference_clock.return_value = datetime(2028, 1, 1, tzinfo=datetime_timezone.utc)
                TournamentCache().refresh_tournament_score_reference()

        with patch.object(self.tournament_cache, '_update_tournament_users_in_pipeline', side_effect=rotate_during_update) as mocked:
            self.tournament_cache.update_tournament_users(iter([record]), fields=['score_current'])
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(self.reference_time(), self.reference_clock.return_value)
        self.assertAlmostEqual(cache.zscore(self.key, self.user.id), 25 * self.scale)

    def test_nonempty_cache_without_reference_requires_rebuild(self):
        cache.zadd(self.key, {self.user.id: 100})
        record = TournamentUser(user_id=self.user.id, score_current=80, last_updated=self.now)
        with self.assertRaisesMessage(RuntimeError, 'run rebuild_tournament_current_score_cache'):
            self.tournament_cache.update_tournament_user(record)
        with self.assertRaises(RuntimeError):
            self.tournament_cache.refresh_tournament_score_reference()
        self.assertEqual(cache.zscore(self.key, self.user.id), 100)
        self.assertIsNone(cache.get(TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY))

    def test_current_score_command_rebuilds_only_current_score_and_reference(self):
        record = TournamentUser.objects.create(user=self.user, score_current=100, last_updated=self.old_time, score_total=100)
        default = self.create_user('current_score_command_default')
        TournamentUser.objects.create(user=default)
        cache.zadd(self.key, {'999': 500})
        cache.zadd(TOURNAMENT_USER_CACHE_KEYS['score_total'], {'999': 123})
        output = StringIO()
        for _ in range(2):
            call_command('rebuild_tournament_current_score_cache', batch_size=1, stdout=output)
            self.assertEqual(self.reference_time(), self.anchor)
            self.assertEqual(cache.zcard(self.key), 1)
            self.assertAlmostEqual(cache.zscore(self.key, self.user.id), 50 * self.scale)
            self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['score_total'], '999'), 123)
        record.refresh_from_db()
        self.assertEqual((record.score_current, record.last_updated, record.score_total), (100, self.old_time, 100))
        self.assertIn('rebuilt 2 tournament current score cache rows', output.getvalue())
        for batch_size in (0, -1):
            with self.subTest(batch_size=batch_size), self.assertRaises(CommandError):
                call_command('rebuild_tournament_current_score_cache', batch_size=batch_size, stdout=StringIO())

    def test_current_score_rebuild_is_atomic_and_retries_after_concurrent_write(self):
        record = TournamentUser.objects.create(user=self.user, score_current=100, last_updated=self.old_time)
        self.tournament_cache.update_tournament_user(record)
        update = self.tournament_cache._update_tournament_users_in_pipeline
        interrupted = False

        def concurrent_update(pipe, records, fields, **kwargs):
            nonlocal interrupted
            update(pipe, records, fields, **kwargs)
            self.assertAlmostEqual(cache.zscore(self.key, self.user.id), (60 if interrupted else 50) * self.scale)
            if not interrupted:
                interrupted = True
                record.score_current = 120
                record.save(update_fields=['score_current'])
                TournamentCache().update_tournament_user(record, fields=['score_current'])

        with patch.object(self.tournament_cache, '_update_tournament_users_in_pipeline', side_effect=concurrent_update):
            self.assertEqual(self.tournament_cache.rebuild_tournament_current_score_cache(batch_size=1), 1)
        self.assertAlmostEqual(cache.zscore(self.key, self.user.id), 60 * self.scale)

    def test_empty_database_rebuild_clears_stale_scores_and_initializes_anchor(self):
        cache.zadd(self.key, {'999': 500})
        call_command('rebuild_tournament_current_score_cache', stdout=StringIO())
        self.assertEqual(cache.zcard(self.key), 0)
        self.assertEqual(self.reference_time(), self.anchor)

    def test_updates_each_zset_with_one_bulk_add_and_one_bulk_remove(self):
        records = [
            TournamentUser(user_id=101, score_current=100, last_updated=self.old_time, score_total=100, gsc_total=60),
            TournamentUser(user_id=102, score_current=80, last_updated=self.now, score_total=80, gsc_total=40),
            TournamentUser(user_id=103),
            TournamentUser(user_id=104),
        ]
        for fields, expected_values in (
            (['score_current', 'score_total'], [{101: 50 * self.scale, 102: 80 * self.scale}, {101: 100, 102: 80}]),
            (['score_total', 'gsc_total'], [{101: 100, 102: 80}, {101: 60, 102: 40}]),
        ):
            with self.subTest(fields=fields):
                self.tournament_cache.clear_tournament_user_cache()
                self.tournament_cache.update_tournament_users([
                    TournamentUser(user_id=user_id, score_current=1, last_updated=self.now, score_total=1, gsc_total=1)
                    for user_id in (103, 104)
                ], fields=fields)
                pipe = cache.pipeline()
                with patch.object(cache, 'pipeline', return_value=pipe):
                    with patch.object(pipe, 'zadd', wraps=pipe.zadd) as adds, patch.object(pipe, 'zrem', wraps=pipe.zrem) as removals:
                        self.tournament_cache.update_tournament_users(iter(records), fields=fields)
                self.assertEqual(adds.call_count, len(fields))
                self.assertEqual(removals.call_count, len(fields))
                for field, expected, addition, removal in zip(fields, expected_values, adds.call_args_list, removals.call_args_list):
                    key = TOURNAMENT_USER_CACHE_KEYS[field]
                    self.assertEqual(addition.args[0], key)
                    self.assertEqual(set(addition.args[1]), set(expected))
                    self.assertEqual(removal.args[0], key)
                    self.assertEqual(set(removal.args[1:]), {103, 104})
                    self.assertEqual(cache.zcard(key), 2)
                    for user_id, score in expected.items():
                        self.assertAlmostEqual(addition.args[1][user_id], score)
                        self.assertAlmostEqual(cache.zscore(key, user_id), score)

    def test_empty_batch_does_not_queue_redis_commands(self):
        with patch.object(cache, 'pipeline') as pipeline:
            self.tournament_cache.update_tournament_users([], fields=['score_current'])
            self.tournament_cache.update_tournament_users(iter([]), fields=['score_total'])
        pipeline.assert_not_called()
