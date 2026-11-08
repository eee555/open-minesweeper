"""作品排行缓存单测：增量、分页、幂等衰减与回退；见 MEDIA_PLAN.md 第 12 节。"""

from datetime import datetime, timezone as datetime_timezone

from django.test import SimpleTestCase

from . import cache
from .utils import MEDIA_HOT_DAILY_RETENTION


class MediaCacheTests(SimpleTestCase):
    def setUp(self):
        cache.clear_rankings()
        cache.set_hot_reference(datetime(2026, 1, 1, tzinfo=datetime_timezone.utc))

    def tearDown(self):
        cache.clear_rankings()

    def test_add_and_remove_scores(self):
        cache.add_media_scores(1, 10, 2.5, 3)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_HOT, 1), 2.5)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_LIKES, 1), 3)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_HOT, 10), 2.5)
        cache.remove_media_scores(1, 10, 2.5, 3)
        self.assertIsNone(cache.cache.zscore(cache.MEDIA_RANK_HOT, 1))
        self.assertIsNone(cache.cache.zscore(cache.MEDIA_RANK_LIKES, 1))
        self.assertIsNone(cache.cache.zscore(cache.MEDIA_RANK_USER_HOT, 10))
        self.assertIsNone(cache.cache.zscore(cache.MEDIA_RANK_USER_LIKES, 10))

    def test_remove_scores_keeps_remaining_user_total(self):
        cache.add_media_scores(1, 10, 2.0, 5)
        cache.add_media_scores(2, 10, 1.0, 7)
        cache.remove_media_scores(1, 10, 2.0, 5)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_LIKES, 10), 7)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_HOT, 10), 1.0)

    def test_add_scores_converts_db_base_to_current_anchor(self):
        base = datetime(2026, 1, 1, tzinfo=datetime_timezone.utc)
        target = datetime(2026, 2, 1, tzinfo=datetime_timezone.utc)
        factor = MEDIA_HOT_DAILY_RETENTION ** 31
        cache.set_hot_reference(target)
        cache.add_media_scores(1, 10, 2.0, 3, base)
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_HOT, 1), 2.0 * factor)
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_HOT, 10), 2.0 * factor)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_LIKES, 1), 3)

    def test_increments_are_consistent_across_anchor_publication(self):
        base = datetime(2026, 1, 1, tzinfo=datetime_timezone.utc)
        target = datetime(2026, 2, 1, tzinfo=datetime_timezone.utc)
        cache.set_hot_reference(base)
        cache.add_media_scores(1, 10, 2.0, 1, base)  # 刷新前按旧 anchor 写入
        cache.refresh_hot_reference(target)
        cache.add_media_scores(2, 10, 2.0, 1, base)  # 刷新后仍按 DB 行基准折算
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_HOT, 1), cache.cache.zscore(cache.MEDIA_RANK_HOT, 2))
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_HOT, 10), 2 * cache.cache.zscore(cache.MEDIA_RANK_HOT, 1))

    def test_remove_scores_after_anchor_change_uses_actual_zset_score(self):
        base = datetime(2026, 1, 1, tzinfo=datetime_timezone.utc)
        target = datetime(2026, 2, 1, tzinfo=datetime_timezone.utc)
        cache.set_hot_reference(base)
        cache.add_media_scores(1, 10, 2.0, 5, base)
        cache.refresh_hot_reference(target)
        cache.remove_media_scores(1, 10, 2.0, 5, base)
        self.assertIsNone(cache.cache.zscore(cache.MEDIA_RANK_HOT, 1))
        self.assertIsNone(cache.cache.zscore(cache.MEDIA_RANK_USER_HOT, 10))
        self.assertIsNone(cache.cache.zscore(cache.MEDIA_RANK_USER_LIKES, 10))

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
        target = datetime(2026, 2, 1, tzinfo=datetime_timezone.utc)
        factor = MEDIA_HOT_DAILY_RETENTION ** 31
        self.assertTrue(cache.refresh_hot_reference(target))
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_HOT, 1), 10.0 * factor)
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_HOT, 10), 4.0 * factor)
        self.assertEqual(cache.get_hot_reference(), target)
        self.assertFalse(cache.refresh_hot_reference(target))
        self.assertAlmostEqual(cache.cache.zscore(cache.MEDIA_RANK_HOT, 1), 10.0 * factor)

    def test_refresh_does_not_touch_likes_zsets(self):
        cache.cache.zadd(cache.MEDIA_RANK_LIKES, {1: 8})
        cache.cache.zadd(cache.MEDIA_RANK_USER_LIKES, {10: 8})
        cache.refresh_hot_reference(datetime(2026, 2, 1, tzinfo=datetime_timezone.utc))
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_LIKES, 1), 8)
        self.assertEqual(cache.cache.zscore(cache.MEDIA_RANK_USER_LIKES, 10), 8)
