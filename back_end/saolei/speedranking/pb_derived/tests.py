from io import StringIO

from django.core.management import call_command
from django.test import override_settings, SimpleTestCase, TestCase

from config.text_choices import MS_TextChoices
from msuser.models import UserMS
from userprofile.models import UserProfile
from videomanager.models import ExpandVideoModel, VideoModel
from .cache import PBDerivedCache
from .services import compute_for_records, prepare_changes, remove_player
from .utils import compute, FIELDS, PROBABILITIES, RANKINGS, SEGMENT_MEAN_PARTS, SEGMENT_WEIGHTS, SEGMENTS, ZERO_TT
from ..cache import cache, pipeline
from ..pb.cache import PBRankingCache
from ..saolei.cache import SpeedRankingCache
from ..saolei.utils import RANK_STATS, RANKING_NAMES


class DerivedComputationTests(SimpleTestCase):
    def test_segments_cover_each_level_without_gaps_or_overlaps(self):
        self.assertEqual({level: len(bounds) for level, bounds in SEGMENTS.items()}, {'b': 4, 'i': 8, 'e': 11})
        self.assertEqual(sum(len(bounds) for bounds in SEGMENTS.values()), 23)
        self.assertEqual(sum(len(fields) for fields in FIELDS.values()), 132)
        for level, bounds in SEGMENTS.items():
            expected = 1
            for index, (start, end) in enumerate(bounds):
                self.assertEqual(start, expected)
                self.assertGreaterEqual(end, start)
                self.assertGreater(SEGMENT_WEIGHTS[level][index], 0)
                expected = end + 1
            self.assertEqual(expected, len(PROBABILITIES[level]))
            self.assertAlmostEqual(sum(PROBABILITIES[level][1:]), 1.0)

    def test_full_range_normalization_and_typical_time(self):
        bv, timems = 10, 10000
        probability = PROBABILITIES['b'][bv]
        result = compute({(False, 'b', bv): timems})
        segment = next(index for index, (start, end) in enumerate(SEGMENTS['b']) if start <= bv <= end)
        weight = probability * (1000 * bv / timems)
        self.assertEqual(result['collection']['std:b:count'], 1)
        self.assertAlmostEqual(result['collection']['std:b:probability'], probability)
        self.assertAlmostEqual(result['collection']['std:sum:asb'], 1000 * bv / timems)
        self.assertAlmostEqual(result['skill'][f'std:b:s{segment + 1}'], weight / SEGMENT_WEIGHTS['b'][segment])
        self.assertAlmostEqual(result['typical_time'][f'std:b:s{segment + 1}'], SEGMENT_MEAN_PARTS['b'][segment] / weight)
        self.assertAlmostEqual(result['skill']['std:b:total'], weight)
        self.assertAlmostEqual(result['skill']['std:sum:total'], weight)

    def test_zero_weight_zero_timems_and_out_of_range_pb(self):
        zero = compute({(False, 'b', 0): 0})
        self.assertEqual(zero['collection']['std:b:count'], 1)
        self.assertEqual(zero['collection']['std:b:probability'], 0)
        self.assertEqual(zero['collection']['std:b:asb'], 0)
        self.assertEqual(zero['skill']['std:b:total'], 0)
        self.assertAlmostEqual(zero['typical_time']['std:b:total'], 4 * ZERO_TT)
        outside = compute({(False, 'b', 999): 1000})
        self.assertEqual(outside['collection']['std:b:count'], 1)
        self.assertEqual(outside['collection']['std:b:probability'], 0)
        self.assertEqual(outside['collection']['std:b:asb'], 999)
        self.assertEqual(outside['skill']['std:b:total'], 0)
        self.assertAlmostEqual(outside['typical_time']['std:b:total'], 4 * ZERO_TT)

    def test_zero_skill_totals_and_three_level_skill_sum(self):
        empty = compute({}, modes=('std',))
        self.assertEqual(empty['skill']['std:sum:total'], 0)
        self.assertAlmostEqual(empty['typical_time']['std:b:total'], 4 * ZERO_TT)
        self.assertAlmostEqual(empty['typical_time']['std:i:total'], 8 * ZERO_TT)
        self.assertAlmostEqual(empty['typical_time']['std:e:total'], 11 * ZERO_TT)
        self.assertAlmostEqual(empty['typical_time']['std:sum:total'], 23 * ZERO_TT)
        self.assertNotIn('nf:b:total', empty['skill'])
        mixed = compute({(False, 'b', 10): 10000, (False, 'i', 50): 20000, (False, 'e', 150): 30000})
        self.assertAlmostEqual(mixed['skill']['std:sum:total'], sum(mixed['skill'][f'std:{level}:total'] for level in ('b', 'i', 'e')))
        self.assertAlmostEqual(mixed['typical_time']['std:sum:total'], sum(mixed['typical_time'][f'std:{level}:total'] for level in ('b', 'i', 'e')))

    def test_new_positive_pb_never_reduces_skill_and_nf_is_separate(self):
        first = compute({(False, 'b', 10): 1000})
        both = compute({(False, 'b', 10): 1000, (False, 'b', 11): 999999999})
        self.assertGreater(both['skill']['std:sum:total'], first['skill']['std:sum:total'])
        self.assertEqual(both['collection']['std:sum:count'], 2)
        nf_only = compute({(True, 'i', 50): 10000})
        self.assertIn('nf:i:total', nf_only['skill'])
        self.assertNotIn('std:i:total', nf_only['skill'])


@override_settings(RATELIMIT_ENABLE=False)
class DerivedCacheTests(SimpleTestCase):
    def setUp(self):
        self.derived = PBDerivedCache()
        for ranking in (PBRankingCache(), self.derived, *(SpeedRankingCache(name, stats=RANK_STATS) for name in RANKING_NAMES)):
            ranking.flush()
            self.addCleanup(ranking.flush)

    def old_pb(self):
        return {7: {'std:b:10': {'timems': 10000, 'video_id': 1, 'rank': None}, 'nf:b:10': {'timems': 20000, 'video_id': 2, 'rank': None}}}

    def write(self, changes):
        previous = {player_id: self.derived.get_records(player_id) for player_id in changes}
        with pipeline() as pipe:
            self.derived.write_changes(pipe, previous, changes)
            pipe.execute()

    def test_prepare_changes_overlays_full_pb_and_keeps_nf(self):
        old = self.old_pb()
        changes = prepare_changes(old, {(7, 'std:b:10'): (3, 5000 * 2 ** 26)})
        expected = compute_for_records({**old[7], 'std:b:10': {'timems': 5000, 'video_id': 3, 'rank': None}})
        self.assertEqual(changes[7], expected)
        self.assertIn('nf:b:total', changes[7]['skill'])
        self.assertEqual(changes[7]['collection']['std:sum:count'], 1)

    def test_last_pb_removal_clears_only_that_category(self):
        old = self.old_pb()
        changes = prepare_changes(old, {(7, 'std:b:10'): None})
        self.write(changes)
        records = self.derived.get_records(7)
        self.assertTrue(all(not field.startswith('std:') for field in records['collection']))
        self.assertTrue(any(field.startswith('nf:') for field in records['skill']))
        for field in FIELDS['collection']:
            score = cache.zscore(self.derived.rank_key('collection', field), '7')
            if field.startswith('std:'):
                self.assertIsNone(score)
            else:
                self.assertIsNotNone(score)

    def test_equal_scores_follow_member_order(self):
        self.write({player: compute({}, modes=('std',)) for player in (2, 10)})
        rows = cache.zrange(self.derived.rank_key('collection', 'std:sum:count'), 0, -1)
        self.assertEqual([int(value) for value in rows], [10, 2])
        self.assertEqual(self.derived.get_range(('collection',), 'collection', 'std:sum:count', 0, 20)['players'], [10, 2])

    def test_remove_player_clears_hash_and_all_members(self):
        self.write({7: compute({}, modes=('std',))})
        remove_player(7)
        self.assertEqual(self.derived.get_records(7), {ranking: {} for ranking in RANKINGS})
        for ranking in RANKINGS:
            for field in FIELDS[ranking]:
                self.assertEqual(cache.zcard(self.derived.rank_key(ranking, field)), 0)


@override_settings(RATELIMIT_ENABLE=False)
class DerivedIntegrationTests(TestCase):
    def setUp(self):
        self.derived = PBDerivedCache()
        for ranking in (PBRankingCache(), self.derived, *(SpeedRankingCache(name, stats=RANK_STATS) for name in RANKING_NAMES)):
            ranking.flush()
            self.addCleanup(ranking.flush)
        self.user = UserProfile.objects.create_user(username='derived', email='derived@example.com', userms=UserMS.objects.create())

    def create_video(self, **kwargs):
        fields = {'player': self.user, 'video': ExpandVideoModel.objects.create(identifier='derived'), 'file': 'videos/derived.evf', 'software': 'e', 'state': MS_TextChoices.State.OFFICIAL, 'level': 'b', 'mode': '00', 'bv': 10, 'timems': 10000, 'right_ce': 0}
        fields.update(kwargs)
        with self.captureOnCommitCallbacks(execute=True):
            return VideoModel.objects.create(**fields)

    def test_video_updates_derived_hash_and_ranking_api(self):
        video = self.create_video()
        records = self.derived.get_records(self.user.id)
        self.assertEqual(records['collection']['std:sum:count'], 1)
        self.assertEqual(records['collection']['nf:sum:count'], 1)
        summary = self.client.get('/api/speedranking/pb_derived/summary', {'player_id': self.user.id})
        self.assertEqual(summary.status_code, 200, summary.content)
        payload = summary.json()
        self.assertEqual(len(payload['pb']), 2)
        self.assertEqual(payload['ranks']['collection']['std:sum:count'], 1)
        self.assertEqual(payload['ranks']['typical_time']['nf:e:s1'], 1)
        other = UserProfile.objects.create_user(username='derived-empty', email='derived-empty@example.com', userms=UserMS.objects.create())
        empty = self.client.get('/api/speedranking/pb_derived/summary', {'player_id': other.id}).json()
        self.assertIsNone(empty['ranks']['collection']['nf:sum:count'])
        self.assertAlmostEqual(empty['records']['typical_time']['nf:sum:total'], 23 * ZERO_TT)
        self.assertNotIn('meta', payload)
        self.assertNotIn('meta', empty)
        rank = self.client.get('/api/speedranking/pb_derived/rank', {'ranking': 'collection', 'field': 'std:sum:count'})
        self.assertEqual(rank.status_code, 200, rank.content)
        self.assertNotIn('meta', rank.json())
        self.assertEqual(rank.json()['count'], 1)
        self.assertEqual(rank.json()['rows'][0]['player_id'], self.user.id)
        skill = self.client.get('/api/speedranking/pb_derived/rank', {'ranking': 'skill', 'field': 'std:b:total'})
        self.assertEqual(set(skill.json()['rows'][0]['records']), {'skill', 'typical_time'})
        invalid = self.client.get('/api/speedranking/pb_derived/rank', {'ranking': 'collection', 'field': 'std:sum:total'})
        self.assertEqual(invalid.status_code, 422)
        with self.captureOnCommitCallbacks(execute=True):
            video.delete()
        self.assertEqual(self.derived.get_records(self.user.id), {ranking: {} for ranking in RANKINGS})
        self.assertEqual(self.client.get('/api/speedranking/pb_derived/rank', {'ranking': 'collection', 'field': 'std:sum:count'}).json()['count'], 0)

    def test_admin_rebuild_and_full_rebuild(self):
        self.create_video()
        url = '/api/speedranking/pb_derived/admin/rebuild_player'
        payload = {'player_id': self.user.id}
        self.assertEqual(self.client.post(url, payload).status_code, 403)
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)
        self.derived.flush()
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertGreater(response.json()['fields'], 0)
        self.assertIsNotNone(cache.zscore(self.derived.rank_key('typical_time', 'std:b:total'), str(self.user.id)))
        output = StringIO()
        call_command('rebuild_pb_derived_ranks', batch_size=1, stdout=output)
        self.assertIn('132 ranking indices', output.getvalue())
        self.assertEqual(self.derived.get_records(self.user.id)['collection']['std:sum:count'], 1)
        call_command('rebuild_pb_ranks', batch_size=1, stdout=StringIO())
        self.assertEqual(self.derived.get_records(self.user.id)['collection']['std:sum:count'], 1)

    def test_user_deletion_removes_derived_records(self):
        self.create_video()
        player_id = self.user.pk
        with self.captureOnCommitCallbacks(execute=True):
            self.user.delete()
        self.assertEqual(self.derived.get_records(player_id), {ranking: {} for ranking in RANKINGS})
