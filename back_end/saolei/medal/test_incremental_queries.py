from unittest.mock import patch

from django.core.cache import caches
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from tournament.models import Tournament, TournamentParticipant
from userprofile.models import UserProfile
from videomanager.models import VideoModel
from .cache import delete_player_states, read_player_state, write_player_state
from .models import MedalGrant, MedalScan, PlayerMedalSummary, PlayerProgress
from .services import _flush_player_states, player_states, refresh_player_medals, replace_pins, set_player_override
from .test_state_cache import MedalStateFixture
from .tests import MedalTestCase
from .utils import NOVICE_MODES, SHAREHOLDER_CODE, STATE_CACHE_SECONDS


def selects(queries):
    return [query['sql'] for query in queries if query['sql'].lstrip().upper().startswith('SELECT ')]


class MedalIncrementalQueryTests(MedalStateFixture, MedalTestCase):
    def refresh(self, *videos):
        with self.captureOnCommitCallbacks(execute=True):
            refresh_player_medals(self.user.id, video_ids=[video.id for video in videos])

    def prepare_unchanged(self):
        self.make_video(timems=19000, upload_time=self.earlier)
        self.scan()
        return self.make_video(timems=19500, upload_time=self.later)

    def test_ordinary_refresh_uses_six_selects_and_no_writes_or_cache_access(self):
        video = self.prepare_unchanged()
        # 无缓存、空缓存、旧格式错误快照均不改变计算依据和查询预算。
        for payload in (None, {'grants': []}, {'grants': [{'code': SHAREHOLDER_CODE, 'value': 1, 'locked': True}]}):
            with self.subTest(payload=payload):
                if payload is None:
                    delete_player_states([self.user.id])
                else:
                    write_player_state(self.user.id, payload)
                with patch('medal.cache._cache', side_effect=AssertionError('calculation accessed cache')), CaptureQueriesContext(connection) as queries:
                    self.refresh(video)
                sql = selects(queries)
                self.assertEqual(len(sql), 6, sql)
                self.assertFalse(any(query['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for query in queries))
                self.assertEqual(sum('FROM `medal_medaldefinition`' in query for query in sql), 1)
                self.assertEqual(sum('FROM `videomanager_videomodel`' in query for query in sql), 1)
                touched = next(query for query in sql if 'FROM `videomanager_videomodel`' in query)
                self.assertIn(str(video.id), touched)
                self.assertNotIn('MIN(', touched.upper())
                self.assertNotIn('MAX(', touched.upper())

    def test_multiple_touched_videos_still_use_six_selects(self):
        first = self.prepare_unchanged()
        second = self.make_video(timems=19900, upload_time=self.later)
        with CaptureQueriesContext(connection) as queries:
            self.refresh(first, second)
        sql = selects(queries)
        self.assertEqual(len(sql), 6, sql)
        touched = next(query for query in sql if 'FROM `videomanager_videomodel`' in query)
        self.assertIn(str(first.id), touched)
        self.assertIn(str(second.id), touched)

    def test_backfill_uses_scoped_history_and_eleven_selects_including_publication(self):
        self.prepare_unchanged()
        self.wear(self.user, ['ability.time.b'])
        older = self.make_video(timems=19000, upload_time=self.earlier - (self.later - self.earlier))
        delete_player_states([self.user.id])
        with CaptureQueriesContext(connection) as queries:
            self.refresh(older)
        sql = selects(queries)
        self.assertEqual(len(sql), 11, sql)
        history = [query for query in sql if 'FROM `videomanager_videomodel`' in query][1:]
        self.assertTrue(history)
        for query in history:
            self.assertIn(f'`player_id` = {self.user.id}', query)
            self.assertIn('LIMIT 1', query)
            self.assertNotIn('MIN(', query.upper())
            self.assertNotIn('MAX(', query.upper())
        grant = self.active()
        self.assertEqual(grant.video_id, older.id)
        self.assertEqual(grant.granted_at, older.upload_time)
        self.assertEqual(grant.stage_log[0]['evidence_id'], older.id)

    def test_incomplete_mode_set_updates_database_without_publishing_display(self):
        self.prepare_unchanged()
        second = self.make_video(mode='01', upload_time=self.later)
        with patch('medal.services.write_player_states') as publish, patch('medal.services._novice_modes_found') as history, CaptureQueriesContext(connection) as queries:
            self.refresh(second)
        publish.assert_not_called()
        history.assert_not_called()
        self.assertEqual(len(selects(queries)), 6)
        self.assertEqual(PlayerProgress.objects.get(user=self.user, code=NOVICE_MODES).extra, {'modes': ['00', '01']})

    def test_display_misses_are_one_batched_select_then_zero_on_hit(self):
        self.prepare_unchanged()
        other = UserProfile.objects.create_user(username='display_other', email='display-other@example.com')
        with self.captureOnCommitCallbacks(execute=True):
            refresh_player_medals(other.id, full=True)
        expected = player_states([self.user.id, other.id])
        delete_player_states([self.user.id, other.id])
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(player_states([self.user.id, other.id]), expected)
        self.assertEqual(len(selects(queries)), 1)
        self.assertFalse(any('FROM `videomanager_videomodel`' in query for query in selects(queries)))
        with self.assertNumQueries(0):
            self.assertEqual(player_states([self.user.id, other.id]), expected)

    def test_missing_summaries_use_batched_grants_without_video_history(self):
        self.prepare_unchanged()
        other = UserProfile.objects.create_user(username='summary_other', email='summary-other@example.com')
        MedalScan.objects.create(user=other, scanned_at=timezone.now())
        expected = player_states([self.user.id, other.id])
        PlayerMedalSummary.objects.filter(user_id__in=[self.user.id, other.id]).delete()
        delete_player_states([self.user.id, other.id])
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(player_states([self.user.id, other.id]), expected)
        self.assertEqual(len(selects(queries)), 2)
        self.assertFalse(any('videomanager_videomodel' in query for query in selects(queries)))

    def test_unscanned_and_missing_users_do_not_scan_or_create_cache_entries(self):
        with patch('medal.services._evaluate_locked') as scan, CaptureQueriesContext(connection) as queries:
            self.assertEqual(player_states([self.user.id, 0]), [{'user_id': self.user.id, 'grants': []}, {'user_id': 0, 'grants': []}])
        scan.assert_not_called()
        self.assertEqual(len(selects(queries)), 1)
        self.assertIsNone(read_player_state(self.user.id))

    def test_redis_outage_does_not_block_upgrade_or_database_display_fallback(self):
        self.prepare_unchanged()
        self.wear(self.user, ['ability.time.b'])
        faster = self.make_video(timems=14000, upload_time=self.later)
        backend = caches['default']
        with self.assertLogs('medal.cache', level='WARNING'), patch.object(backend, 'get_many', side_effect=ConnectionError('offline')), patch.object(backend, 'set_many', side_effect=ConnectionError('offline')):
            self.refresh(faster)
            result = player_states([self.user.id])
        grant = self.active()
        self.assertEqual(grant.stage, 15000)
        self.assertEqual(grant.video_id, faster.id)
        self.assertEqual(next(row for row in result[0]['grants'] if row['code'] == 'ability.time.b')['stage'], 15000)
        self.assertIsNone(read_player_state(self.user.id))
        player_states([self.user.id])
        self.assertEqual(next(row for row in read_player_state(self.user.id)['grants'] if row['code'] == 'ability.time.b')['stage'], 15000)

    def test_failed_publication_deletes_old_value_and_uses_finite_ttl(self):
        self.prepare_unchanged()
        backend = caches['default']
        with patch.object(backend, 'set_many', return_value=['failed']) as publish:
            _flush_player_states([self.user.id])
        self.assertEqual(publish.call_args.kwargs['timeout'], STATE_CACHE_SECONDS)
        self.assertIsNone(read_player_state(self.user.id))

    def test_older_commit_callback_publishes_latest_committed_summary(self):
        self.prepare_unchanged()
        self.wear(self.user, ['ability.time.b'])
        faster = self.make_video(timems=14000, upload_time=self.later)
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            refresh_player_medals(self.user.id, video_ids=[faster.id])
        newest = self.make_video(timems=9000, upload_time=self.later)
        self.refresh(newest)
        expected = read_player_state(self.user.id)
        self.assertTrue(callbacks)
        for callback in reversed(callbacks):
            callback()
        self.assertEqual(read_player_state(self.user.id), expected)
        self.assertEqual(next(row for row in expected['grants'] if row['code'] == 'ability.time.b')['stage'], 10000)

    def test_rollback_does_not_publish_or_change_progress(self):
        self.prepare_unchanged()
        expected = read_player_state(self.user.id)
        faster = self.make_video(timems=14000, upload_time=self.later)
        with self.captureOnCommitCallbacks(execute=True), self.assertRaisesRegex(RuntimeError, 'rollback'):
            with transaction.atomic():
                refresh_player_medals(self.user.id, video_ids=[faster.id])
                raise RuntimeError('rollback')
        self.assertEqual(self.active().stage, 20000)
        self.assertEqual(read_player_state(self.user.id), expected)

    def test_pin_change_publishes_only_worn_grants(self):
        self.prepare_unchanged()
        grant = self.active()
        with self.captureOnCommitCallbacks(execute=True):
            replace_pins(self.user, [grant.id])
        shown = [row['code'] for row in read_player_state(self.user.id)['grants']]
        self.assertEqual(shown, [grant.definition_code])

    def test_scoped_tournament_and_manual_grants_survive_incremental_and_cold_display(self):
        video = self.prepare_unchanged()
        tournament = Tournament.objects.create()
        participant = TournamentParticipant.objects.create(tournament=tournament, user=self.user)
        # 赛事记录由赛事入口维护，普通录像增量不能误删或更改它。
        grant = MedalGrant.objects.create(user=self.user, definition_code='event.place', stage=1, scope_key='event:1', participant=participant, evidence={'rank': 2}, granted_at=self.earlier)
        self.user.is_staff = True
        with self.captureOnCommitCallbacks(execute=True):
            set_player_override(self.user, self.user.id, 'ability.time.b', '', 'grant', 'manual', stage=10000)
        self.refresh(video)
        self.wear(self.user, ['ability.time.b', 'event.place'])
        delete_player_states([self.user.id])
        rows = player_states([self.user.id])[0]['grants']
        self.assertEqual([(row['scope'], row['code']) for row in rows], sorted((row['scope'], row['code']) for row in rows))
        scoped = next(row for row in rows if row['code'] == grant.definition_code)
        self.assertEqual((scoped['scope'], scoped['tournament'], scoped['rank']), ('event:1', tournament.id, 2))
        self.assertEqual(self.active().stage, 10000)
        grant.refresh_from_db()
        self.assertIsNone(grant.revoked_at)

    def test_deleted_current_evidence_remains_incremental_without_cache(self):
        first = self.make_video(timems=19000, upload_time=self.earlier)
        self.scan()
        replacement = self.make_video(timems=19500, upload_time=self.later)
        with self.captureOnCommitCallbacks(execute=True):
            VideoModel.objects.filter(pk=first.id).delete()
        self.assertIsNone(read_player_state(self.user.id))
        with patch('medal.services._evaluate_locked', side_effect=AssertionError('unexpected full scan')):
            with self.captureOnCommitCallbacks(execute=True):
                refresh_player_medals(self.user.id, video_ids=[first.id], degrade_levels=['b'], invalidate_once=True)
        self.assertEqual(self.active().video_id, replacement.id)
        self.assertEqual(self.active().granted_at, replacement.upload_time)
