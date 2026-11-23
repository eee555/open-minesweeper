from datetime import timedelta
from io import StringIO
import json
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.db import transaction
from django.test import override_settings, TestCase
from django.utils import timezone

from config.customranking import CUSTOM_PLUCK_LEVELS
from config.text_choices import MS_TextChoices
from userprofile.models import UserProfile
from videomanager.models import ExpandVideoModel, MAX_TIMEMS, VideoModel
from .cache import get_player_pluck_records, PLuckRankingCache, read_records, video_to_score
from .services import add_videos_to_custom_pluck_ranks, refresh_custom_pluck_rank_range, remove_videos_from_custom_pluck_ranks

LEVEL = MS_TextChoices.Level.CUSTOM_8_8_40
SECOND_LEVEL = MS_TextChoices.Level.CUSTOM_16_16_100


@override_settings(RATELIMIT_ENABLE=False)
class PluckRankingTests(TestCase):
    def setUp(self):
        self.now = timezone.now().replace(microsecond=0)
        self.players = [UserProfile.objects.create_user(username=f'pluck_{index}', email=f'pluck-{index}@example.com') for index in range(3)]
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.enterContext(override_settings(MEDIA_ROOT=directory.name))
        for target in ['speedranking.services._sync_video', 'effranking.services._sync_video']:
            self.enterContext(patch(target))
        self.clear_cache()

    def tearDown(self):
        self.clear_cache()

    def clear_cache(self):
        for level in CUSTOM_PLUCK_LEVELS:
            PLuckRankingCache(level).flush()

    def video(self, *, player=None, pluck=1, timems=1000, seconds=0, level=LEVEL, **fields):
        expand = ExpandVideoModel.objects.create(identifier='pluck-test')
        # Keep replay and expansion ids different to catch accidental use of video.video_id.
        video = VideoModel(
            id=expand.pk + 1_000_000, player=player or self.players[0], video=expand,
            file='videos/pluck-test.evf', file_size=1, software=MS_TextChoices.Software.EVF,
            level=level, mode=MS_TextChoices.Mode.STD, state=MS_TextChoices.State.OFFICIAL,
            bv=40, pluck=pluck, timems=timems,
        )
        for field, value in fields.items():
            setattr(video, field, value)
        VideoModel.objects.bulk_create([video])
        VideoModel.objects.filter(pk=video.pk).update(upload_time=self.now + timedelta(seconds=seconds))
        video.refresh_from_db()
        return video

    def seed(self, **fields):
        video = self.video(**fields)
        PLuckRankingCache(video.level).add_record_batch([video])
        return video

    def record(self, player=None, level=LEVEL):
        return get_player_pluck_records((player or self.players[0]).pk, [level]).get(level)

    def update_video(self, video, **fields):
        for field, value in fields.items():
            setattr(video, field, value)
        with self.captureOnCommitCallbacks(execute=True):
            video.save(update_fields=set(fields))

    def test_save_compares_pluck_time_and_upload_and_backfills_worsened_record(self):
        first = self.seed(pluck=2)
        candidate = self.video(pluck=3, timems=2000, seconds=10)
        self.update_video(candidate, pluck=2)
        self.assertEqual(self.record()['video_id'], first.pk)
        self.update_video(candidate, timems=1000)
        self.assertEqual(self.record()['video_id'], first.pk)
        self.update_video(candidate, upload_time=self.now - timedelta(seconds=1))
        self.assertEqual(self.record()['video_id'], candidate.pk)
        with patch('customranking.services.best_videos') as candidates:
            self.update_video(candidate, pluck=1)
        candidates.assert_not_called()
        self.assertEqual(self.record()['pluck'], 1)
        self.update_video(candidate, pluck=4)
        self.assertEqual(self.record()['video_id'], first.pk)

    def test_create_and_save_wait_for_commit_and_use_the_current_saved_video(self):
        with self.captureOnCommitCallbacks(execute=True):
            video = VideoModel.objects.create(
                player=self.players[0], video=ExpandVideoModel.objects.create(), file='videos/pluck-test.evf',
                software=MS_TextChoices.Software.EVF, level=LEVEL, mode=MS_TextChoices.Mode.STD,
                state=MS_TextChoices.State.OFFICIAL, bv=40, timems=1000, pluck=2,
            )
            self.assertIsNone(self.record())
            video.pluck = 1
            video.save(update_fields=['pluck'])
            self.assertIsNone(self.record())
            VideoModel.objects.filter(pk=video.pk).update(pluck=0.5)
        self.assertEqual(self.record()['pluck'], 0.5)
        self.assertEqual(self.record()['video_id'], video.pk)

    def test_state_mode_and_hidden_changes_remove_and_restore_qualification(self):
        video = self.seed()
        for field, invalid, valid in (
            ('state', MS_TextChoices.State.IDENTIFIER, MS_TextChoices.State.OFFICIAL),
            ('mode', MS_TextChoices.Mode.QWC, MS_TextChoices.Mode.STD),
            ('ongoing_tournament', True, False), ('pluck', None, 1),
        ):
            with self.subTest(field=field):
                self.update_video(video, **{field: invalid})
                self.assertIsNone(self.record())
                self.update_video(video, **{field: valid})
                self.assertEqual(self.record()['video_id'], video.pk)

    def test_player_and_level_move_rebuilds_old_category_and_adds_new_category(self):
        video = self.seed(pluck=1)
        backup = self.video(pluck=2)
        self.update_video(video, player=self.players[1], level=SECOND_LEVEL)
        self.assertEqual(self.record()['video_id'], backup.pk)
        self.assertEqual(self.record(self.players[1], SECOND_LEVEL)['video_id'], video.pk)

    def test_delete_backfills_and_clears_last_record_for_instance_and_queryset(self):
        for queryset in (False, True):
            with self.subTest(queryset=queryset):
                best = self.seed()
                second = self.video(pluck=2)
                backup = self.video(pluck=3)
                with self.captureOnCommitCallbacks(execute=True):
                    if queryset:
                        VideoModel.objects.filter(pk__in=[best.pk, second.pk]).delete()
                    else:
                        best.delete()
                self.assertEqual(self.record()['video_id'], backup.pk if queryset else second.pk)
                with self.captureOnCommitCallbacks(execute=True):
                    VideoModel.objects.filter(player=self.players[0]).delete()
                self.assertIsNone(self.record())
                self.assertEqual(len(PLuckRankingCache(LEVEL)), 0)

    def test_non_record_delete_does_not_query_candidates(self):
        best = self.seed()
        other = self.video(pluck=2)
        with patch('customranking.services.best_videos') as candidates:
            with self.captureOnCommitCallbacks(execute=True):
                other.delete()
        candidates.assert_not_called()
        self.assertEqual(self.record()['video_id'], best.pk)

    def test_save_delete_and_bulk_rollback_leave_existing_cache_unchanged(self):
        best = self.seed()
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaisesMessage(RuntimeError, 'rollback'):
                with transaction.atomic():
                    best.pluck = 0
                    best.save(update_fields=['pluck'])
                    add_videos_to_custom_pluck_ranks(VideoModel.objects.filter(pk=best.pk))
                    VideoModel.objects.filter(pk=best.pk).delete()
                    raise RuntimeError('rollback')
        self.assertEqual(self.record()['video_id'], best.pk)
        self.assertEqual(self.record()['pluck'], 1)

    def test_user_cascade_clears_the_record_after_commit(self):
        self.seed()
        self.video(pluck=2)
        with self.captureOnCommitCallbacks(execute=True):
            UserProfile.objects.filter(pk=self.players[0].pk).delete()
        self.assertIsNone(self.record())

    def test_bulk_add_and_remove_only_replace_affected_categories(self):
        first = self.seed(pluck=2)
        candidate = self.video(pluck=1)
        other_level = self.video(level=SECOND_LEVEL)
        another_player = self.video(player=self.players[1], pluck=3)
        added = VideoModel.objects.filter(pk__in=[candidate.pk, other_level.pk, another_player.pk])
        with self.captureOnCommitCallbacks(execute=True):
            add_videos_to_custom_pluck_ranks(added)
        self.assertEqual(self.record()['video_id'], candidate.pk)
        self.assertEqual(self.record(level=SECOND_LEVEL)['video_id'], other_level.pk)
        with self.captureOnCommitCallbacks(execute=True):
            VideoModel.objects.filter(pk=candidate.pk).update(state=MS_TextChoices.State.IDENTIFIER)
            remove_videos_from_custom_pluck_ranks(VideoModel.objects.filter(pk=candidate.pk))
        self.assertEqual(self.record()['video_id'], first.pk)
        self.assertEqual(self.record(self.players[1])['video_id'], another_player.pk)
        self.assertEqual(self.record(level=SECOND_LEVEL)['video_id'], other_level.pk)

    def test_zero_score_and_existing_detail_format_work_with_incremental_updates(self):
        video = self.video(pluck=0, timems=MAX_TIMEMS)
        ranking = PLuckRankingCache(LEVEL)
        # This is the pre-refactor format, written without any model or rebuild service.
        ranking.client.zadd(ranking.rank_key, {str(video.player_id): 0})
        ranking.client.hset(ranking.detail_key, video.player_id, json.dumps({
            'video_id': video.pk, 'timems': video.timems, 'upload_time': video.upload_time.isoformat(),
        }))
        self.assertEqual(read_records([(video.player_id, LEVEL)])[video.player_id, LEVEL]['pluck'], 0)
        self.update_video(video, timems=1000)
        self.assertEqual(ranking.client.zscore(ranking.rank_key, video.player_id), video_to_score(video))
        self.assertEqual(self.record()['video_id'], video.pk)

    def test_public_rank_and_player_api_only_read_cache(self):
        first = self.seed(pluck=0, timems=2000)
        earlier = self.seed(player=self.players[1], pluck=0, timems=1000)
        self.seed(level=SECOND_LEVEL)
        PLuckRankingCache(SECOND_LEVEL).flush()
        VideoModel.objects.filter(pk=first.pk).update(pluck=9)
        response = self.client.get('/api/customranking/pluck', {'level': LEVEL})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([row['video_id'] for row in response.json()['players']], [earlier.pk, first.pk])
        response = self.client.get('/api/customranking/pluck/player', {'player_id': first.player_id})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), [{'level': LEVEL, 'video_id': first.pk, 'pluck': 0}])

    def test_rebuild_command_selects_from_videos_and_clears_stale_records(self):
        self.video(timems=1001)
        self.video(seconds=1)
        best = self.video()
        self.seed(player=self.players[1], state=MS_TextChoices.State.IDENTIFIER)
        outside = self.seed(level=SECOND_LEVEL)
        call_command('rebuild_custom_pluck_cache', level=LEVEL, batch_size=1, stdout=StringIO())
        self.assertEqual(PLuckRankingCache(LEVEL).get_rank_range(0, 10)[0]['video_id'], best.pk)
        self.assertEqual(len(PLuckRankingCache(LEVEL)), 1)
        self.assertEqual(self.record(level=SECOND_LEVEL)['video_id'], outside.pk)

    def test_admin_range_repairs_logged_incomplete_records_and_clears_stale_entries(self):
        best = self.seed()
        stale = self.seed(player=self.players[1], state=MS_TextChoices.State.IDENTIFIER)
        outside = self.seed(player=self.players[2], state=MS_TextChoices.State.IDENTIFIER)
        ranking = PLuckRankingCache(LEVEL)
        ranking.client.hdel(ranking.detail_key, best.player_id)
        ranking.client.zrem(ranking.rank_key, stale.player_id)
        with self.assertLogs('customranking', level='ERROR'):
            self.update_video(best, pluck=0.5)
        result = refresh_custom_pluck_rank_range(best.player_id, stale.player_id)
        self.assertEqual(result, {'errorList': [], 'successCount': 1})
        self.assertEqual(self.record()['video_id'], best.pk)
        self.assertEqual(self.record()['pluck'], 0.5)
        self.assertIsNone(ranking.client.zscore(ranking.rank_key, stale.player_id))
        self.assertIsNone(ranking.client.hget(ranking.detail_key, stale.player_id))
        self.assertEqual(self.record(self.players[2])['video_id'], outside.pk)
