"""作品服务层单测：投稿、投喂、审核、驳回清零、恢复、硬删除与刷新；见 MEDIA_PLAN.md 第 12 节。"""

from datetime import datetime, timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from userprofile.models import UserProfile
from . import cache
from .models import Media, MediaLikes, UserMedia
from .services import (
    create_media, get_balance, hard_delete_media, like_media, MediaServiceError,
    refresh_hot_reference, reject_media, reopen_media, set_media_banned, verify_media,
)
from .utils import decay, MediaFormat, MediaStatus

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
        self.assertEqual(cache.cache.zcard(cache.MEDIA_RANK_LIKES), 0)

    def test_verify_fills_four_zsets(self):
        media = self._create_media()
        self._like(media, 2)
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
        self.assertEqual(cache.cache.zcard(cache.MEDIA_RANK_LIKES), 0)
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

    def test_hard_delete_refunds_and_rolls_back_zsets(self):
        media = self._create_media()
        self._like(media, 5)
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
        self._like(media, 2)
        media.refresh_from_db()
        old_hot = media.hot_value
        refresh_hot_reference(NEXT_REFERENCE)
        media.refresh_from_db()
        self.assertEqual(media.hot_value_updated_at, NEXT_REFERENCE)
        self.assertLess(media.hot_value, old_hot)
        self.assertEqual(cache.get_hot_reference(), NEXT_REFERENCE)

    def test_like_between_db_fold_and_anchor_publish_is_consistent(self):
        """刷新窗口内投喂不丢热度，DB 与四个 zset 仍使用可对齐的时间基准。"""
        media = self._create_media()
        with self.captureOnCommitCallbacks(execute=True):
            verify_media(media.pk, self.actor.pk)
            self._like(media, 2)
        media.refresh_from_db()
        old_hot = media.hot_value
        factor = decay(REFERENCE, NEXT_REFERENCE)
        original_refresh = cache.refresh_hot_reference

        def refresh_after_like(at_time=None):
            like_media(self.user, media.pk)  # DB 换算已提交、anchor 尚未发布
            return original_refresh(at_time)

        with patch.object(cache, 'refresh_hot_reference', side_effect=refresh_after_like):
            with self.captureOnCommitCallbacks(execute=True):
                refresh_hot_reference(NEXT_REFERENCE)
        media.refresh_from_db()
        self.assertEqual(media.hot_value_updated_at, NEXT_REFERENCE)
        self.assertGreater(media.hot_value, old_hot * factor)
        self.assertEqual(cache.get_hot_reference(), NEXT_REFERENCE)
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_HOT, media.pk), media.hot_value)
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk), media.hot_value)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_LIKES, media.pk), 3)

    def test_media_created_during_refresh_converges_to_new_reference(self):
        """窗口内按旧 anchor 新建的作品由二次换算收敛，避免 DB 排序混用基准。"""
        created_ids = []
        original_refresh = cache.refresh_hot_reference

        def create_then_refresh(at_time=None):
            created_ids.append(self._create_media('BV1window00001').pk)
            return original_refresh(at_time)

        with patch.object(cache, 'refresh_hot_reference', side_effect=create_then_refresh):
            refresh_hot_reference(NEXT_REFERENCE)
        created = Media.objects.get(pk=created_ids[0])
        self.assertEqual(created.hot_value_updated_at, NEXT_REFERENCE)
        self.assertEqual(cache.get_hot_reference(), NEXT_REFERENCE)

    def test_rejected_media_stays_cleared_after_refresh(self):
        media = self._create_media()
        self._like(media, 2)
        reject_media(media.pk, self.actor.pk, 'wrong')
        refresh_hot_reference(NEXT_REFERENCE)
        media.refresh_from_db()
        self.assertEqual(media.likes, 0)
        self.assertEqual(media.hot_value, 0)
        self.assertFalse(MediaLikes.objects.filter(media=media).exists())

    def test_create_media_validates_base_after_insert(self):
        """读到旧 anchor 后锚点推进：创建完成后必须把该行换算到新基准。"""
        anchors = iter([REFERENCE, NEXT_REFERENCE])
        with patch.object(cache, 'get_hot_reference', side_effect=lambda: next(anchors)):
            media = self._create_media('BV1basevalid001')
        self.assertEqual(Media.objects.get(pk=media.pk).hot_value_updated_at, NEXT_REFERENCE)

    def test_late_feed_callback_after_hard_delete_does_not_resurrect(self):
        media = self._create_media()
        with self.captureOnCommitCallbacks(execute=True):
            verify_media(media.pk, self.actor.pk)
        with self.captureOnCommitCallbacks(execute=True):
            hard_delete_media(media.pk, self.actor.pk)
        cache.sync_media_scores(media.pk, self.user.pk)  # 迟到的投喂回调
        self.assertIsNone(cache.cache.zscore(cache.MEDIA_RANK_LIKES, media.pk))
        self.assertIsNone(cache.cache.zscore(cache.MEDIA_RANK_HOT, media.pk))
        self.assertIsNone(cache.cache.zscore(cache.MEDIA_RANK_USER_LIKES, self.user.pk))

    def test_rebuild_is_reconciled_by_late_callback(self):
        """重建快照期间提交的投喂：迟到回调按 DB 绝对值补齐，既不丢也不重复。"""
        media = self._create_media()
        with self.captureOnCommitCallbacks(execute=True):
            verify_media(media.pk, self.actor.pk)
        original_decay = cache.decay
        state = {'done': False}

        def decay_after_write(base, at):
            if not state['done']:
                state['done'] = True
                like_media(self.user, media.pk)
            return original_decay(base, at)

        with patch.object(cache, 'decay', side_effect=decay_after_write):
            cache.rebuild_rankings()
        media.refresh_from_db()
        cache.sync_media_scores(media.pk, self.user.pk)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_LIKES, media.pk), media.likes)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_LIKES, self.user.pk), media.likes)
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_HOT, media.pk), media.hot_value)

    def test_rebuild_holds_cache_lock(self):
        with patch.object(cache, 'media_cache_lock', wraps=cache.media_cache_lock) as locked:
            cache.rebuild_rankings()
        locked.assert_called_once_with()

    def test_rebuild_rankings_only_verified(self):
        verified = self._create_media('BV1verified0001')
        self._like(verified, 3)
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

    def test_rebuild_rankings_normalizes_mixed_row_bases(self):
        first = self._create_media('BV1mixed000001')
        second = self._create_media('BV1mixed000002')
        older = REFERENCE - timedelta(days=10)
        Media.objects.filter(pk=first.pk).update(hot_value=2.0, status=MediaStatus.VERIFIED)
        Media.objects.filter(pk=second.pk).update(
            hot_value=3.0, status=MediaStatus.VERIFIED, hot_value_updated_at=older,
        )
        cache.clear_rankings()
        self.assertEqual(cache.rebuild_rankings(), 2)
        self.assertEqual(cache.get_hot_reference(), older)
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_HOT, first.pk), 2.0 * decay(REFERENCE, older))
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_HOT, second.pk), 3.0)

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
