from datetime import timedelta
import re
from unittest.mock import patch

from django.core.cache import caches
from django.core.management import call_command
from django.db import connection
from django.db.models.query import QuerySet
from django.tasks import TaskResultStatus
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from config.text_choices import MS_TextChoices
from userprofile.models import UserProfile
from videomanager.models import ExpandVideoModel, VideoModel
from .cache import read_player_state, write_player_state
from .models import MedalGrant, MedalScan, PlayerProgress
from .services import _aggregate_level, _flush_player_states, player_summary, refresh_player_medals, set_player_override
from .tasks import enqueue_player_backfill, enqueue_player_refresh, player_refresh_pending, task_backfill_player_medals, task_refresh_player_medals
from .tests import MedalTestCase
from .utils import NOVICE_MODES, open_modes, REFRESH_COALESCE_DELAY


def _row(payload, code):
    return next(item for item in payload['grants'] if item['code'] == code)


class MedalStateFixture:
    def setUp(self):
        caches['default'].clear()
        self.user = UserProfile.objects.create_user(username='medal_state', email='medal-state@example.com', password='password')
        self.ids = iter(range(3_000_000, 4_000_000))
        self.earlier = timezone.now() - timedelta(days=3)
        self.later = timezone.now() - timedelta(days=1)

    def make_video(self, *, level='b', mode='00', timems=10000, upload_time=None, bv=10, right_ce=0):
        video_id = next(self.ids)
        expand = ExpandVideoModel.objects.create(identifier=f'state-{video_id}')
        VideoModel.objects.bulk_create([
            VideoModel(
                id=video_id, player=self.user, video=expand, file=f'videos/{video_id}.evf', software='e',
                level=level, mode=mode, state=MS_TextChoices.State.OFFICIAL, timems=timems, bv=bv,
                left=max(bv, 1), right=right_ce, double=0, left_ce=bv, right_ce=right_ce, double_ce=0,
            ),
        ])
        VideoModel.objects.filter(pk=video_id).update(upload_time=upload_time or timezone.now())
        return VideoModel.objects.get(pk=video_id)

    def scan(self):
        with self.captureOnCommitCallbacks(execute=True):
            refresh_player_medals(self.user.id, full=True)

    def active(self, code='ability.time.b'):
        return MedalGrant.objects.filter(user=self.user, definition_code=code, revoked_at__isnull=True).first()


class MedalStateCacheTests(MedalStateFixture, MedalTestCase):
    def test_first_scan_and_missing_display_cache_keep_below_threshold_pb_ungranted(self):
        self.assertIsNone(read_player_state(self.user.id))
        with self.captureOnCommitCallbacks(execute=True):
            refresh_player_medals(self.user.id, video_ids=[1])
        self.assertTrue(MedalScan.objects.filter(user=self.user).exists())
        self.assertEqual(read_player_state(self.user.id), {'grants': []})

        video = self.make_video(timems=25000, upload_time=self.earlier)
        caches['default'].clear()
        self.assertIsNone(read_player_state(self.user.id))
        with self.captureOnCommitCallbacks(execute=True):
            refresh_player_medals(self.user.id, video_ids=[video.id])
        stored = read_player_state(self.user.id) or {'grants': []}
        self.assertNotIn('ability.time.b', [row['code'] for row in stored['grants']])
        self.assertIsNone(self.active())
        self.assertNotIn('shareholder.origin', [row['code'] for row in stored['grants']])
        shareholder = PlayerProgress.objects.get(user=self.user, code='shareholder.origin')
        self.assertEqual(shareholder.current_stage, 0)
        self.assertEqual(shareholder.current_value, video.id)

    def test_unreachable_video_does_not_aggregate(self):
        self.make_video(timems=19000, upload_time=self.earlier)
        self.scan()
        self.wear(self.user, ['ability.time.b'])
        grant = self.active()
        slow = self.make_video(timems=30000, upload_time=self.later)
        with patch('medal.services._evaluate_locked') as full_scan, patch('medal.services._aggregate_level') as aggregate, patch('medal.services.evaluate_min_video_id') as shareholder:
            with self.captureOnCommitCallbacks(execute=True):
                refresh_player_medals(self.user.id, video_ids=[slow.id])
        full_scan.assert_not_called()
        aggregate.assert_not_called()
        shareholder.assert_not_called()
        grant.refresh_from_db()
        self.assertIsNone(grant.revoked_at)
        self.assertEqual(grant.stage, 20000)
        self.assertNotIn('value', _row(read_player_state(self.user.id), 'ability.time.b'))

    def test_better_video_updates_grant_without_aggregation(self):
        first = self.make_video(timems=19000, upload_time=self.earlier)
        self.scan()
        self.wear(self.user, ['ability.time.b'])
        faster = self.make_video(timems=14000, upload_time=self.later)
        with patch('medal.services._evaluate_locked') as full_scan, patch('medal.services._aggregate_level') as aggregate:
            with self.captureOnCommitCallbacks(execute=True):
                refresh_player_medals(self.user.id, video_ids=[faster.id])
        full_scan.assert_not_called()
        aggregate.assert_not_called()
        grant = self.active()
        self.assertEqual(grant.stage, 15000)
        self.assertEqual(grant.video_id, faster.id)
        self.assertEqual(grant.evidence['video_id'], faster.id)
        self.assertNotEqual(grant.video_id, first.id)
        stored = _row(read_player_state(self.user.id), 'ability.time.b')
        self.assertEqual(stored['stage'], 15000)
        self.assertNotIn('value', stored)
        self.assertNotIn('locked', stored)

    def test_mode_level_nf_changes_invalidate_once_sets(self):
        video = self.make_video(timems=16000, upload_time=self.earlier)
        self.scan()

        def queued_kwargs():
            return DBTaskResult.objects.filter(
                task_path=task_refresh_player_medals.module_path, status=TaskResultStatus.READY,
            ).latest('id').args_kwargs['kwargs']

        video.mode = '01'
        with self.captureOnCommitCallbacks(execute=True):
            video.save(update_fields=['mode'])
        mode_change = queued_kwargs()
        self.assertTrue(mode_change['invalidate_once'])
        self.assertEqual(mode_change['degrade_levels'], ['b'])
        DBTaskResult.objects.filter(task_path=task_refresh_player_medals.module_path, status=TaskResultStatus.READY).delete()

        video.mode = '00'
        video.level = 'i'
        with self.captureOnCommitCallbacks(execute=True):
            video.save(update_fields=['mode', 'level'])
        level_change = queued_kwargs()
        self.assertTrue(level_change['invalidate_once'])
        self.assertCountEqual(level_change['degrade_levels'], ['b', 'i'])
        DBTaskResult.objects.filter(task_path=task_refresh_player_medals.module_path, status=TaskResultStatus.READY).delete()

        video.right_ce = 1
        with self.captureOnCommitCallbacks(execute=True):
            video.save(update_fields=['right_ce'])
        self.assertTrue(queued_kwargs()['invalidate_once'])

    def test_worse_score_and_delete_aggregate_only_the_affected_level(self):
        beginner = self.make_video(timems=16000, upload_time=self.earlier)
        self.make_video(level='e', timems=400000, upload_time=self.earlier)
        self.scan()
        beginner.timems = 25000
        with self.captureOnCommitCallbacks(execute=True):
            beginner.save(update_fields=['timems'])
        queued = DBTaskResult.objects.get(task_path=task_refresh_player_medals.module_path, status=TaskResultStatus.READY)
        self.assertEqual(queued.args_kwargs['kwargs']['degrade_levels'], ['b'])
        self.assertNotIn('invalidate_once', queued.args_kwargs['kwargs'])
        self.assertEqual(queued.args_kwargs['kwargs']['video_ids'], [beginner.id])
        calls = []

        def spy(user, level):
            calls.append(level)
            return _aggregate_level(user, level)

        with patch('medal.services._evaluate_locked') as full_scan, patch('medal.services._aggregate_level', spy):
            with self.captureOnCommitCallbacks(execute=True):
                task_refresh_player_medals.call(self.user.id, **queued.args_kwargs['kwargs'])
        full_scan.assert_not_called()
        self.assertEqual(calls, ['b'])
        self.assertIsNone(self.active())
        self.assertNotIn('ability.time.b', [row['code'] for row in read_player_state(self.user.id)['grants']])

        kept = self.make_video(timems=19000, upload_time=self.earlier)
        best = self.make_video(timems=16000, upload_time=self.later)
        caches['default'].clear()
        self.scan()
        self.wear(self.user, ['ability.time.b'])
        self.assertEqual(self.active().video_id, kept.id)
        with self.captureOnCommitCallbacks(execute=True):
            VideoModel.objects.filter(pk=best.id).delete()
        deleted = DBTaskResult.objects.filter(task_path=task_refresh_player_medals.module_path, status=TaskResultStatus.READY).latest('id')
        self.assertIn('b', deleted.args_kwargs['kwargs']['degrade_levels'])
        self.assertNotIn('e', deleted.args_kwargs['kwargs'].get('degrade_levels') or [])
        self.assertIsNotNone(read_player_state(self.user.id))
        calls.clear()
        with patch('medal.services._evaluate_locked') as full_scan, patch('medal.services._aggregate_level', spy):
            with self.captureOnCommitCallbacks(execute=True):
                task_refresh_player_medals.call(self.user.id, **deleted.args_kwargs['kwargs'])
        full_scan.assert_not_called()
        self.assertEqual(calls, ['b'])
        grant = self.active()
        self.assertEqual(grant.video_id, kept.id)
        self.assertEqual(grant.stage, 20000)
        self.assertNotIn('value', _row(read_player_state(self.user.id), 'ability.time.b'))

    def test_backfill_command_enqueues_only_unscanned_players(self):
        scanned = UserProfile.objects.create_user(username='medal_scanned', email='medal-scanned@example.com', password='password')
        MedalScan.objects.create(user=scanned, scanned_at=timezone.now())
        pending = UserProfile.objects.create_user(username='medal_pending', email='medal-pending@example.com', password='password')
        call_command('enqueue_medal_backfill')
        rows = DBTaskResult.objects.filter(task_path=task_backfill_player_medals.module_path)
        self.assertCountEqual([row.args_kwargs['args'][0] for row in rows], [self.user.id, pending.id])
        self.assertTrue(all(row.priority == 0 for row in rows))
        self.assertFalse(MedalScan.objects.filter(user=pending).exists())
        self.assertIsNone(read_player_state(pending.id))

    def test_state_api_hides_stage_zero_and_locked_entries(self):
        write_player_state(self.user.id, {
            'grants': [
                {'code': 'ability.time.b', 'stage': 20000, 'value': 15230, 'timestamp': 1761123456, 'scope': '', 'tournament': None, 'rank': None},
                {'code': 'ability.bvs.b', 'stage': 0, 'value': 12000, 'timestamp': None, 'scope': '', 'tournament': None, 'rank': None},
                {'code': 'ability.stnb.b', 'stage': 10, 'value': 10, 'timestamp': 1761120000, 'scope': '', 'tournament': None, 'rank': None, 'locked': True},
            ],
        })
        other = UserProfile.objects.create_user(username='medal_state_other', email='medal-state-other@example.com', password='password')
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(f'/api/medal/players/state?ids={self.user.id},{other.id},{self.user.id}')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(re.search(r'medal_medalgrant|videomanager_video', '\n'.join(query['sql'] for query in captured)))
        body = response.json()
        self.assertEqual([item['user_id'] for item in body], [self.user.id, other.id])
        self.assertEqual(body[1]['grants'], [])
        visible = {'code': 'ability.time.b', 'stage': 20000, 'timestamp': 1761123456, 'scope': '', 'tournament': None, 'rank': None}
        self.assertEqual(body[0]['grants'], [visible])
        self.assertNotIn('value', body[0]['grants'][0])
        self.assertNotIn('locked', body[0]['grants'][0])
        detail = self.client.get(f'/api/medal/players/{self.user.id}')
        self.assertEqual(detail.status_code, 200)
        self.assertIn('series', detail.json())
        self.assertIn('scan_pending', detail.json())
        self.assertEqual(self.client.get('/api/medal/players/state?ids=1,abc').status_code, 400)
        self.assertEqual(self.client.get('/api/medal/players/state?ids=' + ','.join(str(item) for item in range(1, 102))).status_code, 400)

    def test_locked_code_is_not_granted_again(self):
        self.make_video(timems=19000, upload_time=self.earlier)
        self.scan()
        staff = UserProfile.objects.create_user(username='medal_state_staff', email='medal-state-staff@example.com', password='password', is_staff=True)
        with self.captureOnCommitCallbacks(execute=True):
            set_player_override(staff, self.user.id, 'ability.time.b', '', 'revoke', '更正')
        self.assertNotIn('ability.time.b', [row['code'] for row in read_player_state(self.user.id)['grants']])
        faster = self.make_video(timems=10000, upload_time=self.later)
        with patch('medal.services._evaluate_locked') as full_scan:
            with self.captureOnCommitCallbacks(execute=True):
                refresh_player_medals(self.user.id, video_ids=[faster.id])
        full_scan.assert_not_called()
        self.assertIsNone(self.active())
        self.assertNotIn('ability.time.b', [row['code'] for row in read_player_state(self.user.id)['grants']])

    def test_commit_rewrites_state_from_database(self):
        self.make_video(timems=19000, upload_time=self.earlier)
        self.scan()
        self.wear(self.user, ['ability.time.b'])
        write_player_state(self.user.id, {'grants': []})
        self.assertEqual(read_player_state(self.user.id), {'grants': []})
        _flush_player_states([self.user.id])
        stored = read_player_state(self.user.id)
        self.assertEqual(_row(stored, 'ability.time.b')['stage'], 20000)
        self.assertNotIn('value', _row(stored, 'ability.time.b'))

    def test_ungranted_modes_merge_without_requerying_official_videos(self):
        self.make_video(mode='00', upload_time=self.earlier)
        self.scan()
        self.assertEqual(PlayerProgress.objects.get(user=self.user, code=NOVICE_MODES).extra['modes'], ['00'])
        second = self.make_video(mode='01', upload_time=self.later)
        with patch('medal.services._novice_modes_found') as found, patch('medal.services._evaluate_locked') as full_scan:
            with self.captureOnCommitCallbacks(execute=True):
                refresh_player_medals(self.user.id, video_ids=[second.id])
        full_scan.assert_not_called()
        found.assert_not_called()
        self.assertEqual(PlayerProgress.objects.get(user=self.user, code=NOVICE_MODES).extra['modes'], ['00', '01'])
        self.assertNotIn(NOVICE_MODES, [row['code'] for row in read_player_state(self.user.id)['grants']])
        self.assertIsNone(self.active(NOVICE_MODES))

        modes = list(open_modes())
        for mode in modes:
            self.make_video(mode=mode, upload_time=self.later)
        last = self.make_video(mode=modes[-1], upload_time=self.later)
        PlayerProgress.objects.filter(user=self.user, code=NOVICE_MODES).update(extra={'modes': modes[:-1]})
        MedalGrant.objects.filter(user=self.user, definition_code=NOVICE_MODES).delete()
        with patch('medal.services._novice_modes_found') as found, patch('medal.services._evaluate_locked') as full_scan:
            with self.captureOnCommitCallbacks(execute=True):
                refresh_player_medals(self.user.id, video_ids=[last.id])
        full_scan.assert_not_called()
        found.assert_not_called()
        grant = self.active(NOVICE_MODES)
        self.assertIsNotNone(grant)
        self.wear(self.user, [NOVICE_MODES])
        self.assertNotIn('modes', _row(read_player_state(self.user.id), NOVICE_MODES))

    def test_missing_modes_set_falls_back_to_database_once(self):
        modes = list(open_modes())
        for mode in modes[:-1]:
            self.make_video(mode=mode, upload_time=self.earlier)
        self.scan()
        PlayerProgress.objects.filter(user=self.user, code=NOVICE_MODES).update(extra=None)
        last = self.make_video(mode=modes[-1], upload_time=self.later)
        # 没有 modes 字段时若只并当前录像，凑不齐历史模式，发不出勋章。
        with patch('medal.services._evaluate_locked') as full_scan:
            with self.captureOnCommitCallbacks(execute=True):
                refresh_player_medals(self.user.id, video_ids=[last.id])
        full_scan.assert_not_called()
        self.assertIsNotNone(self.active(NOVICE_MODES))

    def test_sub3_video_save_repairs_parked_task_and_updates_summary_and_history(self):
        first = self.make_video(timems=3994, upload_time=self.earlier)
        self.scan()
        self.wear(self.user, ['ability.time.b'])
        enqueue_player_refresh(self.user.id)
        row = DBTaskResult.objects.get(task_path=task_refresh_player_medals.module_path)
        DBTaskResult.objects.filter(pk=row.pk).update(run_after=timezone.now().replace(year=9999))
        faster = self.make_video(timems=2484, upload_time=self.later)
        with patch('speedranking.signals.sync_video'), patch('effranking.signals.sync_video'), patch('videomanager.signals.newest_cache'), patch('customranking.signals.remove_from_custom_pluck_rank'):
            with self.captureOnCommitCallbacks(execute=True):
                faster.save(update_fields=['timems'])
        row.refresh_from_db()
        self.assertLessEqual(row.run_after, timezone.now() + REFRESH_COALESCE_DELAY)
        self.assertEqual(DBTaskResult.objects.filter(task_path=task_refresh_player_medals.module_path, status=TaskResultStatus.READY).count(), 1)
        self.assertTrue(player_refresh_pending(self.user.id))
        DBTaskResult.objects.filter(pk=row.pk).update(status=TaskResultStatus.RUNNING)
        self.assertTrue(player_refresh_pending(self.user.id))
        with self.captureOnCommitCallbacks(execute=True):
            task_refresh_player_medals.call(*row.args_kwargs['args'], **row.args_kwargs['kwargs'])
        DBTaskResult.objects.filter(pk=row.pk).update(status=TaskResultStatus.SUCCESSFUL)
        self.assertFalse(player_refresh_pending(self.user.id))
        grant = self.active()
        self.assertEqual(grant.stage, 3000)
        self.assertEqual(grant.video_id, faster.id)
        self.assertEqual(grant.granted_at, first.upload_time)
        self.assertEqual([(entry['stage'], entry['evidence_id']) for entry in grant.stage_log], [(4000, first.id), (3000, faster.id)])
        summary = player_summary(self.user.id)
        item = next(item for series in summary['series'] for item in series['items'] if item['code'] == 'ability.time.b')
        self.assertEqual((item['stage'], item['video_id']), (3000, faster.id))
        self.assertEqual(_row(read_player_state(self.user.id), 'ability.time.b')['stage'], 3000)


class MedalStateQueueTests(MedalTestCase):
    def setUp(self):
        self.user = UserProfile.objects.create_user(username='medal_state_queue', email='medal-state-queue@example.com')

    def test_ready_refresh_merges_video_ids(self):
        before = timezone.now()
        first = enqueue_player_refresh(self.user.id, video_ids=[11], degrade_levels=['b'])
        self.assertIsNotNone(first)
        row = DBTaskResult.objects.get(task_path=task_refresh_player_medals.module_path)
        self.assertEqual(row.priority, 1)
        self.assertGreaterEqual(row.run_after, before + REFRESH_COALESCE_DELAY)
        scheduled = row.run_after
        self.assertIsNone(enqueue_player_refresh(self.user.id, video_ids=[12], invalidate_once=True))
        row.refresh_from_db()
        self.assertEqual(row.run_after, scheduled)
        self.assertEqual(row.args_kwargs['args'], [self.user.id])
        self.assertEqual(row.args_kwargs['kwargs']['video_ids'], [11, 12])
        self.assertEqual(row.args_kwargs['kwargs']['degrade_levels'], ['b'])
        self.assertTrue(row.args_kwargs['kwargs']['invalidate_once'])
        self.assertIsNone(enqueue_player_refresh(self.user.id))
        row.refresh_from_db()
        self.assertEqual(row.run_after, scheduled)
        self.assertEqual(row.args_kwargs['kwargs'], {'full': True})

    def test_far_future_ready_task_is_brought_forward_even_when_payload_is_unchanged(self):
        for enqueue, task in [(enqueue_player_refresh, task_refresh_player_medals), (enqueue_player_backfill, task_backfill_player_medals)]:
            with self.subTest(task=task.module_path):
                enqueue(self.user.id)
                row = DBTaskResult.objects.get(task_path=task.module_path)
                DBTaskResult.objects.filter(pk=row.pk).update(run_after=timezone.now().replace(year=9999))
                before = timezone.now()
                self.assertIsNone(enqueue(self.user.id))
                row.refresh_from_db()
                self.assertGreaterEqual(row.run_after, before)
                limit = timezone.now() + REFRESH_COALESCE_DELAY if task is task_refresh_player_medals else timezone.now()
                self.assertLessEqual(row.run_after, limit)
                self.assertEqual(DBTaskResult.objects.filter(task_path=task.module_path).count(), 1)

    def test_upload_merges_into_old_full_task_and_repairs_its_schedule(self):
        enqueue_player_refresh(self.user.id)
        row = DBTaskResult.objects.get(task_path=task_refresh_player_medals.module_path)
        DBTaskResult.objects.filter(pk=row.pk).update(run_after=timezone.now().replace(year=9999))
        enqueue_player_refresh(self.user.id, video_ids=[6])
        row.refresh_from_db()
        self.assertEqual(row.args_kwargs['kwargs'], {'full': True})
        self.assertLessEqual(row.run_after, timezone.now() + REFRESH_COALESCE_DELAY)

    def test_worker_claiming_task_during_merge_does_not_lose_new_video(self):
        enqueue_player_refresh(self.user.id, video_ids=[11])
        original_first = QuerySet.first

        def claim_before_lock(queryset):
            if queryset.model is DBTaskResult:
                DBTaskResult.objects.filter(task_path=task_refresh_player_medals.module_path, status=TaskResultStatus.READY).update(status=TaskResultStatus.RUNNING)
            return original_first(queryset)

        with patch.object(QuerySet, 'first', autospec=True, side_effect=claim_before_lock):
            self.assertIsNotNone(enqueue_player_refresh(self.user.id, video_ids=[12]))
        ready = DBTaskResult.objects.get(task_path=task_refresh_player_medals.module_path, status=TaskResultStatus.READY)
        self.assertEqual(ready.args_kwargs['kwargs']['video_ids'], [12])
        self.assertEqual(DBTaskResult.objects.filter(task_path=task_refresh_player_medals.module_path, status=TaskResultStatus.RUNNING).count(), 1)
