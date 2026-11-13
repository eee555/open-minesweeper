"""作品排行缓存单测：双基准折算、绝对分数写入与无锁重建；见 MEDIA_PLAN.md 第 12 节、附录 A。"""

from datetime import datetime, timezone as datetime_timezone
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from userprofile.models import UserProfile
from . import cache, services
from .models import Media
from .utils import decay, MediaFormat, MediaStatus

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
        services.sync_media_scores(pk, self.user.pk)

    def _zscore(self, key, member):
        return cache.cache.zscore(key, member)

    def test_default_hot_reference_is_month_start(self):
        self.assertEqual(
            cache.default_hot_reference(datetime(2026, 11, 10, 12, tzinfo=datetime_timezone.utc)),
            datetime(2026, 11, 1, tzinfo=datetime_timezone.utc),
        )

    def test_db_and_redis_references_are_independent(self):
        self._media(1, hot=2.0, likes=3)
        self.assertEqual(cache.read_db_hot_reference(), REFERENCE)
        self.assertEqual(cache.get_hot_reference(), REFERENCE)
        self.assertAlmostEqual(cache.reference_factor(), 1.0)
        cache.set_hot_reference(TARGET)
        self.assertEqual(cache.read_db_hot_reference(), REFERENCE)
        self.assertEqual(cache.get_hot_reference(), TARGET)
        self.assertAlmostEqual(cache.reference_factor(), decay(REFERENCE, TARGET))

    def test_missing_redis_reference_is_initialized_from_db(self):
        self._media(1, hot=2.0, likes=3)
        cache.clear_rankings()
        self.assertIsNone(cache.read_hot_reference())
        self.assertEqual(cache.get_hot_reference(), cache.read_db_hot_reference())
        self.assertEqual(cache.read_hot_reference(), REFERENCE)

    def test_sync_and_clear_scores(self):
        media = self._media(1, hot=2.5, likes=3)
        self._sync(media.pk)
        self.assertEqual(self._zscore(cache.MEDIA_RANK_HOT, 1), 2.5)
        self.assertEqual(self._zscore(cache.MEDIA_RANK_LIKES, 1), 3)
        self.assertEqual(self._zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk), 2.5)
        media.delete()
        self._sync(1)
        for key in cache.MEDIA_RANK_KEYS:
            member = 1 if key in (cache.MEDIA_RANK_HOT, cache.MEDIA_RANK_LIKES) else self.user.pk
            self.assertIsNone(self._zscore(key, member))

    def test_sync_keeps_remaining_user_total(self):
        first = self._media(1, hot=2.0, likes=5)
        self._media(2, hot=1.0, likes=7)
        self._sync(first.pk)
        self._sync(2)
        first.delete()
        self._sync(1)
        self.assertEqual(self._zscore(cache.MEDIA_RANK_USER_LIKES, self.user.pk), 7)
        self.assertEqual(self._zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk), 1.0)

    def test_sync_scores_are_absolute_and_idempotent(self):
        self._media(1, hot=2.5, likes=3)
        self._sync(1)
        self._sync(1)
        self.assertEqual(self._zscore(cache.MEDIA_RANK_HOT, 1), 2.5)
        self.assertEqual(self._zscore(cache.MEDIA_RANK_LIKES, 1), 3)
        self.assertEqual(self._zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk), 2.5)
        self.assertEqual(self._zscore(cache.MEDIA_RANK_USER_LIKES, self.user.pk), 3)

    def test_sync_uses_decay_between_db_and_redis_references(self):
        media = self._media(1, hot=2.0, likes=3)
        cache.set_hot_reference(TARGET)
        factor = decay(REFERENCE, TARGET)
        self._sync(media.pk)
        media.refresh_from_db()
        self.assertEqual(media.hot_value_updated_at, REFERENCE)
        self.assertAlmostEqual(self._zscore(cache.MEDIA_RANK_HOT, 1), 2.0 * factor)
        self.assertAlmostEqual(self._zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk), 2.0 * factor)
        self.assertEqual(self._zscore(cache.MEDIA_RANK_LIKES, 1), 3)

    def test_sync_ignores_pending_and_rejected_rows(self):
        self._media(1, hot=5.0, likes=9, status=MediaStatus.PENDING)
        self._sync(1)
        for key in cache.MEDIA_RANK_KEYS:
            self.assertEqual(cache.cache.zcard(key), 0)

    def test_late_sync_after_hard_delete_does_not_resurrect(self):
        media = self._media(1, hot=2.0, likes=3)
        self._sync(media.pk)
        media.delete()
        self._sync(1)
        self.assertIsNone(self._zscore(cache.MEDIA_RANK_HOT, 1))
        self.assertIsNone(self._zscore(cache.MEDIA_RANK_LIKES, 1))
        self.assertIsNone(self._zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk))
        self.assertIsNone(self._zscore(cache.MEDIA_RANK_USER_LIKES, self.user.pk))

    def test_author_score_survives_out_of_order_delete_and_like(self):
        first = self._media(1, hot=2.0, likes=5)
        second = self._media(2, hot=1.0, likes=7)
        self._sync(first.pk)
        self._sync(second.pk)
        first.delete()
        second.likes = 8
        second.save(update_fields=['likes'])
        self._sync(second.pk)
        self._sync(1)
        self.assertEqual(self._zscore(cache.MEDIA_RANK_USER_LIKES, self.user.pk), 8)
        self.assertEqual(self._zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk), 1.0)

    def test_ranking_pagination_and_user_aggregates(self):
        cache.set_media_scores(1, self.user.pk, 5.0, 3, 5.0, 3, True)
        cache.set_media_scores(2, self.user.pk, 9.0, 1, 14.0, 4, True)
        ids, total = cache.get_ranking(cache.MEDIA_RANK_HOT, 0, 1)
        self.assertEqual(ids, [2])
        self.assertEqual(total, 2)
        ids, total = cache.get_ranking(cache.MEDIA_RANK_HOT, 1, 1)
        self.assertEqual(ids, [1])
        rows, total = cache.get_user_ranking('likes')
        self.assertEqual(total, 1)
        self.assertEqual(rows[0][0], self.user.pk)
        self.assertAlmostEqual(rows[0][1], 14.0)
        self.assertAlmostEqual(rows[0][2], 4.0)
        with self.assertRaises(ValueError):
            cache.get_user_ranking('unknown')

    def test_rebuild_rankings_only_verified(self):
        verified = self._media(1, hot=2.0, likes=3)
        self._media(2, hot=5.0, likes=9, status=MediaStatus.PENDING)
        self._media(3, hot=5.0, likes=9, status=MediaStatus.REJECTED)
        cache.clear_rankings()
        cache.set_hot_reference(REFERENCE)
        self.assertEqual(cache.rebuild_rankings(), 1)
        self.assertEqual(cache.cache.zcard(cache.MEDIA_RANK_LIKES), 1)
        self.assertEqual(self._zscore(cache.MEDIA_RANK_LIKES, verified.pk), 3)
        self.assertEqual(self._zscore(cache.MEDIA_RANK_HOT, verified.pk), 2.0)
        self.assertEqual(self._zscore(cache.MEDIA_RANK_USER_LIKES, self.user.pk), 3)
        self.assertEqual(cache.get_hot_reference(), REFERENCE)

    def test_rebuild_rankings_scales_by_reference_factor(self):
        self._media(1, hot=2.0, likes=3)
        self.assertEqual(cache.rebuild_rankings(reference=TARGET), 1)
        self.assertAlmostEqual(self._zscore(cache.MEDIA_RANK_HOT, 1), 2.0 * decay(REFERENCE, TARGET))
        self.assertEqual(self._zscore(cache.MEDIA_RANK_LIKES, 1), 3)
        self.assertEqual(cache.get_hot_reference(), TARGET)

    def test_rebuild_rankings_takes_no_cache_lock(self):
        self._media(1, hot=2.0, likes=3)
        with patch.object(cache.cache, 'lock', side_effect=AssertionError('rebuild must not take a lock')):
            self.assertEqual(cache.rebuild_rankings(), 1)
        self.assertFalse(cache.cache.exists('media:cache:lock'))

    def test_rebuild_rankings_rejects_nonpositive_batch_size(self):
        with self.assertRaises(ValueError):
            cache.rebuild_rankings(batch_size=0)

    def test_clear_rankings_deletes_five_fixed_keys(self):
        cache.set_media_scores(1, self.user.pk, 2.0, 3, 2.0, 3, True)
        cache.clear_rankings()
        for key in cache.MEDIA_CACHE_KEYS:
            self.assertFalse(cache.cache.exists(key))
