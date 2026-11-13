"""作品服务层单测：投稿、投喂、审核、驳回、恢复、硬删除与低频命令；见 MEDIA_PLAN.md 第 12 节、附录 A。"""

from datetime import datetime, timedelta, timezone as datetime_timezone
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone
from django_tasks_db.models import DBTaskResult
from redis.exceptions import ConnectionError as RedisConnectionError

from config.common import TASK_CLEANUP_CONFIGS
from userprofile.models import UserProfile
from . import cache
from .models import Media, MediaLikes, UserMedia
from .services import (
    create_media, get_balance, hard_delete_media, like_media, MediaServiceError,
    reject_media, reopen_media, set_media_banned, sync_media_scores, verify_media,
)
from .utils import decay, MediaFormat, MediaStatus

REFERENCE = datetime(2026, 1, 1, tzinfo=datetime_timezone.utc)
TARGET = datetime(2026, 2, 1, tzinfo=datetime_timezone.utc)


class MediaServiceTests(TestCase):
    def setUp(self):
        cache.clear_rankings()
        cache.set_hot_reference(REFERENCE)
        self.user = UserProfile.objects.create_user(username='media-service', password='test-password')
        UserProfile.objects.filter(pk=self.user.pk).update(date_joined=timezone.now() - timedelta(days=10))
        self.user.refresh_from_db()
        self.actor = self.user
        # 空表兜底基准固定为 REFERENCE，令 T_db 与 T_r 可控、reference_factor() 为 1。
        patcher = patch.object(cache, 'default_hot_reference', return_value=REFERENCE)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        cache.clear_rankings()

    def _create_media(self, suffix='BV1xx411c7mD'):
        return create_media(
            self.user, media_format=MediaFormat.B_V, suffix=suffix, title='test title',
            created_at=timezone.now() - timedelta(days=1), language='',
        )

    def _like(self, media, times=1):
        for _ in range(times):
            like_media(self.user, media.pk)

    def test_balance_and_duplicate_submission(self):
        self.assertGreaterEqual(get_balance(self.user), 9)
        self._create_media()
        with self.assertRaises(MediaServiceError) as caught:
            self._create_media()
        self.assertEqual(caught.exception.status_code, 409)

    def test_like_pending_only_writes_db(self):
        media = self._create_media()
        self._like(media, 3)
        media.refresh_from_db()
        self.assertEqual(media.likes, 3)
        self.assertGreater(media.hot_value, 3)
        self.assertEqual(MediaLikes.objects.get(user=self.user, media=media).likes, 3)
        self.assertEqual(UserMedia.objects.get(pk=self.user.pk).likes_sent, 3)
        self.assertEqual(UserMedia.objects.get(pk=self.user.pk).daily_likes, 3)
        for key in cache.MEDIA_RANK_KEYS:
            self.assertEqual(cache.cache.zcard(key), 0)

    def test_verify_fills_four_zsets(self):
        media = self._create_media()
        self._like(media, 2)
        verify_media(media.pk, self.actor.pk)
        media.refresh_from_db()
        self.assertEqual(media.status, MediaStatus.VERIFIED)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_LIKES, media.pk), 2)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_LIKES, self.user.pk), 2)
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_HOT, media.pk), media.hot_value)
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk), media.hot_value)
        with self.assertRaises(MediaServiceError):
            verify_media(media.pk, self.actor.pk)

    def test_verified_like_writes_absolute_scores(self):
        media = self._create_media()
        verify_media(media.pk, self.actor.pk)
        self._like(media, 3)
        media.refresh_from_db()
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_LIKES, media.pk), 3)
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_HOT, media.pk), media.hot_value)
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk), media.hot_value)

    def test_reject_refunds_and_clears_everything(self):
        media = self._create_media()
        self._like(media, 4)
        self.assertEqual(UserMedia.objects.get(pk=self.user.pk).likes_sent, 4)
        reject_media(media.pk, self.actor.pk, 'not minesweeper related')
        media.refresh_from_db()
        self.assertEqual(media.status, MediaStatus.REJECTED)
        self.assertEqual(media.likes, 0)
        self.assertEqual(media.hot_value, 0)
        self.assertEqual(media.refunded_likes, 4)
        self.assertEqual(media.reject_reason, 'not minesweeper related')
        self.assertEqual(media.hot_value_updated_at, REFERENCE)
        self.assertEqual(UserMedia.objects.get(pk=self.user.pk).likes_sent, 0)
        self.assertFalse(MediaLikes.objects.filter(media=media).exists())
        for key in cache.MEDIA_RANK_KEYS:
            self.assertEqual(cache.cache.zcard(key), 0)
        with self.assertRaises(MediaServiceError):
            reject_media(media.pk, self.actor.pk)

    def test_reopen_reuses_same_row(self):
        media = self._create_media()
        self._like(media, 2)
        reject_media(media.pk, self.actor.pk, 'wrong')
        reopen_media(media.pk, self.actor.pk)
        media.refresh_from_db()
        self.assertEqual(media.status, MediaStatus.PENDING)
        self.assertIsNone(media.rejected_at)
        self.assertEqual(media.likes, 0)
        self.assertEqual(UserMedia.objects.get(pk=self.user.pk).likes_sent, 0)
        self.assertEqual(Media.objects.filter(format=MediaFormat.B_V, suffix=media.suffix).count(), 1)
        for key in cache.MEDIA_RANK_KEYS:
            self.assertEqual(cache.cache.zcard(key), 0)

    def test_hard_delete_refunds_and_rolls_back_zsets(self):
        media = self._create_media()
        self._like(media, 5)
        verify_media(media.pk, self.actor.pk)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_LIKES, media.pk), 5)
        self.assertTrue(hard_delete_media(media.pk, self.actor.pk))
        self.assertFalse(Media.objects.filter(pk=media.pk).exists())
        self.assertEqual(UserMedia.objects.get(pk=self.user.pk).likes_sent, 0)
        for key in cache.MEDIA_RANK_KEYS:
            self.assertEqual(cache.cache.zcard(key), 0)

    def test_hard_delete_rejects_non_verified(self):
        media = self._create_media()
        with self.assertRaises(MediaServiceError) as caught:
            hard_delete_media(media.pk, self.actor.pk)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertTrue(Media.objects.filter(pk=media.pk).exists())

    def test_late_sync_after_hard_delete_does_not_resurrect(self):
        media = self._create_media()
        verify_media(media.pk, self.actor.pk)
        hard_delete_media(media.pk, self.actor.pk)
        sync_media_scores(media.pk, self.user.pk)
        for key in cache.MEDIA_RANK_KEYS:
            self.assertEqual(cache.cache.zcard(key), 0)

    def test_create_media_uses_db_reference_without_lock(self):
        media = self._create_media()
        self.assertEqual(media.hot_value_updated_at, cache.read_db_hot_reference())
        self.assertFalse(cache.cache.exists('media:cache:lock'))

    def test_request_path_sync_enqueues_no_tasks_and_takes_no_lock(self):
        media = self._create_media()
        self._like(media, 2)
        verify_media(media.pk, self.actor.pk)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_LIKES, media.pk), 2)
        self.assertFalse(DBTaskResult.objects.filter(task_path__startswith='media.').exists())
        self.assertFalse(cache.cache.exists('media:cache:lock'))
        self.assertFalse(any('media' in item['task_path'] for item in TASK_CLEANUP_CONFIGS))

    def test_sync_media_scores_swallows_redis_errors(self):
        media = self._create_media()
        verify_media(media.pk, self.actor.pk)
        with patch.object(cache, 'set_media_scores', side_effect=RedisConnectionError('redis down')):
            with self.assertLogs('media', level='ERROR') as logs:
                result = like_media(self.user, media.pk)
        self.assertEqual(result['likes'], 1)
        media.refresh_from_db()
        self.assertEqual(media.likes, 1)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_LIKES, media.pk), 0)
        self.assertIn('ranking cache sync failed', logs.output[0])

    def test_reference_factor_scales_zset_scores(self):
        cache.set_hot_reference(TARGET)
        media = self._create_media()
        self._like(media, 2)
        verify_media(media.pk, self.actor.pk)
        media.refresh_from_db()
        factor = decay(REFERENCE, TARGET)
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_HOT, media.pk), media.hot_value * factor)
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk), media.hot_value * factor)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_LIKES, media.pk), 2)

    def test_check_reports_consistent_cache(self):
        media = self._create_media()
        self._like(media, 2)
        verify_media(media.pk, self.actor.pk)
        out = StringIO()
        call_command('refresh_media_rankings', '--check', stdout=out)
        self.assertIn('matches the database', out.getvalue())

    def test_check_uses_decay_between_db_and_redis_references(self):
        cache.set_hot_reference(TARGET)
        media = self._create_media()
        self._like(media, 2)
        verify_media(media.pk, self.actor.pk)
        out = StringIO()
        call_command('refresh_media_rankings', '--check', stdout=out)
        self.assertIn('T_db=2026-01-01T00:00:00+00:00 T_r=2026-02-01T00:00:00+00:00', out.getvalue())
        self.assertIn('matches the database', out.getvalue())

    def test_check_detects_score_drift(self):
        media = self._create_media()
        self._like(media, 2)
        verify_media(media.pk, self.actor.pk)
        cache.cache.zincrby(cache.MEDIA_RANK_LIKES, 1, media.pk)
        with self.assertRaises(CommandError) as caught:
            call_command('refresh_media_rankings', '--check', stdout=StringIO())
        self.assertIn('drift detected', str(caught.exception))
        self.assertIn('refresh_media_rankings', str(caught.exception))

    def test_check_detects_missing_anchor(self):
        cache.clear_rankings()
        with self.assertRaises(CommandError) as caught:
            call_command('refresh_media_rankings', '--check', stdout=StringIO())
        self.assertIn('anchor (T_r) is missing', str(caught.exception))

    def test_rebuild_only_repairs_drift_without_advancing_reference(self):
        media = self._create_media()
        self._like(media, 2)
        verify_media(media.pk, self.actor.pk)
        cache.cache.zincrby(cache.MEDIA_RANK_LIKES, 1, media.pk)
        call_command('refresh_media_rankings', '--rebuild-only', stdout=StringIO())
        media.refresh_from_db()
        self.assertEqual(media.hot_value_updated_at, REFERENCE)
        self.assertEqual(cache.get_hot_reference(), REFERENCE)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_LIKES, media.pk), 2)
        call_command('refresh_media_rankings', '--check', stdout=StringIO())

    def test_reference_advances_db_and_redis_bases(self):
        media = self._create_media()
        self._like(media, 2)
        verify_media(media.pk, self.actor.pk)
        media.refresh_from_db()
        old_hot = media.hot_value
        call_command('refresh_media_rankings', '--reference', TARGET.isoformat(), stdout=StringIO())
        media.refresh_from_db()
        self.assertEqual(media.hot_value_updated_at, TARGET)
        self.assertAlmostEqual(media.hot_value, old_hot * decay(REFERENCE, TARGET))
        self.assertEqual(cache.read_db_hot_reference(), TARGET)
        self.assertEqual(cache.get_hot_reference(), TARGET)
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_HOT, media.pk), media.hot_value)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_LIKES, media.pk), 2)
        call_command('refresh_media_rankings', '--check', stdout=StringIO())

    def test_reference_is_idempotent(self):
        media = self._create_media()
        self._like(media, 2)
        verify_media(media.pk, self.actor.pk)
        call_command('refresh_media_rankings', '--reference', TARGET.isoformat(), stdout=StringIO())
        media.refresh_from_db()
        hot_after_first = media.hot_value
        call_command('refresh_media_rankings', '--reference', TARGET.isoformat(), stdout=StringIO())
        media.refresh_from_db()
        self.assertEqual(media.hot_value, hot_after_first)
        self.assertEqual(cache.get_hot_reference(), TARGET)

    def test_reference_rejects_earlier_base(self):
        media = self._create_media()
        earlier = (REFERENCE - timedelta(days=1)).isoformat()
        with self.assertRaises(CommandError) as caught:
            call_command('refresh_media_rankings', '--reference', earlier, stdout=StringIO())
        self.assertIn('earlier than T_db', str(caught.exception))
        media.refresh_from_db()
        self.assertEqual(media.hot_value_updated_at, REFERENCE)
        self.assertEqual(cache.get_hot_reference(), REFERENCE)

    def test_rebuild_failure_keeps_db_authoritative(self):
        media = self._create_media()
        verify_media(media.pk, self.actor.pk)
        with patch.object(cache, 'rebuild_rankings', side_effect=RedisConnectionError('redis down')):
            with self.assertRaises(CommandError) as caught:
                call_command('refresh_media_rankings', '--reference', TARGET.isoformat(), stdout=StringIO())
        self.assertIn('T_db', str(caught.exception))
        self.assertIn('authoritative', str(caught.exception))
        media.refresh_from_db()
        self.assertEqual(media.hot_value_updated_at, TARGET)

    def test_degraded_submission_requires_title_on_verify(self):
        media = create_media(self.user, media_format=MediaFormat.B_V, suffix='BV1degraded001',
                             language='', metadata_pending=True)
        self.assertEqual(media.title, '')
        self.assertTrue(media.metadata_pending)
        with self.assertRaises(MediaServiceError) as caught:
            verify_media(media.pk, self.actor.pk)
        self.assertEqual(caught.exception.status_code, 400)
        media.refresh_from_db()
        self.assertEqual(media.status, MediaStatus.PENDING)
        corrected_at = timezone.now() - timedelta(days=3)
        verify_media(media.pk, self.actor.pk, title='manual title', created_at=corrected_at)
        media.refresh_from_db()
        self.assertEqual(media.status, MediaStatus.VERIFIED)
        self.assertEqual(media.title, 'manual title')
        self.assertEqual(media.created_at, corrected_at)
        self.assertFalse(media.metadata_pending)

    def test_normal_submission_keeps_fetched_metadata(self):
        media = create_media(self.user, media_format=MediaFormat.B_V, suffix='BV1normal0001',
                             title='auto title', created_at=timezone.now() - timedelta(days=1), language='')
        self.assertFalse(media.metadata_pending)
        verify_media(media.pk, self.actor.pk)
        media.refresh_from_db()
        self.assertEqual(media.title, 'auto title')

    def test_set_media_banned(self):
        self.assertTrue(set_media_banned(self.user.pk, True).banned)
        self.assertFalse(set_media_banned(self.user.pk, False).banned)

    def test_daily_like_limit_is_ten_successful_likes(self):
        UserProfile.objects.filter(pk=self.user.pk).update(date_joined=timezone.now() - timedelta(days=30))
        self.user.refresh_from_db()
        media = self._create_media()
        self._like(media, 10)
        self.assertEqual(UserMedia.objects.get(pk=self.user.pk).daily_likes, 10)
        with self.assertRaises(MediaServiceError) as caught:
            like_media(self.user, media.pk)
        self.assertEqual(caught.exception.status_code, 429)
        media.refresh_from_db()
        self.assertEqual(media.likes, 10)
        self.assertEqual(UserMedia.objects.get(pk=self.user.pk).daily_likes, 10)

    def test_daily_counter_resets_on_utc_date_change(self):
        media = self._create_media()
        yesterday = timezone.now().date() - timedelta(days=1)
        UserMedia.objects.create(user=self.user, daily_likes=10, daily_date=yesterday)
        result = like_media(self.user, media.pk)
        self.assertEqual(result['likes'], 1)
        profile = UserMedia.objects.get(pk=self.user.pk)
        self.assertNotEqual(profile.daily_date, yesterday)
        self.assertEqual(profile.daily_likes, 1)

    def test_failed_like_does_not_consume_daily_quota(self):
        media = self._create_media()
        self._like(media, 1)
        with self.assertRaises(MediaServiceError) as caught:
            like_media(self.user, media.pk + 1)
        self.assertEqual(caught.exception.status_code, 404)
        profile = UserMedia.objects.get(pk=self.user.pk)
        self.assertEqual(profile.daily_likes, 1)
        self.assertEqual(profile.likes_sent, 1)

    def test_refund_does_not_rewind_daily_counter(self):
        media = self._create_media()
        self._like(media, 3)
        reject_media(media.pk, self.actor.pk, 'wrong')
        profile = UserMedia.objects.get(pk=self.user.pk)
        self.assertEqual(profile.likes_sent, 0)
        self.assertEqual(profile.daily_likes, 3)
