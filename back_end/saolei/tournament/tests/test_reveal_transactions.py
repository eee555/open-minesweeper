from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.db import connection, transaction
from django.tasks import TaskResultStatus
from django.test import override_settings, TransactionTestCase
from django_tasks_db.models import DBTaskResult
from redis.exceptions import TimeoutError as RedisTimeoutError

from config.text_choices import MS_TextChoices, Tournament_TextChoices
from customranking.models import CustomPluckRecord
from medal.tasks import enqueue_player_refresh, task_refresh_player_medals
from userprofile.models import UserProfile
from videomanager.models import ExpandVideoModel, VideoModel
from ..models import Tournament
from ..services import reveal_videos_for_tournament


class TournamentRevealTransactionTests(TransactionTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.enterContext(override_settings(TOP_RANKING_LOCK_PATH=Path(directory.name) / 'top.sqlite3'))
        self.queue_redis = self.enterContext(patch('videomanager.cache.cache'))
        self.pluck_redis = self.enterContext(patch('customranking.cache.cache'))
        self.speed_refresh = self.enterContext(patch('speedranking.services._update_videos'))
        self.eff_refresh = self.enterContext(patch('effranking.services._update_videos'))
        self.user = UserProfile.objects.create_user(username='reveal_transaction', email='reveal-transaction@example.com')
        # Skip setup signals; only the reveal operation should publish cache data.
        Tournament.objects.bulk_create([Tournament(state=Tournament_TextChoices.State.AWARDED)])
        self.tournament = Tournament.objects.get()
        self.video = self.make_video(self.user)

    def make_video(self, player):
        video = VideoModel(
            player=player, video=ExpandVideoModel.objects.create(), file='videos/reveal-test.evf',
            software=MS_TextChoices.Software.EVF, level=MS_TextChoices.Level.CUSTOM_8_8_40,
            mode=MS_TextChoices.Mode.STD, state=MS_TextChoices.State.OFFICIAL,
            ongoing_tournament=True, timems=10000, pluck=1, bv=50,
            left=50, right=10, double=0, left_ce=50, right_ce=10, double_ce=0,
        )
        VideoModel.objects.bulk_create([video])
        video = VideoModel.objects.get(video_id=video.video_id)
        self.tournament.videos.add(video)
        return video

    def ready_medal_players(self):
        tasks = DBTaskResult.objects.filter(task_path=task_refresh_player_medals.module_path, status=TaskResultStatus.READY)
        return [payload['args'][0] for payload in tasks.values_list('args_kwargs', flat=True)]

    def assert_public(self):
        self.video.refresh_from_db()
        self.assertFalse(self.video.ongoing_tournament)

    def assert_queue_contains(self, *video_ids):
        self.queue_redis.hset.assert_called_once()
        self.assertEqual(set(self.queue_redis.hset.call_args.kwargs['mapping']), set(video_ids))

    def test_outer_rollback_does_not_publish_cache_or_enqueue_medals(self):
        with self.assertRaisesMessage(RuntimeError, 'rollback reveal'):
            with transaction.atomic():
                self.assertEqual(reveal_videos_for_tournament(self.tournament), 1)
                self.queue_redis.hset.assert_not_called()
                self.pluck_redis.zadd.assert_not_called()
                self.pluck_redis.hset.assert_not_called()
                self.assertFalse(CustomPluckRecord.objects.exists())
                self.assertEqual(self.ready_medal_players(), [])
                raise RuntimeError('rollback reveal')
        self.video.refresh_from_db()
        self.assertTrue(self.video.ongoing_tournament)
        self.assertFalse(CustomPluckRecord.objects.exists())
        self.assertEqual(self.ready_medal_players(), [])
        self.queue_redis.hset.assert_not_called()
        self.pluck_redis.zadd.assert_not_called()
        self.pluck_redis.hset.assert_not_called()
        self.speed_refresh.assert_not_called()
        self.eff_refresh.assert_not_called()

    def test_success_publishes_only_after_outer_commit(self):
        queue_transaction_states = []

        def check_committed(*args, **kwargs):
            queue_transaction_states.append(connection.in_atomic_block)

        self.queue_redis.hset.side_effect = check_committed
        with transaction.atomic():
            self.assertEqual(reveal_videos_for_tournament(self.tournament), 1)
            self.queue_redis.hset.assert_not_called()
            self.pluck_redis.hset.assert_not_called()
            self.speed_refresh.assert_not_called()
            self.eff_refresh.assert_not_called()
            self.assertFalse(CustomPluckRecord.objects.exists())
            self.assertEqual(self.ready_medal_players(), [])
        self.assert_public()
        self.assertEqual(queue_transaction_states, [False])
        self.assert_queue_contains(self.video.pk)
        self.assertTrue(CustomPluckRecord.objects.filter(video=self.video).exists())
        self.pluck_redis.zadd.assert_called_once()
        self.pluck_redis.hset.assert_called_once()
        self.speed_refresh.assert_called_once()
        self.eff_refresh.assert_called_once()
        self.assertEqual(self.ready_medal_players(), [self.user.pk])

    def test_custom_rank_cache_timeout_keeps_reveal_and_other_callbacks(self):
        self.pluck_redis.hset.side_effect = RedisTimeoutError('custom ranking cache unavailable')
        with self.assertLogs('django.db.backends.base', level='ERROR') as logs:
            self.assertEqual(reveal_videos_for_tournament(self.tournament), 1)
        self.assertIn('custom ranking cache unavailable', '\n'.join(logs.output))
        self.assert_public()
        self.assert_queue_contains(self.video.pk)
        self.pluck_redis.zadd.assert_called_once()
        self.pluck_redis.hset.assert_called_once()
        self.speed_refresh.assert_called_once()
        self.eff_refresh.assert_called_once()
        self.assertEqual(self.ready_medal_players(), [self.user.pk])

    def test_queue_cache_timeout_does_not_skip_rankings_or_medals(self):
        self.queue_redis.hset.side_effect = RedisTimeoutError('newest queue unavailable')
        with self.assertLogs('django.db.backends.base', level='ERROR') as logs:
            self.assertEqual(reveal_videos_for_tournament(self.tournament), 1)
        self.assertIn('newest queue unavailable', '\n'.join(logs.output))
        self.assert_public()
        self.assertTrue(CustomPluckRecord.objects.filter(video=self.video).exists())
        self.pluck_redis.hset.assert_called_once()
        self.speed_refresh.assert_called_once()
        self.eff_refresh.assert_called_once()
        self.assertEqual(self.ready_medal_players(), [self.user.pk])

    def test_speed_rank_failure_does_not_skip_other_callbacks(self):
        self.speed_refresh.side_effect = RedisTimeoutError('speed ranking cache unavailable')
        with self.assertLogs('django.db.backends.base', level='ERROR') as logs:
            self.assertEqual(reveal_videos_for_tournament(self.tournament), 1)
        self.assertIn('speed ranking cache unavailable', '\n'.join(logs.output))
        self.assert_public()
        self.assert_queue_contains(self.video.pk)
        self.assertTrue(CustomPluckRecord.objects.filter(video=self.video).exists())
        self.pluck_redis.hset.assert_called_once()
        self.eff_refresh.assert_called_once()
        self.assertEqual(self.ready_medal_players(), [self.user.pk])

    def test_medal_enqueue_failure_does_not_skip_other_players_or_caches(self):
        other = UserProfile.objects.create_user(username='reveal_other', email='reveal-other@example.com')
        other_video = self.make_video(other)

        def enqueue(player_id):
            if player_id == self.user.pk:
                raise RuntimeError('medal queue unavailable')
            return enqueue_player_refresh(player_id)

        with patch('medal.signals.enqueue_player_refresh', side_effect=enqueue), self.assertLogs('django.db.backends.base', level='ERROR') as logs:
            self.assertEqual(reveal_videos_for_tournament(self.tournament), 2)
        self.assertIn('medal queue unavailable', '\n'.join(logs.output))
        self.assert_public()
        other_video.refresh_from_db()
        self.assertFalse(other_video.ongoing_tournament)
        self.assert_queue_contains(self.video.pk, other_video.pk)
        self.assertEqual(CustomPluckRecord.objects.count(), 2)
        self.assertEqual(self.pluck_redis.hset.call_count, 2)
        self.speed_refresh.assert_called_once()
        self.eff_refresh.assert_called_once()
        self.assertEqual(self.ready_medal_players(), [other.pk])
