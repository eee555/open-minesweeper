"""作品排行缓存回归：双基准折算、绝对分数写入与无锁重建。"""

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

    def _sync(self):
        services.sync_user_scores(self.user.pk)

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
        self._sync()
        self.assertEqual(self._zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk), 2.5)
        media.delete()
        self._sync()
        for key in cache.MEDIA_RANK_KEYS:
            self.assertIsNone(self._zscore(key, self.user.pk))

    def test_sync_scores_are_absolute_and_idempotent(self):
        self._media(1, hot=2.5, likes=3)
        self._sync()
        self._sync()
        self.assertEqual(self._zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk), 2.5)
        self.assertEqual(self._zscore(cache.MEDIA_RANK_USER_LIKES, self.user.pk), 3)

    def test_sync_uses_decay_between_db_and_redis_references(self):
        media = self._media(1, hot=2.0, likes=3)
        cache.set_hot_reference(TARGET)
        factor = decay(REFERENCE, TARGET)
        self._sync()
        media.refresh_from_db()
        self.assertEqual(media.hot_value_updated_at, REFERENCE)
        self.assertAlmostEqual(self._zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk), 2.0 * factor)

    def test_sync_ignores_pending_and_rejected_rows(self):
        self._media(1, hot=5.0, likes=9, status=MediaStatus.PENDING)
        self._sync()
        for key in cache.MEDIA_RANK_KEYS:
            self.assertEqual(cache.cache.zcard(key), 0)

    def test_author_score_refreshes_remaining_works_after_delete_and_like(self):
        first = self._media(1, hot=2.0, likes=5)
        second = self._media(2, hot=1.0, likes=7)
        self._sync()
        first.delete()
        self._sync()
        self.assertEqual(self._zscore(cache.MEDIA_RANK_USER_LIKES, self.user.pk), 7)
        second.likes = 8
        second.save(update_fields=['likes'])
        self._sync()
        self.assertEqual(self._zscore(cache.MEDIA_RANK_USER_LIKES, self.user.pk), 8)
        self.assertEqual(self._zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk), 1.0)

    def test_user_ranking_pagination_and_aggregates(self):
        cache.set_user_scores(self.user.pk, 14.0, 4, True)
        cache.set_user_scores(self.user.pk + 1, 2.0, 1, True)
        rows, total = cache.get_user_ranking('likes', 0, 1)
        self.assertEqual(total, 2)
        self.assertEqual(rows, [(self.user.pk, 14.0, 4.0)])
        rows, total = cache.get_user_ranking('likes', 1, 1)
        self.assertEqual(rows, [(self.user.pk + 1, 2.0, 1.0)])
        with self.assertRaises(ValueError):
            cache.get_user_ranking('unknown')

    def test_rebuild_rankings_only_verified(self):
        self._media(1, hot=2.0, likes=3)
        self._media(2, hot=5.0, likes=9, status=MediaStatus.PENDING)
        self._media(3, hot=5.0, likes=9, status=MediaStatus.REJECTED)
        cache.clear_rankings()
        cache.set_hot_reference(REFERENCE)
        self.assertEqual(cache.rebuild_rankings(), 1)
        self.assertEqual(self._zscore(cache.MEDIA_RANK_USER_LIKES, self.user.pk), 3)
        self.assertEqual(cache.get_hot_reference(), REFERENCE)

    def test_rebuild_rankings_scales_by_reference_factor(self):
        self._media(1, hot=2.0, likes=3)
        self.assertEqual(cache.rebuild_rankings(reference=TARGET), 1)
        self.assertAlmostEqual(self._zscore(cache.MEDIA_RANK_USER_HOT, self.user.pk), 2.0 * decay(REFERENCE, TARGET))
        self.assertEqual(cache.get_hot_reference(), TARGET)

    def test_rebuild_rankings_takes_no_cache_lock(self):
        self._media(1, hot=2.0, likes=3)
        with patch.object(cache.cache, 'lock', side_effect=AssertionError('rebuild must not take a lock')):
            self.assertEqual(cache.rebuild_rankings(), 1)
        self.assertFalse(cache.cache.exists('media:cache:lock'))

    def test_rebuild_rankings_rejects_nonpositive_batch_size(self):
        with self.assertRaises(ValueError):
            cache.rebuild_rankings(batch_size=0)

    def test_clear_rankings_deletes_three_fixed_keys(self):
        cache.set_user_scores(self.user.pk, 2.0, 3, True)
        cache.clear_rankings()
        for key in cache.MEDIA_CACHE_KEYS:
            self.assertFalse(cache.cache.exists(key))
