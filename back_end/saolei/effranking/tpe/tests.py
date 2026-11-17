from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import transaction
from django.test import override_settings, SimpleTestCase, TestCase

from config.text_choices import MS_TextChoices
from msuser.models import UserMS
from userprofile.models import UserProfile
from videomanager.models import ExpandVideoModel, VideoModel
from .cache import TPERankingCache
from .services import rebuild_player_record
from .utils import candidate_for_video
from ..cache import cache
from ..nf_ioe.cache import NFIOERankingCache
from ..services import add_videos_to_eff_ranks, remove_videos_from_eff_ranks
from ..thrp.cache import ThrpRankingCache


class TPEFormulaTests(SimpleTestCase):
    def test_invalid_ioe_is_not_a_candidate(self):
        video = {'id': 1, 'level': 'i', 'mode': '00', 'state': MS_TextChoices.State.OFFICIAL, 'ongoing_tournament': False, 'timems': 1000, 'ioe': 0.5}
        self.assertEqual(candidate_for_video(video), {'value': 2, 'video_id': 1})
        for ioe in (None, 0, -1, float('inf'), float('nan')):
            self.assertIsNone(candidate_for_video({**video, 'ioe': ioe}))


@override_settings(RATELIMIT_ENABLE=False)
class TPERankingTests(TestCase):
    def setUp(self):
        self.ranking = TPERankingCache()
        for ranking in (self.ranking, ThrpRankingCache(), NFIOERankingCache()):
            ranking.flush()
            self.addCleanup(ranking.flush)
        self.user = self.create_user('tpe')

    def create_user(self, name):
        return UserProfile.objects.create_user(username=name, email=f'{name}@example.com', userms=UserMS.objects.create())

    def create_video(self, **kwargs):
        fields = {'player': self.user, 'video': ExpandVideoModel.objects.create(identifier='tpe'), 'file': 'videos/tpe.evf', 'software': 'e', 'state': MS_TextChoices.State.OFFICIAL, 'level': 'i', 'mode': MS_TextChoices.Mode.STD, 'bv': 2, 'timems': 1000, 'left': 4, 'right': 0, 'double': 0, 'left_ce': 2, 'right_ce': 0, 'double_ce': 0}
        fields.update(kwargs)
        with self.captureOnCommitCallbacks(execute=True):
            return VideoModel.objects.create(**fields)

    def save_video(self, video, **fields):
        for name, value in fields.items():
            setattr(video, name, value)
        with self.captureOnCommitCallbacks(execute=True):
            video.save(update_fields=fields)

    def record(self, player=None):
        response = self.client.get(f'/api/effranking/tpe/player/{(player or self.user).id}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_admission_actual_clicks_zero_and_read_only_api(self):
        first = self.create_video()
        self.create_video(timems=500, left=12)
        self.create_video(timems=1000)
        for fields in ({'level': 'b'}, {'level': 'c8_8_40'}, {'mode': MS_TextChoices.Mode.RKC}, {'state': MS_TextChoices.State.IDENTIFIER}, {'ongoing_tournament': True}, {'left': None}):
            self.create_video(**fields)
        self.assertEqual(self.record()['i'], {'value': 2, 'video_id': first.id})
        self.assertIsNone(self.record()['ranks']['sum'])
        self.save_video(first, double=2)
        self.assertNotEqual(self.record()['i']['video_id'], first.id)
        self.save_video(first, bv=4)
        self.assertEqual(self.record()['i']['video_id'], first.id)
        self.save_video(first, timems=0)
        self.assertEqual(self.record()['i']['value'], 0)
        expert = self.create_video(level='e', right_ce=1)
        self.assertEqual(self.record()['e']['video_id'], expert.id)
        self.assertEqual(self.record()['ranks']['sum'], 1)
        with self.assertNumQueries(0):
            response = self.client.get('/api/effranking/tpe/rank', {'stat': 'sum', 'end': 1})
            personal = self.record()
        self.assertEqual(set(response.json()['players'][0]), {'player_id', 'i', 'e'})
        self.assertEqual(personal['i']['value'], 0)
        self.assertEqual(self.client.get('/api/effranking/tpe/rank', {'stat': 'b'}).status_code, 422)

    def test_category_moves_deletion_and_rollback(self):
        backup = self.create_video(timems=2000)
        best = self.create_video()
        other = self.create_user('tpe-other')
        self.save_video(best, player=other, level='e')
        self.assertEqual(self.record()['i']['video_id'], backup.id)
        self.assertEqual(self.record(other)['e']['video_id'], best.id)
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(ValueError), transaction.atomic():
                best.timems = 0
                best.save(update_fields=['timems'])
                raise ValueError('rollback')
        self.assertEqual(self.record(other)['e']['value'], 2)
        with self.captureOnCommitCallbacks(execute=True):
            best.delete()
        self.assertIsNone(self.record(other)['e'])
        self.assertFalse(cache.hexists(self.ranking.detail_key, other.id))
        self.save_video(backup, ongoing_tournament=True)
        self.assertIsNone(self.record()['i'])

    @patch('effranking.news.emit')
    def test_bulk_add_remove_and_news_require_both_sum_components(self, emit):
        first = self.create_video(state=MS_TextChoices.State.IDENTIFIER)
        second = self.create_video(level='e', state=MS_TextChoices.State.IDENTIFIER)
        subset = VideoModel.objects.filter(pk__in=[first.pk, second.pk])
        subset.update(state=MS_TextChoices.State.OFFICIAL)
        emit.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            add_videos_to_eff_ranks(subset)
        payloads = [call.args[2] for call in emit.call_args_list if call.args[2]['field'].startswith('tpe:')]
        self.assertEqual([item['field'] for item in payloads], ['tpe:i', 'tpe:e', 'tpe:sum'])
        self.assertIsNone(payloads[-1]['old'])
        self.assertIsNone(payloads[-1]['new']['video_id'])
        self.assertEqual(payloads[-1]['new']['value'], 4)
        VideoModel.objects.filter(pk=first.pk).update(state=MS_TextChoices.State.IDENTIFIER)
        with self.captureOnCommitCallbacks(execute=True):
            remove_videos_from_eff_ranks(VideoModel.objects.filter(pk=first.pk))
        self.assertIsNone(self.record()['ranks']['sum'])
        emit.reset_mock()
        self.save_video(first, state=MS_TextChoices.State.OFFICIAL)
        total = next(call.args[2] for call in emit.call_args_list if call.args[2]['field'] == 'tpe:sum')
        self.assertIsNone(total['old'])
        emit.reset_mock()
        self.save_video(first, timems=500)
        improved = next(call.args[2] for call in emit.call_args_list if call.args[2]['field'] == 'tpe:i')
        self.assertEqual((improved['old']['value'], improved['new']['value']), (2, 1))
        emit.reset_mock()
        self.save_video(first, timems=2000)
        self.assertFalse(any(call.args[2]['field'].startswith('tpe:') for call in emit.call_args_list))

    def test_admin_and_rebuild_repair_complete_sum_without_sum_database_query(self):
        first = self.create_video()
        expert = self.create_video(level='e')
        url = '/api/effranking/tpe/admin/rebuild_record'
        payload = {'player_id': self.user.id, 'stat': 'i'}
        self.assertEqual(self.client.post(url, payload).status_code, 403)
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)
        VideoModel.objects.filter(pk=first.pk).update(left=2)
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['i']['value'], 1)
        cache.zrem(self.ranking.rank_key('sum'), self.user.id)
        with self.assertNumQueries(0):
            rebuild_player_record(self.user.id, 'sum')
        self.assertEqual(cache.zscore(self.ranking.rank_key('sum'), self.user.id), 3)
        self.ranking.flush()
        call_command('rebuild_eff_ranks', ranking_name='tpe', batch_size=1, stdout=StringIO())
        self.assertEqual(self.record()['i']['video_id'], first.id)
        self.assertEqual(self.record()['e']['video_id'], expert.id)
        with patch('effranking.tpe.services.prepare_add_videos', side_effect=RuntimeError('failed rebuild')), self.assertRaises(RuntimeError):
            call_command('rebuild_eff_ranks', ranking_name='tpe', stdout=StringIO())
        self.assertEqual(self.record()['i']['value'], 1)
