from unittest.mock import patch

from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from tournament.models import Tournament, TournamentParticipant
from videomanager.models import VideoModel
from . import tests
from .models import MedalGrant, MedalPins, MedalScan, PlayerMedalSummary, PlayerProgress
from .services import active_definitions, evaluate_player, MedalError, player_summary, replace_pins, set_player_override, write_stage


class MedalSummaryTests(tests.MedalShellFixture):
    make_video = tests.BasicMedalTests.make_video

    def setUp(self):
        super().setUp()
        self.ids = iter(range(6_000_000, 7_000_000))

    def items(self, summary):
        return [item for group in summary['series'] for item in group['items']]

    def test_existing_player_is_backfilled_without_scanning_videos(self):
        grant = MedalGrant.objects.create(user=self.user, definition_code=self.definition.code, stage=50000, granted_at=self.granted_at)
        PlayerProgress.objects.create(user=self.user, definition=self.definition, code=self.definition.code, current_stage=50000, current_value=49000)
        MedalPins.objects.create(user=self.user, grant_ids=[grant.id])
        MedalScan.objects.create(user=self.user, scanned_at=timezone.now())
        active_definitions()
        with CaptureQueriesContext(connection) as queries:
            result = player_summary(self.user.id)
        self.assertFalse(any('videomanager_videomodel' in query['sql'] for query in queries))
        self.assertFalse(result['scan_pending'])
        self.assertEqual(result['score'], 5)
        self.assertEqual(result['pin_ids'], [grant.id])
        self.assertIsNone(result['pins'][0]['current_value'])
        with self.assertNumQueries(1):
            self.assertEqual(player_summary(self.user.id), result)

    def test_unscanned_player_and_missing_user_remain_distinct(self):
        self.assertTrue(player_summary(self.user.id)['scan_pending'])
        with self.assertNumQueries(1):
            self.assertTrue(player_summary(self.user.id)['scan_pending'])
        with self.assertNumQueries(1), self.assertRaises(MedalError) as error:
            player_summary(0)
        self.assertEqual(error.exception.code, 'user')
        evaluate_player(self.user.id)
        with self.assertNumQueries(1):
            self.assertFalse(player_summary(self.user.id)['scan_pending'])

    def test_summary_pins_and_grants_roll_back_together(self):
        grant = write_stage(self.user, self.definition, stage=60000, current_value=59000)
        replace_pins(self.user, [grant.id])
        before = player_summary(self.user.id)
        with self.assertRaisesRegex(RuntimeError, 'rollback'), transaction.atomic():
            write_stage(self.user, self.definition, stage=50000, current_value=49000)
            replace_pins(self.user, [])
            self.assertEqual(player_summary(self.user.id)['score'], 5)
            raise RuntimeError('rollback')
        self.assertEqual(player_summary(self.user.id), before)
        self.assertEqual(MedalGrant.objects.get(pk=grant.id).stage, 60000)
        self.assertEqual(MedalPins.objects.get(user=self.user).grant_ids, [grant.id])

    def test_summary_write_failure_rolls_back_business_changes(self):
        grant = write_stage(self.user, self.definition, stage=60000, current_value=59000)
        before = player_summary(self.user.id)
        with patch.object(PlayerMedalSummary, 'save', side_effect=RuntimeError('summary failure')):
            with self.assertRaisesRegex(RuntimeError, 'summary failure'):
                write_stage(self.user, self.definition, stage=50000, current_value=49000)
        self.assertEqual(MedalGrant.objects.get(pk=grant.id).stage, 60000)
        self.assertEqual(player_summary(self.user.id), before)

    def test_definition_changes_apply_without_rewriting_each_player(self):
        grant = write_stage(self.user, self.definition, stage=50000, current_value=49000)
        replace_pins(self.user, [grant.id])
        data = PlayerMedalSummary.objects.get(user=self.user).data
        self.definition.score_by_stage = [30, 50, 80]
        self.definition.save(update_fields=['score_by_stage'])
        self.assertEqual(player_summary(self.user.id)['score'], 50)
        self.definition.hidden = True
        self.definition.annotation = '已解锁说明'
        self.definition.save(update_fields=['hidden', 'annotation'])
        self.assertEqual(player_summary(self.user.id)['pins'][0]['annotation'], '已解锁说明')
        self.assertEqual(player_summary(self.user.id)['score'], 0)
        self.definition.active = False
        self.definition.save(update_fields=['active'])
        result = player_summary(self.user.id)
        self.assertEqual(result['pin_ids'], [])
        self.assertNotIn(self.definition.code, [item['code'] for item in self.items(result)])
        self.assertEqual(PlayerMedalSummary.objects.get(user=self.user).data, data)

    def test_manual_override_and_revocation_update_the_summary(self):
        self.user.is_staff = True
        grant = set_player_override(self.user, self.user.id, self.definition.code, '', 'grant', '人工复核', stage=50000)
        replace_pins(self.user, [grant.id])
        self.assertEqual(player_summary(self.user.id)['pins'][0]['stage'], 50000)
        self.assertNotIn('reason', str(PlayerMedalSummary.objects.get(user=self.user).data))
        set_player_override(self.user, self.user.id, self.definition.code, '', 'revoke', '撤销')
        result = player_summary(self.user.id)
        self.assertEqual(result['pin_ids'], [])
        self.assertEqual(result['score'], 0)

    def test_evaluation_preserves_scoped_grants_in_summary(self):
        grant = write_stage(self.user, self.definition, scope_key='event:1', stage=50000, evidence={'rank': 2, 'tournament_id': 123})
        replace_pins(self.user, [grant.id])
        evaluate_player(self.user.id)
        item = player_summary(self.user.id)['pins'][0]
        self.assertEqual(item['grant_id'], grant.id)
        self.assertEqual(item['scope_key'], 'event:1')
        self.assertEqual(item['rank'], 2)
        self.assertEqual(item['tournament_id'], 123)
        self.assertIsNone(item['current_value'])

    def test_unchanged_evaluation_does_not_rewrite_summary(self):
        evaluate_player(self.user.id)
        with patch.object(PlayerMedalSummary, 'save', side_effect=AssertionError('unexpected summary write')):
            evaluate_player(self.user.id)

    def test_deleted_video_does_not_leave_a_stale_evidence_link(self):
        video = self.make_video()
        grant = write_stage(self.user, self.definition, stage=50000, current_value=49000, video=video)
        replace_pins(self.user, [grant.id])
        self.assertEqual(player_summary(self.user.id)['pins'][0]['video_id'], video.id)
        VideoModel.objects.filter(pk=video.id).delete()
        self.assertFalse(PlayerMedalSummary.objects.filter(user=self.user).exists())
        self.assertIsNone(player_summary(self.user.id)['pins'][0]['video_id'])

    def test_evidence_deletion_rollback_preserves_the_summary(self):
        video = self.make_video()
        grant = write_stage(self.user, self.definition, stage=50000, video=video)
        replace_pins(self.user, [grant.id])
        before = player_summary(self.user.id)
        with self.assertRaisesRegex(RuntimeError, 'rollback'), transaction.atomic():
            VideoModel.objects.filter(pk=video.id).delete()
            self.assertFalse(PlayerMedalSummary.objects.filter(user=self.user).exists())
            raise RuntimeError('rollback')
        self.assertEqual(player_summary(self.user.id), before)

    def test_deleted_participant_does_not_leave_a_stale_tournament_link(self):
        tournament = Tournament.objects.create()
        participant = TournamentParticipant.objects.create(tournament=tournament, user=self.user)
        grant = write_stage(self.user, self.definition, scope_key='event:1', stage=50000, participant=participant)
        replace_pins(self.user, [grant.id])
        self.assertEqual(player_summary(self.user.id)['pins'][0]['tournament_id'], tournament.id)
        participant.delete()
        self.assertFalse(PlayerMedalSummary.objects.filter(user=self.user).exists())
        self.assertIsNone(player_summary(self.user.id)['pins'][0]['tournament_id'])
