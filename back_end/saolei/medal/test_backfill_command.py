from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.tasks import TaskResultStatus
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from userprofile.models import UserProfile
from . import tests
from .models import MedalGrant, MedalScan, PlayerMedalSummary, PlayerProgress
from .services import evaluate_player, replace_pins, set_player_override
from .tasks import enqueue_player_backfill, task_backfill_player_medals
from .utils import NOVICE_MODES


class MedalBackfillCommandTests(tests.MedalTestCase):
    setUp = tests.BasicMedalTests.setUp
    make_video = tests.BasicMedalTests.make_video
    active = tests.BasicMedalTests.active

    def command(self, **options):
        output = StringIO()
        call_command('enqueue_medal_backfill', stdout=output, **options)
        return output.getvalue()

    def pending(self):
        return DBTaskResult.objects.filter(task_path=task_backfill_player_medals.module_path, status=TaskResultStatus.READY)

    def test_all_recalculates_scanned_player_from_impossible_old_modes(self):
        videos = [self.make_video(mode=mode, upload_time=self.earlier) for mode in ('00', '05', '06')]
        completing = self.make_video(mode='10', upload_time=self.later)
        videos.append(completing)
        # 模拟旧版本十模式规则留下的玩家状态。
        with patch('medal.services.open_modes', return_value=['00', '01', '04', '05', '06', '07', '08', '09', '10', '11']):
            evaluate_player(self.user.id)
        self.assertTrue(MedalScan.objects.filter(user=self.user).exists())
        self.assertIsNone(self.active(NOVICE_MODES))
        retained = self.active('ability.time.b')
        replace_pins(self.user, [retained.pk])
        progress_id = PlayerProgress.objects.get(user=self.user, code=NOVICE_MODES).pk
        self.command()
        self.assertFalse(self.pending().exists())
        self.assertIn('Enqueued 1', self.command(all=True, batch_size=1))
        self.assertIsNone(self.active(NOVICE_MODES))  # 命令只入队，不同步扫描录像。
        queued = self.pending().get()
        self.assertEqual(queued.priority, 0)
        with self.captureOnCommitCallbacks(execute=True):
            task_backfill_player_medals.call(self.user.id)
        grant = self.active(NOVICE_MODES)
        self.assertEqual(grant.stage, 1)
        self.assertEqual(grant.granted_at, completing.upload_time)
        self.assertEqual(set(grant.evidence['video_ids']), {video.id for video in videos})
        self.assertEqual(PlayerProgress.objects.get(user=self.user, code=NOVICE_MODES).pk, progress_id)
        self.assertEqual(PlayerMedalSummary.objects.get(user=self.user).data['pin_ids'], [retained.pk])
        evaluate_player(self.user.id)
        self.assertEqual(self.active(NOVICE_MODES).pk, grant.pk)
        self.assertEqual(MedalGrant.objects.filter(user=self.user, definition_code=NOVICE_MODES).count(), 1)

    def test_default_and_all_selection_and_dry_run(self):
        MedalScan.objects.create(user=self.user, scanned_at=timezone.now())
        other = UserProfile.objects.create_user(username='unscanned', email='unscanned@example.com')
        self.assertIn('Dry run: 1 players', self.command(dry_run=True))
        self.assertIn('Dry run: 2 players', self.command(all=True, dry_run=True))
        self.assertFalse(self.pending().exists())
        self.command()
        self.assertEqual(list(self.pending().values_list('args_kwargs', flat=True)), [{'args': [other.pk], 'kwargs': {}}])

    def test_limits_resume_bounds_and_existing_ready_task_deduplication(self):
        users = [self.user] + [UserProfile.objects.create_user(username=f'backfill-{index}', email=f'backfill-{index}@example.com') for index in range(3)]
        enqueue_player_backfill(self.user.pk)
        output = self.command(all=True, batch_size=1, limit=2, through_id=users[2].pk)
        self.assertIn(f'last_user_id={users[1].pk}', output)
        self.assertEqual(self.pending().count(), 2)
        self.command(all=True, after_id=users[1].pk, through_id=users[2].pk)
        self.assertEqual(self.pending().count(), 3)
        ids = {row['args'][0] for row in self.pending().values_list('args_kwargs', flat=True)}
        self.assertEqual(ids, {user.pk for user in users[:3]})

    def test_invalid_options_do_not_enqueue(self):
        for options in ({'batch_size': 0}, {'limit': 0}, {'after_id': -1}, {'through_id': -1}):
            with self.subTest(options=options), self.assertRaises(CommandError):
                self.command(all=True, **options)
        self.assertFalse(self.pending().exists())

    def test_all_preserves_manual_revoke(self):
        for mode in ('00', '05', '06', '10'):
            self.make_video(mode=mode)
        staff = UserProfile.objects.create_user(username='backfill-staff', email='backfill-staff@example.com', is_staff=True)
        set_player_override(staff, self.user.pk, NOVICE_MODES, '', 'revoke', '人工禁止')
        self.command(all=True)
        with self.captureOnCommitCallbacks(execute=True):
            task_backfill_player_medals.call(self.user.pk)
        self.assertIsNone(self.active(NOVICE_MODES))

    def test_all_does_not_award_incomplete_mode_set(self):
        for mode in ('00', '05', '06'):
            self.make_video(mode=mode)
        self.command(all=True)
        with self.captureOnCommitCallbacks(execute=True):
            task_backfill_player_medals.call(self.user.pk)
        self.assertIsNone(self.active(NOVICE_MODES))
        self.assertEqual(PlayerProgress.objects.get(user=self.user, code=NOVICE_MODES).extra['modes'], ['00', '05', '06'])

    def test_snapshot_upper_bound_excludes_new_players(self):
        def add_new_player(user_id):
            self.assertEqual(user_id, self.user.pk)
            UserProfile.objects.create_user(username='created-during-backfill', email='new-backfill@example.com')
            return object()

        with patch('medal.management.commands.enqueue_medal_backfill.enqueue_player_backfill', side_effect=add_new_player) as enqueue:
            self.command(all=True, batch_size=1)
        enqueue.assert_called_once_with(self.user.pk)

    def test_failure_reports_last_successful_cursor(self):
        other = UserProfile.objects.create_user(username='failed-enqueue', email='failed-enqueue@example.com')
        with patch('medal.management.commands.enqueue_medal_backfill.enqueue_player_backfill', side_effect=[object(), RuntimeError('queue unavailable')]):
            with self.assertRaisesRegex(CommandError, f'--after-id {self.user.pk} --through-id {other.pk}'):
                self.command(all=True)
