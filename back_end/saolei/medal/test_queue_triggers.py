from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from threading import Barrier
from unittest.mock import patch

from django.db import close_old_connections, connection
from django.tasks import TaskResultStatus
from django.test import override_settings, skipUnlessDBFeature, TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django_tasks_db.models import DBTaskResult

from config.text_choices import MS_TextChoices, Tournament_TextChoices
from identifier.models import Identifier
from identifier.services import bind_identifier, unbind_identifier
from msuser.models import UserMS
from tournament.models import Tournament
from tournament.services import reveal_videos_for_tournament
from userprofile.models import UserProfile
from userprofile.services import update_user_names
from videomanager.models import ExpandVideoModel, VideoModel
from .tasks import enqueue_player_backfill, enqueue_player_refresh, task_backfill_player_medals, task_refresh_player_medals


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class MedalQueueTriggerTests(TestCase):
    def setUp(self):
        self.userms = UserMS.objects.create()
        self.user = UserProfile.objects.create_user(username='medal_queue', email='medal-queue@example.com', userms=self.userms)

    def make_videos(self, count=2, *, player=None, ongoing_tournament=False):
        player = player or self.user
        videos = []
        for _ in range(count):
            expand = ExpandVideoModel.objects.create(identifier='medal-bulk')
            videos.append(VideoModel(
                player=player, video=expand, file='videos/medal-bulk.evf', software='e',
                level='b', mode='00', state=MS_TextChoices.State.IDENTIFIER,
                ongoing_tournament=ongoing_tournament, timems=10000, bv=50,
                left=50, right=10, double=0, left_ce=50, right_ce=10, double_ce=0,
            ))
        VideoModel.objects.bulk_create(videos)
        return list(VideoModel.objects.filter(video_id__in=[video.video_id for video in videos]))

    def test_realname_profile_service_refreshes_after_commit(self):
        with patch('userprofile.services.verify_text', return_value=True), patch('medal.signals.enqueue_player_refresh') as enqueue:
            with self.captureOnCommitCallbacks(execute=True):
                update_user_names(self.user.id, {'realname': '测试姓名'}, '127.0.0.1')
                enqueue.assert_not_called()
            enqueue.assert_called_once_with(self.user.id)
        self.user.refresh_from_db()
        self.assertEqual(self.user._realname, '测试姓名')

    def test_unrelated_profile_save_does_not_refresh(self):
        with patch('medal.signals.enqueue_player_refresh') as enqueue, self.captureOnCommitCallbacks(execute=True):
            self.user.save(update_fields=['date_updated'])
        enqueue.assert_not_called()

    def test_bind_and_unbind_batch_refresh_one_player_after_commit(self):
        videos = self.make_videos()
        identifier = Identifier.objects.create(identifier='medal-bulk', safe=True)
        dependencies = [
            'newest_cache.update_bulk', 'update_video_count_limit_from_videos',
            'add_videos_to_speed_ranks', 'add_videos_to_custom_pluck_ranks', 'add_videos_to_eff_ranks',
            'remove_videos_from_speed_ranks', 'remove_videos_from_custom_pluck_ranks', 'remove_videos_from_eff_ranks',
        ]
        with ExitStack() as stack:
            for dependency in dependencies:
                stack.enter_context(patch(f'identifier.services.{dependency}'))
            enqueue = stack.enter_context(patch('medal.signals.enqueue_player_refresh'))
            for operation, expected_state in [
                (bind_identifier, MS_TextChoices.State.OFFICIAL),
                (unbind_identifier, MS_TextChoices.State.IDENTIFIER),
            ]:
                with self.captureOnCommitCallbacks(execute=True):
                    self.assertEqual(operation(identifier, self.userms), len(videos))
                    enqueue.assert_not_called()
                enqueue.assert_called_once_with(self.user.id)
                enqueue.reset_mock()
                self.assertEqual(set(VideoModel.objects.values_list('state', flat=True)), {expected_state})

    def test_rolled_back_batch_does_not_refresh(self):
        self.make_videos()
        identifier = Identifier.objects.create(identifier='medal-bulk', safe=True)
        with patch('medal.signals.enqueue_player_refresh') as enqueue, self.captureOnCommitCallbacks(execute=True):
            with patch('identifier.services.newest_cache.update_bulk', side_effect=RuntimeError('rollback')):
                with self.assertRaises(RuntimeError):
                    bind_identifier(identifier, self.userms)
        enqueue.assert_not_called()
        self.assertFalse(VideoModel.objects.filter(state=MS_TextChoices.State.OFFICIAL).exists())

    def test_tournament_bulk_reveal_refreshes_distinct_affected_players(self):
        other = UserProfile.objects.create_user(username='medal_queue_other', email='medal-other@example.com')
        videos = self.make_videos(ongoing_tournament=True)
        videos += self.make_videos(1, player=other, ongoing_tournament=True)
        still_hidden = self.make_videos(1, ongoing_tournament=True)[0]
        awarded = Tournament.objects.create(state=Tournament_TextChoices.State.AWARDED)
        ongoing = Tournament.objects.create(state=Tournament_TextChoices.State.NORMAL)
        awarded.videos.add(*videos, still_hidden)
        ongoing.videos.add(still_hidden)
        with ExitStack() as stack:
            for dependency in ['add_videos_to_state_queues_bulk', 'add_videos_to_speed_ranks', 'add_videos_to_custom_pluck_ranks', 'add_videos_to_eff_ranks']:
                stack.enter_context(patch(f'tournament.services.{dependency}'))
            enqueue = stack.enter_context(patch('medal.signals.enqueue_player_refresh'))
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(reveal_videos_for_tournament(awarded), 3)
                enqueue.assert_not_called()
            self.assertEqual(enqueue.call_count, 2)
            self.assertEqual({call.args[0] for call in enqueue.call_args_list}, {self.user.id, other.id})
        still_hidden.refresh_from_db()
        self.assertTrue(still_hidden.ongoing_tournament)
        self.assertFalse(VideoModel.objects.filter(pk__in=[video.pk for video in videos], ongoing_tournament=True).exists())

    def test_enqueue_filters_player_in_database_and_coalesces_each_task_type(self):
        other = UserProfile.objects.create_user(username='medal_queue_other', email='medal-other@example.com')
        for enqueue, player_task in [
            (enqueue_player_refresh, task_refresh_player_medals),
            (enqueue_player_backfill, task_backfill_player_medals),
        ]:
            enqueue(other.id)
            with CaptureQueriesContext(connection) as queries:
                self.assertIsNotNone(enqueue(self.user.id))
            lookups = [query['sql'] for query in queries if query['sql'].lstrip().upper().startswith('SELECT') and DBTaskResult._meta.db_table in query['sql']]
            self.assertEqual(len(lookups), 1)
            # The payload belongs in the WHERE clause, not in a queue-wide result set.
            self.assertNotIn('args_kwargs', lookups[0].split('FROM')[0])
            self.assertIn('args_kwargs', lookups[0].split('WHERE')[1])
            self.assertIsNone(enqueue(self.user.id))
            self.assertEqual(DBTaskResult.objects.filter(task_path=player_task.module_path).count(), 2)
            DBTaskResult.objects.filter(task_path=player_task.module_path, args_kwargs__args=[self.user.id]).update(status=TaskResultStatus.RUNNING)
            self.assertIsNotNone(enqueue(self.user.id))

    def test_enqueue_of_deleted_player_is_ignored(self):
        self.assertIsNone(enqueue_player_refresh(-1))
        self.assertFalse(DBTaskResult.objects.exists())


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class MedalQueueConcurrencyTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_concurrent_producers_create_one_ready_task_per_type(self):
        user = UserProfile.objects.create_user(username='medal_concurrent', email='medal-concurrent@example.com')
        for enqueue, player_task in [
            (enqueue_player_refresh, task_refresh_player_medals),
            (enqueue_player_backfill, task_backfill_player_medals),
        ]:
            barrier = Barrier(2)

            def produce(enqueue=enqueue, barrier=barrier):
                close_old_connections()
                try:
                    barrier.wait(timeout=10)
                    return enqueue(user.id) is not None
                finally:
                    close_old_connections()

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(produce) for _ in range(2)]
                results = [future.result(timeout=30) for future in futures]
            self.assertEqual(sum(results), 1)
            self.assertEqual(DBTaskResult.objects.filter(task_path=player_task.module_path, status=TaskResultStatus.READY, args_kwargs__args=[user.id]).count(), 1)
