from io import StringIO

from django.core.management import call_command
from django.test import override_settings, SimpleTestCase, TestCase

from config.text_choices import MS_TextChoices
from msuser.models import UserMS
from userprofile.models import UserProfile
from videomanager.models import ExpandVideoModel, VideoModel
from .cache import NFIOERankingCache
from .services import rebuild_player_record
from .utils import empty_record, encode_score, MAX_TIMEMS, RANK_STATS, record_scores
from ..cache import cache
from ..thrp.cache import ThrpRankingCache


class NFIOEScoreTests(SimpleTestCase):
    def test_piecewise_scores_and_sum_use_raw_ioe_and_expert_time(self):
        self.assertEqual(encode_score(0.9, 0), encode_score(0.9, MAX_TIMEMS))
        self.assertLess(encode_score(1, MAX_TIMEMS), encode_score(0.999, 0))
        self.assertEqual(encode_score(1, 0), -(1 + MAX_TIMEMS))
        self.assertEqual(encode_score(3, MAX_TIMEMS, 3), -3)
        self.assertEqual(record_scores(empty_record()), dict.fromkeys(RANK_STATS))
        record = {level: {'value': 1, 'video_id': i, 'timems': 1000} for i, level in enumerate(('b', 'i', 'e'), 1)}
        self.assertEqual(record_scores(record)['sum'], -(3 + MAX_TIMEMS - 1000))
        record['b']['timems'] = 0
        self.assertEqual(record_scores(record)['sum'], -(3 + MAX_TIMEMS - 1000))
        record['i'] = None
        self.assertEqual(record_scores(record)['sum'], -2)


@override_settings(RATELIMIT_ENABLE=False)
class NFIOERankingTests(TestCase):
    def setUp(self):
        self.ranking = NFIOERankingCache()
        for ranking in (self.ranking, ThrpRankingCache()):
            ranking.flush()
            self.addCleanup(ranking.flush)
        self.user = self.create_user('nf-ioe')

    def create_user(self, name):
        return UserProfile.objects.create_user(username=name, email=f'{name}@example.com', userms=UserMS.objects.create())

    def create_video(self, **kwargs):
        fields = {'player': self.user, 'video': ExpandVideoModel.objects.create(identifier='nf-ioe'), 'file': 'videos/nf-ioe.evf', 'software': 'e', 'state': MS_TextChoices.State.OFFICIAL, 'level': 'b', 'mode': MS_TextChoices.Mode.STD, 'bv': 2, 'timems': 1000, 'left': 2, 'right': 0, 'double': 0, 'left_ce': 2, 'right_ce': 0, 'double_ce': 0}
        fields.update(kwargs)
        with self.captureOnCommitCallbacks(execute=True):
            return VideoModel.objects.create(**fields)

    def save_video(self, video, **fields):
        for name, value in fields.items():
            setattr(video, name, value)
        with self.captureOnCommitCallbacks(execute=True):
            video.save(update_fields=fields)

    def record(self, player=None):
        response = self.client.get(f'/api/effranking/nf_ioe/player/{(player or self.user).id}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_admission_ties_perfect_speed_and_generated_click_updates(self):
        first = self.create_video(left=3, timems=5000)
        self.create_video(bv=4, left=6, timems=1)
        for fields in ({'right_ce': 1}, {'state': MS_TextChoices.State.IDENTIFIER}, {'ongoing_tournament': True}, {'mode': MS_TextChoices.Mode.RKC}, {'level': 'c8_8_40'}, {'left': None}):
            self.create_video(**fields)
        self.assertEqual(self.record()['b']['video_id'], first.id)
        self.assertEqual(self.record()['ranks'], {'b': 1, 'i': None, 'e': None, 'sum': 1})
        perfect = self.create_video()
        faster = self.create_video(timems=500)
        self.assertEqual(self.record()['b']['video_id'], faster.id)
        self.save_video(perfect, timems=200)
        self.assertEqual(self.record()['b']['video_id'], perfect.id)
        self.save_video(perfect, double=1)
        self.assertEqual(self.record()['b']['video_id'], faster.id)
        with self.captureOnCommitCallbacks(execute=True):
            faster.delete()
        self.assertAlmostEqual(self.record()['b']['value'], 2 / 3)
        with self.assertNumQueries(0):
            response = self.client.get('/api/effranking/nf_ioe/rank', {'stat': 'b', 'end': 1})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(set(response.json()['players'][0]), {'player_id', 'b', 'i', 'e'})
        self.assertEqual(self.client.get('/api/effranking/nf_ioe/rank', {'stat': 'bad'}).status_code, 422)

    def test_full_sum_only_compares_expert_time_and_moves_rebuild_old_category(self):
        other = self.create_user('nf-ioe-other')
        mine = {}
        theirs = {}
        for level in ('b', 'i', 'e'):
            mine[level] = self.create_video(level=level, timems=4000 if level == 'e' else 9000)
            theirs[level] = self.create_video(player=other, level=level, timems=5000 if level == 'e' else 1)
        self.assertEqual(self.ranking.get_range('sum', 0, 1)['players'][0]['player_id'], self.user.id)
        score = cache.zscore(self.ranking.rank_key('sum'), self.user.id)
        self.save_video(mine['b'], timems=0)
        self.assertEqual(cache.zscore(self.ranking.rank_key('sum'), self.user.id), score)
        self.save_video(theirs['e'], timems=3500)
        self.assertEqual(self.ranking.get_range('sum', 0, 1)['players'][0]['player_id'], other.id)
        self.save_video(theirs['e'], player=self.user, level='i')
        self.assertIsNone(self.record(other)['e'])
        self.assertEqual(self.record()['i']['video_id'], theirs['e'].id)
        self.save_video(mine['e'], right_ce=1)
        self.assertIsNone(self.record()['e'])

    def test_admin_repairs_selected_field_and_sum_uses_cache(self):
        video = self.create_video(left=3)
        url = '/api/effranking/nf_ioe/admin/rebuild_record'
        payload = {'player_id': self.user.id, 'stat': 'b'}
        self.assertEqual(self.client.post(url, payload).status_code, 403)
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)
        VideoModel.objects.filter(pk=video.pk).update(left=2)
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['b']['value'], 1)
        cache.zrem(self.ranking.rank_key('sum'), self.user.id)
        with self.assertNumQueries(0):
            rebuild_player_record(self.user.id, 'sum')
        self.assertEqual(self.record()['ranks']['sum'], 1)

    def test_rebuild_selects_fastest_perfect(self):
        self.create_video(timems=2000)
        best = self.create_video(timems=100)
        self.ranking.flush()
        call_command('rebuild_eff_ranks', ranking_name='nf_ioe', batch_size=1, stdout=StringIO())
        self.assertEqual(self.record()['b']['video_id'], best.id)
