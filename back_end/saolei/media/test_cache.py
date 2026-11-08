"""作品排行缓存单测：按 DB 绝对值写入、衰减幂等与迟到回调；见 MEDIA_PLAN.md 第 12 节。"""

from datetime import datetime, timezone as datetime_timezone

from django.test import TestCase
from django.utils import timezone

from userprofile.models import UserProfile
from . import cache
from .models import Media
from .utils import MEDIA_HOT_DAILY_RETENTION, MediaFormat, MediaStatus

REFERENCE = datetime(2026, 1, 1, tzinfo=datetime_timezone.utc)
TARGET = datetime(2026, 2, 1, tzinfo=datetime_timezone.utc)


class MediaCacheTests(TestCase):
    def setUp(self):
        cache.clear_rankings()
        cache.set_hot_reference(REFERENCE)
        self.user = UserProfile.objects.create_user(username='media-cache', password='test-password')

    def tearDown(self):
        cache.clear_rankings()

    def _media(self, pk, hot=0.0, likes=0, base=REFERENCE, status=MediaStatus.VERIFIED):
        return Media.objects.create(
            pk=pk, user=self.user, title='', created_at=timezone.now(), format=MediaFormat.B_V,
            suffix=f'BV1cache{pk:06d}', status=status, hot_value=hot, likes=likes,
            hot_value_updated_at=base,
        )

    def _sync(self, pk):
        cache.sync_media_scores(pk, self.user.pk)

    def test_sync_and_clear_scores(self):
        media = self._media(1, hot=2.5, likes=3)
        self._sync(media.pk)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_HOT, 1), 2.5)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_LIKES, 1), 3)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk), 2.5)
        media.delete()
        self._sync(1)
        for key in (cache.MEDIA_RANK_HOT, cache.MEDIA_RANK_LIKES):
            self.assertIsNone(cache.cache.zscore(key, 1))
        for key in (cache.MEDIA_RANK_USER_HOT, cache.MEDIA_RANK_USER_LIKES):
            self.assertIsNone(cache.cache.zscore(key, self.user.pk))

    def test_sync_keeps_remaining_user_total(self):
        first = self._media(1, hot=2.0, likes=5)
        self._media(2, hot=1.0, likes=7)
        self._sync(first.pk)
        self._sync(2)
        first.delete()
        self._sync(1)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_LIKES, self.user.pk), 7)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk), 1.0)

    def test_sync_converts_db_base_to_current_anchor(self):
        media = self._media(1, hot=2.0, likes=3)
        cache.set_hot_reference(TARGET)
        factor = MEDIA_HOT_DAILY_RETENTION ** 31
        self._sync(media.pk)
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_HOT, 1), 2.0 * factor)
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk), 2.0 * factor)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_LIKES, 1), 3)

    def test_sync_is_consistent_across_anchor_publication(self):
        first = self._media(1, hot=2.0, likes=1)
        self._sync(first.pk)
        cache.refresh_hot_reference(TARGET)
        second = self._media(2, hot=2.0, likes=1)
        self._sync(second.pk)
        first_hot = cache.cache.zscore(cache.MEDIA_RANK_HOT, 1)
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_HOT, 2), first_hot)
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk), 2 * first_hot)

    def test_late_sync_after_hard_delete_does_not_resurrect(self):
        media = self._media(1, hot=2.0, likes=3)
        self._sync(media.pk)
        media.delete()
        self._sync(1)  # 迟到的投喂回调
        self.assertIsNone(cache.cache.zscore(cache.MEDIA_RANK_HOT, 1))
        self.assertIsNone(cache.cache.zscore(cache.MEDIA_RANK_LIKES, 1))
        self.assertIsNone(cache.cache.zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk))
        self.assertIsNone(cache.cache.zscore(cache.MEDIA_RANK_USER_LIKES, self.user.pk))

    def test_author_score_survives_out_of_order_delete_and_like(self):
        first = self._media(1, hot=2.0, likes=5)
        second = self._media(2, hot=1.0, likes=7)
        self._sync(first.pk)
        self._sync(second.pk)
        first.delete()
        second.likes = 8
        second.save(update_fields=['likes'])
        self._sync(second.pk)  # 新投喂回调先执行
        self._sync(1)  # 迟到的硬删除回调后执行，不能在事务外 ZREM 掉新分数
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_LIKES, self.user.pk), 8)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk), 1.0)

    def test_ranking_pagination(self):
        cache.cache.zadd(cache.MEDIA_RANK_LIKES, {1: 5, 2: 3, 3: 9})
        ids, total = cache.get_ranking(cache.MEDIA_RANK_LIKES, 0, 2)
        self.assertEqual(ids, [3, 1])
        self.assertEqual(total, 3)
        ids, total = cache.get_ranking(cache.MEDIA_RANK_LIKES, 2, 2)
        self.assertEqual(ids, [2])
        self.assertEqual(total, 3)

    def test_refresh_hot_reference_is_idempotent(self):
        cache.cache.zadd(cache.MEDIA_RANK_HOT, {1: 10.0})
        cache.cache.zadd(cache.MEDIA_RANK_USER_HOT, {10: 4.0})
        factor = MEDIA_HOT_DAILY_RETENTION ** 31
        self.assertTrue(cache.refresh_hot_reference(TARGET))
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_HOT, 1), 10.0 * factor)
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_HOT, 10), 4.0 * factor)
        self.assertEqual(cache.get_hot_reference(), TARGET)
        self.assertFalse(cache.refresh_hot_reference(TARGET))
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_HOT, 1), 10.0 * factor)

    def test_refresh_does_not_touch_likes_zsets(self):
        cache.cache.zadd(cache.MEDIA_RANK_LIKES, {1: 8})
        cache.cache.zadd(cache.MEDIA_RANK_USER_LIKES, {10: 8})
        cache.refresh_hot_reference(TARGET)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_LIKES, 1), 8)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_LIKES, 10), 8)
