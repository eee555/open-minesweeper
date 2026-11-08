"""作品服务层单测：投稿、投喂、审核、驳回清零、恢复、硬删除与刷新；见 MEDIA_PLAN.md 第 12 节。"""

from datetime import datetime, timedelta, timezone as datetime_timezone

from django.test import TestCase
from django.utils import timezone

from userprofile.models import UserProfile
from . import cache
from .models import Media, MediaLikes, UserMedia
from .services import (
    create_media, get_balance, hard_delete_media, like_media, MediaServiceError,
    refresh_hot_reference, reject_media, reopen_media, set_media_banned, verify_media,
)
from .utils import MediaFormat, MediaStatus

REFERENCE = datetime(2026, 1, 1, tzinfo=datetime_timezone.utc)
NEXT_REFERENCE = datetime(2026, 2, 1, tzinfo=datetime_timezone.utc)


class MediaServiceTests(TestCase):
    def setUp(self):
        cache.clear_rankings()
        cache.set_hot_reference(REFERENCE)
        self.user = UserProfile.objects.create_user(username='media-service', password='test-password')
        UserProfile.objects.filter(pk=self.user.pk).update(date_joined=timezone.now() - timedelta(days=10))
        self.user.refresh_from_db()
        self.actor = self.user

    def tearDown(self):
        cache.clear_rankings()

    def _create_media(self, suffix='BV1xx411c7mD'):
        return create_media(
            self.user, media_format=MediaFormat.B_V, suffix=suffix, title='test title',
            created_at=timezone.now() - timedelta(days=1), language='',
        )

    def test_balance_and_duplicate_submission(self):
        self.assertGreaterEqual(get_balance(self.user), 9)
        self._create_media()
        with self.assertRaises(MediaServiceError) as caught:
            self._create_media()
        self.assertEqual(caught.exception.status_code, 409)

    def test_like_pending_only_writes_db(self):
        media = self._create_media()
        result = like_media(self.user, media.pk, 3)
        self.assertEqual(result['likes'], 3)
        self.assertEqual(result['status'], MediaStatus.PENDING)
        media.refresh_from_db()
        self.assertEqual(media.likes, 3)
        self.assertGreater(media.hot_value, 3)
        self.assertEqual(MediaLikes.objects.get(user=self.user, media=media).likes, 3)
        self.assertEqual(UserMedia.objects.get(pk=self.user.pk).likes_sent, 3)
        self.assertEqual(cache.cache.zcard(cache.MEDIA_RANK_LIKES), 0)

    def test_verify_fills_four_zsets(self):
        media = self._create_media()
        like_media(self.user, media.pk, 2)
        with self.captureOnCommitCallbacks(execute=True):
            verify_media(media.pk, self.actor.pk)
        media.refresh_from_db()
        self.assertEqual(media.status, MediaStatus.VERIFIED)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_LIKES, media.pk), 2)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_LIKES, self.user.pk), 2)
        self.assertGreater(cache.cache.zscore(cache.MEDIA_RANK_HOT, media.pk), 2)
        with self.assertRaises(MediaServiceError):
            verify_media(media.pk, self.actor.pk)

    def test_reject_refunds_and_clears_everything(self):
        media = self._create_media()
        like_media(self.user, media.pk, 4)
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
        self.assertEqual(cache.cache.zcard(cache.MEDIA_RANK_LIKES), 0)
        with self.assertRaises(MediaServiceError):
            reject_media(media.pk, self.actor.pk)

    def test_reopen_reuses_same_row(self):
        media = self._create_media()
        like_media(self.user, media.pk, 2)
        reject_media(media.pk, self.actor.pk, 'wrong')
        reopen_media(media.pk, self.actor.pk)
        media.refresh_from_db()
        self.assertEqual(media.status, MediaStatus.PENDING)
        self.assertIsNone(media.rejected_at)
        self.assertEqual(media.likes, 0)
        self.assertEqual(UserMedia.objects.get(pk=self.user.pk).likes_sent, 0)
        self.assertEqual(Media.objects.filter(format=MediaFormat.B_V, suffix=media.suffix).count(), 1)

    def test_hard_delete_refunds_and_rolls_back_zsets(self):
        media = self._create_media()
        like_media(self.user, media.pk, 5)
        with self.captureOnCommitCallbacks(execute=True):
            verify_media(media.pk, self.actor.pk)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_LIKES, media.pk), 5)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertTrue(hard_delete_media(media.pk, self.actor.pk))
        self.assertFalse(Media.objects.filter(pk=media.pk).exists())
        self.assertEqual(UserMedia.objects.get(pk=self.user.pk).likes_sent, 0)
        self.assertIsNone(cache.cache.zscore(cache.MEDIA_RANK_LIKES, media.pk))
        self.assertIsNone(cache.cache.zscore(cache.MEDIA_RANK_HOT, media.pk))
        self.assertIsNone(cache.cache.zscore(cache.MEDIA_RANK_USER_LIKES, self.user.pk))
        self.assertIsNone(cache.cache.zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk))

    def test_hard_delete_rejects_non_verified(self):
        media = self._create_media()
        with self.assertRaises(MediaServiceError) as caught:
            hard_delete_media(media.pk, self.actor.pk)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertTrue(Media.objects.filter(pk=media.pk).exists())

    def test_refresh_hot_reference_folds_db(self):
        media = self._create_media()
        like_media(self.user, media.pk, 2)
        media.refresh_from_db()
        old_hot = media.hot_value
        refresh_hot_reference(NEXT_REFERENCE)
        media.refresh_from_db()
        self.assertEqual(media.hot_value_updated_at, NEXT_REFERENCE)
        self.assertLess(media.hot_value, old_hot)
        self.assertEqual(cache.get_hot_reference(), NEXT_REFERENCE)

    def test_rebuild_rankings_only_verified(self):
        verified = self._create_media('BV1verified0001')
        like_media(self.user, verified.pk, 3)
        with self.captureOnCommitCallbacks(execute=True):
            verify_media(verified.pk, self.actor.pk)
        self._create_media('BV1pending00001')
        rejected = self._create_media('BV1rejected001')
        reject_media(rejected.pk, self.actor.pk)
        cache.clear_rankings()
        count = cache.rebuild_rankings()
        self.assertEqual(count, 1)
        self.assertEqual(cache.cache.zcard(cache.MEDIA_RANK_LIKES), 1)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_LIKES, verified.pk), 3)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_LIKES, self.user.pk), 3)

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
        with self.captureOnCommitCallbacks(execute=True):
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
        with self.captureOnCommitCallbacks(execute=True):
            verify_media(media.pk, self.actor.pk)
        media.refresh_from_db()
        self.assertEqual(media.title, 'auto title')

    def test_set_media_banned(self):
        self.assertTrue(set_media_banned(self.user.pk, True).banned)
        self.assertFalse(set_media_banned(self.user.pk, False).banned)
