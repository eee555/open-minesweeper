from datetime import timedelta
from io import StringIO
import json
from unittest.mock import patch

from django.core.management import call_command
from django.test import override_settings, SimpleTestCase, TestCase
from django.utils import timezone

from config.text_choices import MS_TextChoices
from msuser.models import UserMS
from userprofile.models import UserProfile
from videomanager.models import ExpandVideoModel, VideoModel
from .cache import SpeedRankingCache
from .services import best_candidate
from .utils import encode_zset_score, is_better, MAX_RECORD_UNITS, RANK_STATS, RANKING_NAMES, SCORE_TIME_FACTOR, TIME_STATS, TOTAL_PARTS
from ..cache import cache
from ..pb.cache import PBRankingCache
from ..services import add_videos_to_speed_ranks, remove_videos_from_speed_ranks


class StrictNgScoreTests(SimpleTestCase):
    def test_score_precision_and_admission_boundaries(self):
        for stat in RANK_STATS:
            with self.subTest(stat=stat):
                maximum = MAX_RECORD_UNITS * (3 if stat in TOTAL_PARTS else 1)
                value = maximum if stat in TIME_STATS else maximum / 10000
                for upload in (0, SCORE_TIME_FACTOR - 1):
                    encoded = encode_zset_score(stat, value, upload * 60_000_000)
                    self.assertLess(abs(encoded), 2 ** 53)
                    self.assertEqual(int(float(encoded)), encoded)
                step = 1 if stat in TIME_STATS else 0.0001
                better, worse = (value - step, value) if stat in TIME_STATS else (value, value - step)
                self.assertLess(encode_zset_score(stat, better, (SCORE_TIME_FACTOR - 1) * 60_000_000), encode_zset_score(stat, worse, 0))
                for invalid in (-1, value + step / 10, float('inf'), float('nan')):
                    self.assertIsNone(encode_zset_score(stat, invalid, 0))
        self.assertEqual(encode_zset_score('bb', 1.23445, 0), -12345 * SCORE_TIME_FACTOR)
        self.assertTrue(is_better('bb', {'value': 1.23442, 'upload': 2}, {'bb': 1.23441, '_uploads': {'bb': 1}}))


@override_settings(RATELIMIT_ENABLE=False)
class StrictNgRankingTests(TestCase):
    def setUp(self):
        pb = PBRankingCache()
        pb.flush()
        self.addCleanup(pb.flush)
        for ranking_name in RANKING_NAMES:
            ranking = SpeedRankingCache(ranking_name, stats=RANK_STATS)
            ranking.flush()
            self.addCleanup(ranking.flush)
        self.user = self.create_user('strict-ng')

    def create_user(self, name):
        return UserProfile.objects.create_user(username=name, email=f'{name}@example.com', userms=UserMS.objects.create())

    def create_video(self, **kwargs):
        fields = {'player': self.user, 'video': ExpandVideoModel.objects.create(identifier='strict-ng'), 'file': 'videos/strict-ng.evf', 'software': 'e', 'state': MS_TextChoices.State.OFFICIAL, 'level': 'b', 'mode': MS_TextChoices.Mode.QWC, 'bv': 4, 'timems': 1000, 'right_ce': 0}
        fields.update(kwargs)
        with self.captureOnCommitCallbacks(execute=True):
            return VideoModel.objects.create(**fields)

    def save_video(self, video, **fields):
        for field, value in fields.items():
            setattr(video, field, value)
        with self.captureOnCommitCallbacks(execute=True):
            video.save(update_fields=fields)

    def record(self, ranking_name='strict_ng', player=None):
        response = self.client.get(f'/api/speedranking/strict_ng/player/{(player or self.user).id}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()[ranking_name]

    def test_only_strict_ng_videos_with_non_null_bv_are_admitted(self):
        standard = self.create_video(mode=MS_TextChoices.Mode.STD)
        null_bv = self.create_video(bv=None)
        low_bv = self.create_video(bv=1, timems=2000, right_ce=1, state=MS_TextChoices.State.IDENTIFIER)
        self.assertIsNone(self.record()['bt'])
        self.assertIsNone(self.record('strict_ng_nf')['bt'])
        self.save_video(standard, mode=MS_TextChoices.Mode.QWC, bv=2, timems=1500)
        self.assertEqual(self.record()['bt_id'], standard.id)
        self.assertEqual(self.record('strict_ng_nf')['bt_id'], standard.id)
        self.save_video(null_bv, bv=1, timems=1200)
        self.assertEqual(self.record()['bt_id'], null_bv.id)
        # No lower bound: bv=1 qualifies even though saolei.wang requires bv >= 2.
        self.save_video(low_bv, state=MS_TextChoices.State.OFFICIAL, timems=1100, right_ce=0)
        self.assertEqual(self.record()['bt_id'], low_bv.id)
        self.assertEqual(self.record('strict_ng_nf')['bt_id'], low_bv.id)
        self.save_video(low_bv, state=MS_TextChoices.State.IDENTIFIER)
        self.assertEqual(self.record()['bt_id'], null_bv.id)
        self.save_video(low_bv, state=MS_TextChoices.State.OFFICIAL, ongoing_tournament=True)
        self.assertEqual(self.record()['bt_id'], null_bv.id)

    def test_nf_is_a_separate_ranking_but_the_standard_one_includes_it(self):
        flagged = self.create_video(timems=2000, right_ce=1)
        nf = self.create_video(timems=3000, right_ce=0)
        self.assertEqual(self.record()['bt_id'], flagged.id)
        self.assertEqual(self.record('strict_ng_nf')['bt_id'], nf.id)
        for ranking_name in RANKING_NAMES:
            self.assertEqual(self.record(ranking_name)['ranks']['bt'], 1)
        self.assertEqual(self.client.get('/api/speedranking/strict_ng/rank', {'ranking_name': 'strict_ng_nf', 'stat': 'bt'}).json()['count'], 1)

    def test_three_levels_totals_and_missing_parts(self):
        self.create_video(bv=1, timems=1000, right_ce=None)
        self.assertEqual(self.record()['bt'], 1000)
        self.assertEqual(self.record()['bb'], 1)
        self.assertEqual(self.record()['sumt'], 1000 + 2 * 999999)
        self.assertEqual(self.record()['sumb'], 1)
        self.assertIsNone(self.record('strict_ng_nf')['bt'])
        self.create_video(level='i', bv=10, timems=10000)
        self.create_video(level='e', bv=100, timems=100000)
        self.assertEqual(self.record()['sumt'], 111000)
        self.assertEqual(self.record()['sumb'], 3)

    def test_upload_time_breaks_ties(self):
        older = self.create_video(bv=8, timems=2000)
        self.save_video(older, upload_time=timezone.now() - timedelta(minutes=2))
        newer = self.create_video(bv=8, timems=2000)
        self.assertEqual(self.record()['bb_id'], older.id)
        self.save_video(newer, upload_time=older.upload_time - timedelta(days=1))
        self.assertEqual(self.record()['bb_id'], newer.id)
        self.assertEqual(best_candidate(self.user.id, 'strict_ng', 'bb')['id'], newer.id)

    def test_worsening_and_deletion_backfill_only_held_records(self):
        first = self.create_video(timems=1000)
        backup = self.create_video(timems=2000)
        with patch('speedranking.strict_ng.services.best_candidate', wraps=best_candidate) as best:
            self.save_video(backup, timems=3000)
            best.assert_not_called()
        self.save_video(first, timems=4000)
        self.assertEqual(self.record()['bt_id'], backup.id)
        with self.captureOnCommitCallbacks(execute=True):
            backup.delete()
        self.assertEqual(self.record()['bt_id'], first.id)
        with self.captureOnCommitCallbacks(execute=True):
            first.delete()
        self.assertIsNone(self.record()['bt'])
        self.assertEqual(self.client.get('/api/speedranking/strict_ng/rank').json()['count'], 0)

    def test_bulk_add_and_remove_rebuild_affected_records(self):
        backup = self.create_video(timems=2000)
        video = self.create_video(state=MS_TextChoices.State.IDENTIFIER)
        videos = VideoModel.objects.filter(pk=video.pk)
        with self.captureOnCommitCallbacks(execute=True):
            videos.update(state=MS_TextChoices.State.OFFICIAL)
            add_videos_to_speed_ranks(videos)
        self.assertEqual(self.record()['bt_id'], video.id)
        with self.captureOnCommitCallbacks(execute=True):
            videos.update(state=MS_TextChoices.State.IDENTIFIER)
            remove_videos_from_speed_ranks(videos)
        self.assertEqual(self.record()['bt_id'], backup.id)

    def test_rebuild_replaces_stale_entries_and_api_reads_only_redis(self):
        video = self.create_video()
        SpeedRankingCache('strict_ng', stats=RANK_STATS).flush()
        with self.assertNumQueries(0):
            self.assertIsNone(self.record()['bt'])
        call_command('rebuild_strict_ng_ranks', '--ranking-name', 'strict_ng', batch_size=1, stdout=StringIO())
        self.assertEqual(self.record()['bt_id'], video.id)
        with patch('speedranking.strict_ng.services._add_videos', side_effect=ValueError('failed')):
            with self.assertRaises(ValueError):
                call_command('rebuild_strict_ng_ranks', stdout=StringIO())
        self.assertEqual(self.record()['bt_id'], video.id)
        self.assertEqual(self.client.get('/api/speedranking/strict_ng/rank', {'ranking_name': 'invalid'}).status_code, 422)
        self.assertEqual(self.client.get('/api/speedranking/strict_ng/rank', {'stat': 'invalid'}).status_code, 422)

    def test_admin_rebuild_requires_staff_and_repairs_one_record(self):
        first = self.create_video(timems=1000)
        self.client.force_login(self.user)
        url = '/api/speedranking/strict_ng/admin/rebuild_record'
        payload = {'player_id': self.user.id, 'ranking_name': 'strict_ng', 'stat': 'bt'}
        self.assertEqual(self.client.post(url, payload).status_code, 403)
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        VideoModel.objects.filter(pk=first.pk).update(timems=3000)
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual((response.json()['bt'], response.json()['bt_id']), (3000, first.id))
        ranking = SpeedRankingCache('strict_ng')
        cache.zrem(ranking.rank_key('bt'), self.user.id)
        self.assertEqual(self.client.post(url, payload).status_code, 200)
        self.assertEqual(self.record()['ranks']['bt'], 1)
        for invalid in ({'ranking_name': 'invalid'}, {'stat': 'invalid'}, {'player_id': 'invalid'}):
            self.assertEqual(self.client.post(url, {**payload, **invalid}).status_code, 422)

    def test_admin_rebuild_totals_uses_cached_parts(self):
        self.create_video(timems=1000)
        self.create_video(level='i', bv=30, timems=10000)
        self.create_video(level='e', bv=100, timems=100000)
        ranking = SpeedRankingCache('strict_ng_nf')
        record = ranking.get_record(self.user.id)
        record['sumt'] = 0
        record['sumb'] = 0
        cache.hset(ranking.detail_key, self.user.id, json.dumps(record))
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)
        response = self.client.post('/api/speedranking/strict_ng/admin/rebuild_record', {'player_id': self.user.id, 'ranking_name': 'strict_ng_nf', 'stat': 'sumt'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['sumt'], 111000)
        # Totals are both recomputed from the cached parts, not read from the corrupted values.
        self.assertEqual(response.json()['sumb'], 8)
