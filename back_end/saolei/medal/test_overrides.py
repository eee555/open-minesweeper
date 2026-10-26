from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from unittest.mock import patch

from django.db import close_old_connections, connection
from django.test import override_settings, skipUnlessDBFeature, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from config.text_choices import Medal_TextChoices, MS_TextChoices
from userprofile.models import UserProfile
from videomanager.models import VideoModel
from . import services, tests
from .models import MedalDefinition, MedalGrant, MedalOverride, MedalOverrideLog, PlayerProgress
from .services import ensure_basic_definitions, evaluate_player, grant_manual, MedalError, player_summary, revoke_manual, set_player_override, write_stage
from .utils import NOVICE_REALNAME


class OverrideFixture:
    make_video = tests.BasicMedalTests.make_video
    delete_video = tests.MedalTestCase.delete_video

    def setUp(self):
        super().setUp()
        self.user = UserProfile.objects.create_user(username='override_player', email='override-player@example.com', password='password')
        self.actor = UserProfile.objects.create_user(username='override_staff', email='override-staff@example.com', password='password', is_staff=True)
        self.ids = iter(range(5_000_000, 6_000_000))
        self.earlier = timezone.now() - timedelta(days=4)
        self.middle = timezone.now() - timedelta(days=2)
        self.later = timezone.now() - timedelta(days=1)
        ensure_basic_definitions()

    def decide(self, code='ability.time.b', mode='grant', stage=15000, scope_key=''):
        return set_player_override(self.actor, self.user.id, code, scope_key, mode, '管理员复核', stage=stage, granted_at=self.later)

    def grant(self, code='ability.time.b'):
        return MedalGrant.objects.filter(user=self.user, definition_code=code, scope_key='').first()

    def progress(self, code='ability.time.b'):
        return PlayerProgress.objects.get(user=self.user, code=code)


class MedalOverrideTests(OverrideFixture, tests.MedalTestCase):
    def test_forced_stage_remains_fixed_while_real_progress_changes(self):
        forced = self.decide()
        self.assertFalse(PlayerProgress.objects.filter(user=self.user, code='ability.time.b').exists())
        evaluate_player(self.user.id)
        self.assertEqual(self.grant().stage, 15000)
        self.assertIsNone(self.grant().revoked_at)
        self.make_video(timems=19000)
        evaluate_player(self.user.id)
        self.assertEqual(self.progress().current_stage, 20000)
        fast = self.make_video(timems=500)
        evaluate_player(self.user.id)
        self.assertEqual(self.progress().current_stage, 1000)
        forced.refresh_from_db()
        self.assertEqual(forced.stage, 15000)
        self.assertEqual(forced.granted_at, self.later)
        self.assertTrue(forced.evidence['override'])
        self.assertIsNone(forced.video_id)
        self.delete_video(fast.id)
        VideoModel.objects.filter(player=self.user).update(state=MS_TextChoices.State.FROZEN)
        evaluate_player(self.user.id)
        self.assertEqual(self.progress().current_stage, 0)
        self.assertIsNone(self.grant().revoked_at)
        self.assertEqual(self.grant().stage, 15000)

    def test_forbidden_before_first_grant_and_restore_rebuilds_evidence(self):
        self.assertIsNone(self.decide(mode='revoke', stage=None))
        video = self.make_video(timems=19000, upload_time=self.earlier)
        evaluate_player(self.user.id)
        self.assertIsNone(self.grant())
        self.assertEqual(self.progress().current_stage, 20000)
        self.assertIsNone(self.decide(mode='auto', stage=None))
        evaluate_player(self.user.id)
        self.assertEqual(self.grant().video_id, video.id)
        self.assertEqual(self.grant().granted_at, video.upload_time)
        self.assertFalse(MedalOverride.objects.filter(user=self.user).exists())
        self.assertEqual(list(MedalOverrideLog.objects.filter(user=self.user).order_by('id').values_list('action', flat=True)), ['revoke', 'auto'])

    def test_restore_manual_grant_uses_real_stage_and_original_video_time(self):
        video = self.make_video(timems=19000, upload_time=self.earlier)
        evaluate_player(self.user.id)
        original = self.grant()
        self.decide(stage=1000)
        self.decide(mode='auto', stage=None)
        self.assertIsNotNone(self.grant().revoked_at)
        evaluate_player(self.user.id)
        restored = self.grant()
        self.assertEqual(restored.pk, original.pk)
        self.assertEqual(restored.stage, 20000)
        self.assertEqual(restored.video_id, video.id)
        self.assertEqual(restored.granted_at, video.upload_time)
        self.assertNotIn('override', restored.evidence)

    def test_forced_pb_does_not_promote_or_suppress_natural_composite(self):
        code = 'ability.thrp.nf.b'
        self.decide(code=code, stage=100000)
        for level in ('i', 'e'):
            self.make_video(level=level, bv=100, left_ce=100)
        evaluate_player(self.user.id)
        self.assertIsNone(self.grant('ability.thrp.nf.three'))
        beginner = self.make_video(level='b', bv=95, left_ce=100)
        evaluate_player(self.user.id)
        self.assertEqual(self.progress(code).current_stage, 95000)
        self.assertEqual(self.grant(code).stage, 100000)
        self.assertEqual(self.grant('ability.thrp.nf.three').stage, 95000)
        self.decide(code=code, mode='revoke', stage=None)
        evaluate_player(self.user.id)
        self.assertIsNotNone(self.grant(code).revoked_at)
        self.assertIsNone(self.grant('ability.thrp.nf.three').revoked_at)
        VideoModel.objects.filter(pk=beginner.id).update(state=MS_TextChoices.State.FROZEN)
        evaluate_player(self.user.id)
        self.assertEqual(self.progress(code).current_stage, 0)
        self.assertEqual(self.progress('ability.thrp.nf.three').current_stage, 0)
        self.assertIsNotNone(self.grant('ability.thrp.nf.three').revoked_at)

    def test_revoked_once_and_composite_still_clear_natural_progress(self):
        self.user.realname = '自然实名'
        self.user.save(update_fields=['_realname'])
        for level in ('b', 'i', 'e'):
            self.make_video(level=level, bv=100, left_ce=100)
        evaluate_player(self.user.id)
        self.decide(code=NOVICE_REALNAME, mode='revoke', stage=None)
        self.decide(code='ability.thrp.nf.three', mode='revoke', stage=None)
        self.user.realname = '匿名'
        self.user.save(update_fields=['_realname'])
        VideoModel.objects.filter(player=self.user).update(state=MS_TextChoices.State.FROZEN)
        evaluate_player(self.user.id)
        self.assertEqual(self.progress(NOVICE_REALNAME).current_stage, 0)
        self.assertEqual(self.progress('ability.thrp.nf.three').current_stage, 0)
        self.decide(code=NOVICE_REALNAME, mode='auto', stage=None)
        evaluate_player(self.user.id)
        self.assertIsNotNone(self.grant(NOVICE_REALNAME).revoked_at)

    def test_override_keeps_removed_threshold_and_allows_deleted_definition_auto(self):
        self.decide(stage=15000)
        definition = MedalDefinition.objects.get(pk='ability.time.b')
        definition.thresholds = [10000]
        definition.save(update_fields=['thresholds'])
        self.make_video(timems=500)
        evaluate_player(self.user.id)
        self.assertEqual(self.grant().stage, 15000)
        definition.delete()
        self.decide(mode='auto', stage=None)
        self.assertFalse(MedalOverride.objects.filter(user=self.user).exists())
        self.assertIsNotNone(self.grant().revoked_at)
        self.assertEqual(MedalOverrideLog.objects.filter(user=self.user).count(), 2)

    def test_auto_without_override_preserves_natural_grant_and_audit(self):
        self.make_video(timems=19000)
        evaluate_player(self.user.id)
        before = self.grant()
        self.decide(mode='auto', stage=None)
        after = self.grant()
        self.assertEqual(after.stage, before.stage)
        self.assertEqual(after.evidence, before.evidence)
        self.assertIsNone(after.revoked_at)
        self.assertFalse(MedalOverrideLog.objects.filter(user=self.user).exists())

    def test_legacy_entry_points_use_persistent_override_without_fake_progress(self):
        manual = MedalDefinition.objects.create(code='manual.override', series='纪念', kind=Medal_TextChoices.Kind.MANUAL, metric='manual', direction=Medal_TextChoices.Direction.ASC, thresholds=[], active=True)
        granted = grant_manual(self.actor, manual.code, self.user.id, '兼容授予', self.earlier)
        self.assertEqual(granted.stage, 1)
        self.assertFalse(PlayerProgress.objects.filter(user=self.user, code=manual.code).exists())
        self.assertEqual(MedalOverride.objects.get(user=self.user, definition_code=manual.code).mode, 'grant')
        revoke_manual(self.actor, granted.pk, '兼容撤销')
        self.assertEqual(MedalOverride.objects.get(user=self.user, definition_code=manual.code).mode, 'revoke')
        write_stage(self.user, manual, stage=1, current_value=1)
        granted.refresh_from_db()
        self.assertIsNotNone(granted.revoked_at)

    def test_overridden_pb_keeps_natural_stage_without_storing_best(self):
        self.make_video(timems=19000)
        evaluate_player(self.user.id)
        self.assertFalse(PlayerProgress.objects.filter(user=self.user, code='ability.bvs.b').exists())
        self.decide(stage=1000)
        with CaptureQueriesContext(connection) as captured:
            evaluate_player(self.user.id)
        self.assertFalse(any(query['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for query in captured))
        self.assertEqual(self.progress().current_stage, 20000)
        self.assertIsNone(self.progress().current_value)
        self.assertIsNone(self.progress().best_video_id)

    def test_normal_medals_cannot_create_scoped_duplicate_grants(self):
        with self.assertRaises(MedalError) as raised:
            self.decide(scope_key='event:1')
        self.assertEqual(raised.exception.code, 'scope')
        self.assertFalse(MedalOverride.objects.filter(user=self.user).exists())
        self.assertFalse(MedalOverrideLog.objects.filter(user=self.user).exists())

    def test_only_manual_medals_allow_stage_one_with_empty_thresholds(self):
        definition = MedalDefinition.objects.get(pk='ability.time.b')
        definition.thresholds = []
        definition.save(update_fields=['thresholds'])
        with self.assertRaises(MedalError) as raised:
            self.decide(stage=1)
        self.assertEqual(raised.exception.code, 'stage')
        self.assertFalse(MedalOverride.objects.filter(user=self.user).exists())


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'medal-override-concurrent'}})
class MedalOverrideConcurrencyTests(OverrideFixture, TransactionTestCase):
    def run_in_connection(self, operation):
        close_old_connections()
        try:
            return operation()
        finally:
            connection.close()

    @skipUnlessDBFeature('has_select_for_update')
    def test_manual_decision_waits_for_running_evaluation(self):
        self.make_video(timems=19000)
        locked = Event()
        release = Event()
        original_init = services._EvaluationState.__init__

        def pause_after_player_lock(state, user):
            original_init(state, user)
            locked.set()
            if not release.wait(10):
                raise TimeoutError('Timed out waiting to finish evaluation')

        with ThreadPoolExecutor(max_workers=2) as executor:
            with patch.object(services._EvaluationState, '__init__', pause_after_player_lock):
                evaluation = executor.submit(self.run_in_connection, lambda: evaluate_player(self.user.id))
                try:
                    self.assertTrue(locked.wait(10))
                    decision = executor.submit(self.run_in_connection, lambda: self.decide(stage=1000))
                finally:
                    release.set()
                evaluation.result(timeout=15)
                decision.result(timeout=15)
        self.assertEqual(self.grant().stage, 1000)
        self.assertEqual(self.progress().current_stage, 20000)
        self.assertEqual(MedalOverride.objects.filter(user=self.user).count(), 1)
        item = next(item for group in player_summary(self.user.id)['series'] for item in group['items'] if item['code'] == 'ability.time.b')
        self.assertEqual(item['stage'], 1000)

    @skipUnlessDBFeature('has_select_for_update')
    def test_evaluation_started_during_manual_decision_keeps_forced_stage(self):
        self.make_video(timems=19000)
        locked = Event()
        release = Event()
        original_update = MedalOverride.objects.update_or_create

        def pause_override_write(*args, **kwargs):
            locked.set()
            if not release.wait(10):
                raise TimeoutError('Timed out waiting to finish override')
            return original_update(*args, **kwargs)

        with ThreadPoolExecutor(max_workers=2) as executor:
            with patch.object(MedalOverride.objects, 'update_or_create', pause_override_write):
                decision = executor.submit(self.run_in_connection, lambda: self.decide(stage=1000))
                try:
                    self.assertTrue(locked.wait(10))
                    evaluation = executor.submit(self.run_in_connection, lambda: evaluate_player(self.user.id))
                finally:
                    release.set()
                decision.result(timeout=15)
                evaluation.result(timeout=15)
        self.assertEqual(self.grant().stage, 1000)
        self.assertEqual(self.progress().current_stage, 20000)
        self.assertEqual(MedalOverrideLog.objects.filter(user=self.user, action='grant').count(), 1)
        item = next(item for group in player_summary(self.user.id)['series'] for item in group['items'] if item['code'] == 'ability.time.b')
        self.assertEqual(item['stage'], 1000)
