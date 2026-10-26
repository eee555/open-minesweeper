from datetime import timedelta
from unittest.mock import patch

from django.core.cache import caches
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from config.text_choices import MS_TextChoices
from msuser.models import UserMS
from userprofile.models import UserProfile
from videomanager.models import VideoModel
from videomanager.services import set_import_upload_time
from . import tests
from .cache import delete_player_states
from .models import MedalDefinition, PlayerProgress
from .services import ensure_basic_definitions, player_states, player_summary, refresh_player_medals, set_player_override
from .tasks import task_refresh_player_medals
from .utils import NOVICE_LEVELS, NOVICE_LEVELS_NF, NOVICE_MODES, NOVICE_REVIEW, SHAREHOLDER_CODE


class MedalVideoHistoryTests(tests.MedalTestCase):
    make_video = tests.BasicMedalTests.make_video
    active = tests.BasicMedalTests.active

    def setUp(self):
        caches['default'].clear()
        self.user = UserProfile.objects.create_user(username='history', email='history@example.com', userms=UserMS.objects.create())
        self.ids = iter(range(4_000_000, 5_000_000))
        self.earlier = timezone.now() - timedelta(days=5)
        self.middle = self.earlier + timedelta(days=2)
        self.later = self.earlier + timedelta(days=4)

    def scan(self):
        with self.captureOnCommitCallbacks(execute=True):
            refresh_player_medals(self.user.id, full=True)

    def refresh(self, *videos):
        with self.captureOnCommitCallbacks(execute=True):
            refresh_player_medals(self.user.id, video_ids=[video.id for video in videos])

    def change_upload_time(self, video, at, *, imported=False):
        # 保留真实保存信号和勋章任务，隔离其他排行及最新录像队列的 Redis 写入。
        with patch('speedranking.signals.sync_video'), patch('effranking.signals.sync_video'), patch('videomanager.signals.newest_cache'), patch('customranking.signals.remove_from_custom_pluck_rank'):
            with self.captureOnCommitCallbacks(execute=True):
                if imported:
                    set_import_upload_time(video, at)
                else:
                    video.upload_time = at
                    video.save(update_fields=['upload_time'])
        video.refresh_from_db()
        self.assertEqual(video.upload_time, at)
        queued = DBTaskResult.objects.get(task_path=task_refresh_player_medals.module_path)
        self.assertIn(video.id, queued.args_kwargs['kwargs']['video_ids'])
        delete_player_states([self.user.id])
        with self.captureOnCommitCallbacks(execute=True):
            task_refresh_player_medals.call(*queued.args_kwargs['args'], **queued.args_kwargs['kwargs'])

    def assert_history(self, code, records):
        grant = self.active(code)
        expected = [{'stage': stage, 'at': video.upload_time.isoformat(), 'evidence_id': video.id} for stage, video in records]
        self.assertEqual([{key: entry[key] for key in ('stage', 'at', 'evidence_id')} for entry in grant.stage_log], expected)
        self.assertEqual(grant.granted_at, min(video.upload_time for _stage, video in records))
        current = next(video for stage, video in records if stage == grant.stage)
        if code != 'ability.thrp.nf.three':
            self.assertEqual(grant.video_id, current.id)
            self.assertEqual(grant.evidence['video_id'], current.id)
        summary = player_summary(self.user.id)
        item = next(item for group in summary['series'] for item in group['items'] if item['code'] == code)
        self.assertEqual(item['granted_at'], grant.granted_at.isoformat())
        self.assertEqual(item['video_id'], grant.video_id)
        self.wear(self.user, [code])
        cached = next(item for item in player_states([self.user.id])[0]['grants'] if item['code'] == code)
        self.assertEqual(cached['timestamp'], int(grant.granted_at.timestamp()))
        return grant

    def test_backdated_same_stage_replaces_earliest_evidence(self):
        self.make_video(timems=16000, upload_time=self.later)
        self.scan()
        grant_id = self.active('ability.time.b').id
        older = self.make_video(timems=19000, upload_time=self.earlier)
        delete_player_states([self.user.id])
        self.refresh(older)
        grant = self.assert_history('ability.time.b', [(20000, older)])
        self.assertEqual(grant.id, grant_id)
        self.assertIsNone(PlayerProgress.objects.get(user=self.user, code='ability.time.b').best_video_id)
        self.assert_history(NOVICE_REVIEW, [(1, older)])

    def test_sub50_faster_same_stage_does_not_write_then_sub40_upgrades(self):
        code = 'ability.time.e'
        ensure_basic_definitions()
        MedalDefinition.objects.exclude(code=code).update(active=False)
        first = self.make_video(level='e', timems=48000, upload_time=self.earlier)
        self.scan()
        faster = self.make_video(level='e', timems=46000, upload_time=self.middle)
        with patch('medal.services._aggregate_level') as aggregate, CaptureQueriesContext(connection) as captured:
            self.refresh(faster)
        aggregate.assert_not_called()
        self.assertFalse(any(query['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for query in captured))
        self.assert_history(code, [(50000, first)])
        with CaptureQueriesContext(connection) as captured:
            self.scan()
        self.assertFalse(any(query['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for query in captured))
        self.assert_history(code, [(50000, first)])
        progress = PlayerProgress.objects.get(user=self.user, code=code)
        self.assertIsNone(progress.current_value)
        self.assertIsNone(progress.best_video_id)
        self.assertEqual(progress.current_stage, 50000)
        higher = self.make_video(level='e', timems=39000, upload_time=self.later)
        self.refresh(higher)
        self.assert_history(code, [(50000, first), (40000, higher)])

    def test_backdated_equal_score_and_timestamp_tie_use_stable_evidence(self):
        first = self.make_video(timems=19000, upload_time=self.later)
        self.scan()
        older = self.make_video(timems=19000, upload_time=self.earlier)
        self.refresh(older)
        self.assert_history('ability.time.b', [(20000, older)])
        self.change_upload_time(first, self.earlier, imported=True)
        self.assert_history('ability.time.b', [(20000, first)])

    def test_backdated_upgrade_corrects_prior_stage_without_duplicate_nodes(self):
        self.make_video(timems=19000, upload_time=self.later)
        self.scan()
        older = self.make_video(timems=14000, upload_time=self.earlier)
        self.refresh(older)
        self.assert_history('ability.time.b', [(20000, older), (15000, older)])
        self.refresh(older)
        self.scan()
        self.assert_history('ability.time.b', [(20000, older), (15000, older)])

    def test_backdated_lower_stage_corrects_first_date_without_changing_current_evidence(self):
        self.make_video(timems=19000, upload_time=self.middle)
        self.scan()
        higher = self.make_video(timems=14000, upload_time=self.later)
        self.refresh(higher)
        older = self.make_video(timems=18000, upload_time=self.earlier)
        self.refresh(older)
        self.assert_history('ability.time.b', [(20000, older), (15000, higher)])

    def test_import_time_save_updates_dates_logs_and_api(self):
        video = self.make_video(timems=19000, upload_time=self.later)
        self.scan()
        self.change_upload_time(video, self.earlier, imported=True)
        self.assert_history('ability.time.b', [(20000, video)])
        self.assert_history(NOVICE_REVIEW, [(1, video)])
        response = self.client.get(f'/api/medal/players/{self.user.id}')
        self.assertEqual(response.status_code, 200)
        item = next(item for group in response.json()['series'] for item in group['items'] if item['code'] == 'ability.time.b')
        self.assertEqual(item['granted_at'], self.earlier.isoformat(timespec='milliseconds').replace('+00:00', 'Z'))

    def test_move_evidence_later_selects_next_earliest_video(self):
        first = self.make_video(timems=19000, upload_time=self.earlier)
        fallback = self.make_video(timems=16000, upload_time=self.middle)
        self.scan()
        self.change_upload_time(first, self.later)
        self.assert_history('ability.time.b', [(20000, fallback)])
        self.assert_history(NOVICE_REVIEW, [(1, fallback)])

    def test_move_only_evidence_later_updates_first_date(self):
        video = self.make_video(timems=19000, upload_time=self.earlier)
        self.scan()
        self.change_upload_time(video, self.later)
        self.assert_history('ability.time.b', [(20000, video)])

    def test_edit_old_stage_evidence_after_upgrade_repairs_both_nodes(self):
        first = self.make_video(timems=19000, upload_time=self.earlier)
        self.scan()
        higher = self.make_video(timems=14000, upload_time=self.middle)
        self.refresh(higher)
        self.change_upload_time(first, self.later)
        self.assert_history('ability.time.b', [(20000, higher), (15000, higher)])

    def test_full_refresh_repairs_dates_even_when_score_and_stage_unchanged(self):
        video = self.make_video(timems=16000, upload_time=self.later)
        self.scan()
        older = self.make_video(timems=19000, upload_time=self.middle)
        self.scan()
        self.assert_history('ability.time.b', [(20000, older)])
        VideoModel.objects.filter(pk=video.id).update(upload_time=self.earlier)
        video.refresh_from_db()
        self.scan()
        self.assert_history('ability.time.b', [(20000, video)])

    def test_batch_uses_earliest_qualifying_video_not_first_or_fastest(self):
        self.scan()
        fastest = self.make_video(timems=14000, upload_time=self.later)
        older = self.make_video(timems=14500, upload_time=self.earlier)
        self.refresh(fastest, older)
        self.assert_history('ability.time.b', [(15000, older)])
        self.assert_history(NOVICE_REVIEW, [(1, older)])

    def test_unqualified_older_video_does_not_replace_pb_evidence(self):
        video = self.make_video(timems=19000, upload_time=self.middle)
        self.scan()
        touched = [
            self.make_video(timems=20000, upload_time=self.earlier),
            self.make_video(timems=1000, state=MS_TextChoices.State.FROZEN, upload_time=self.earlier),
            self.make_video(timems=1000, ongoing=True, upload_time=self.earlier),
            self.make_video(timems=1000, mode='05', upload_time=self.earlier),
        ]
        self.refresh(*touched)
        self.assert_history('ability.time.b', [(20000, video)])

    def test_levels_track_every_component_when_noncompleting_video_moves_later(self):
        beginner = self.make_video(level='b', upload_time=self.earlier)
        intermediate = self.make_video(level='i', upload_time=self.middle)
        expert = self.make_video(level='e', upload_time=self.middle)
        self.scan()
        for code in (NOVICE_LEVELS, NOVICE_LEVELS_NF):
            self.assert_history(code, [(1, expert)])
        self.change_upload_time(beginner, self.later)
        for code in (NOVICE_LEVELS, NOVICE_LEVELS_NF):
            grant = self.assert_history(code, [(1, beginner)])
            self.assertEqual(grant.evidence['video_ids'], [beginner.id, intermediate.id, expert.id])

    def test_backdated_modes_use_configured_set_and_completion_date(self):
        self.scan()
        definition = MedalDefinition.objects.get(code=NOVICE_MODES)
        definition.scope = {'modes': ['00', '05']}
        definition.save(update_fields=['scope'])
        standard = self.make_video(mode='00', upload_time=self.earlier)
        self.make_video(mode='05', upload_time=self.later)
        self.scan()
        older = self.make_video(mode='05', upload_time=self.middle)
        self.refresh(older)
        grant = self.assert_history(NOVICE_MODES, [(1, older)])
        self.assertEqual(grant.evidence['video_ids'], [standard.id, older.id])

    def test_composite_uses_earliest_threshold_evidence_not_latest_best(self):
        first = self.make_video(level='b', bv=95, left_ce=100, upload_time=self.earlier)
        self.make_video(level='b', bv=100, left_ce=100, upload_time=self.later)
        intermediate = self.make_video(level='i', bv=95, left_ce=100, upload_time=self.middle)
        expert = self.make_video(level='e', bv=95, left_ce=100, upload_time=self.middle)
        self.scan()
        grant = self.assert_history('ability.thrp.nf.three', [(95000, expert)])
        self.assertEqual(grant.evidence['video_ids'], [first.id, intermediate.id, expert.id])
        self.assertEqual(grant.stage_log[0]['video_ids'], grant.evidence['video_ids'])

    def test_composite_backfill_and_component_time_edit_refresh_full_proof(self):
        beginner = self.make_video(level='b', upload_time=self.earlier)
        intermediate = self.make_video(level='i', upload_time=self.earlier)
        self.make_video(level='e', upload_time=self.later)
        self.scan()
        older = self.make_video(level='e', upload_time=self.earlier)
        delete_player_states([self.user.id])
        self.refresh(older)
        grant = self.assert_history('ability.thrp.nf.three', [(100000, older)])
        self.assertEqual(grant.evidence['video_ids'], [beginner.id, intermediate.id, older.id])
        self.change_upload_time(beginner, self.middle)
        self.assert_history('ability.thrp.nf.three', [(100000, beginner)])

    def test_shareholder_backfill_keeps_min_id_progress_and_corrects_evidence(self):
        smallest = self.make_video(video_id=2000, upload_time=self.later)
        self.scan()
        older = self.make_video(video_id=5000, upload_time=self.earlier)
        delete_player_states([self.user.id])
        self.refresh(older)
        self.assert_history(SHAREHOLDER_CODE, [(10000, older)])
        self.assertEqual(PlayerProgress.objects.get(user=self.user, code=SHAREHOLDER_CODE).best_video_id, smallest.id)
        self.change_upload_time(older, self.later + timedelta(days=1))
        self.assert_history(SHAREHOLDER_CODE, [(10000, smallest)])

    def test_manual_override_is_preserved_during_backfill_and_full_refresh(self):
        self.make_video(timems=19000, upload_time=self.middle)
        self.scan()
        actor = UserProfile.objects.create_user(username='history_staff', email='history-staff@example.com', is_staff=True)
        for code, stage in [('ability.time.b', 15000), (NOVICE_REVIEW, 1)]:
            set_player_override(actor, self.user.id, code, '', 'grant', 'reviewed', stage=stage, granted_at=self.later)
        before = {code: self.active(code) for code in ('ability.time.b', NOVICE_REVIEW)}
        older = self.make_video(timems=14000, upload_time=self.earlier)
        self.refresh(older)
        self.scan()
        for code, original in before.items():
            grant = self.active(code)
            self.assertEqual(grant.granted_at, original.granted_at)
            self.assertEqual(grant.evidence, original.evidence)
            self.assertEqual(grant.stage_log, original.stage_log)

    def test_deleted_or_disqualified_historical_evidence_is_replaced(self):
        first = self.make_video(timems=19000, upload_time=self.earlier)
        fallback = self.make_video(timems=18000, upload_time=self.middle)
        self.scan()
        higher = self.make_video(timems=14000, upload_time=self.later)
        self.refresh(higher)
        self.delete_video(first.id)
        self.refresh(first)
        self.assert_history('ability.time.b', [(20000, fallback), (15000, higher)])
        VideoModel.objects.filter(pk=fallback.id).update(state=MS_TextChoices.State.FROZEN)
        self.refresh(fallback)
        self.assert_history('ability.time.b', [(20000, higher), (15000, higher)])

    def test_repeat_refresh_has_no_business_writes_and_later_slow_video_skips_history(self):
        video = self.make_video(timems=19000, upload_time=self.earlier)
        self.scan()
        with CaptureQueriesContext(connection) as queries:
            self.refresh(video)
            self.scan()
        writes = [row['sql'] for row in queries if row['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE '))]
        self.assertEqual(writes, [])
        later = self.make_video(timems=30000, upload_time=self.later)
        with patch('medal.services._sync_video_history') as sync:
            self.refresh(later)
        sync.assert_not_called()
