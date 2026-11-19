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
from .services import best_candidate, rebuild_player_record
from .utils import candidate_for_video, POWERS, RECORD_FIELDS
from ..cache import cache
from ..nf_ioe.cache import NFIOERankingCache
from ..services import add_videos_to_eff_ranks, remove_videos_from_eff_ranks
from ..thrp.cache import ThrpRankingCache


class TPEFormulaTests(SimpleTestCase):
    def test_invalid_ioe_is_not_a_candidate(self):
        video = {'id': 1, 'level': 'i', 'mode': '00', 'state': MS_TextChoices.State.OFFICIAL, 'ongoing_tournament': False, 'timems': 1000, 'ioe': 0.5}
        self.assertEqual(candidate_for_video(video), {'value': 2, 'video_id': 1})
        self.assertEqual(candidate_for_video(video, 2), {'value': 4, 'video_id': 1})
        self.assertEqual(candidate_for_video(video, 3), {'value': 8, 'video_id': 1})
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
        self.assertEqual(set(response.json()['players'][0]), {'player_id', *RECORD_FIELDS})
        self.assertEqual(personal['i']['value'], 0)
        self.assertEqual((personal['i2']['value'], personal['i3']['value']), (0, 0))
        self.assertEqual((personal['e2']['value'], personal['e3']['value']), (4, 8))
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
    def test_bulk_formulas_select_independent_records_and_only_rebuild_removed_holders(self, emit):
        first = self.create_video(left=8, timems=100, state=MS_TextChoices.State.IDENTIFIER)
        second = self.create_video(left=4, timems=300, state=MS_TextChoices.State.IDENTIFIER)
        third = self.create_video(left=2, timems=2000, state=MS_TextChoices.State.IDENTIFIER)
        expert = self.create_video(level='e', state=MS_TextChoices.State.IDENTIFIER)
        other = self.create_user('tpe-bulk-other')
        other_video = self.create_video(player=other, level='e', state=MS_TextChoices.State.IDENTIFIER)
        subset = VideoModel.objects.filter(pk__in=[first.pk, second.pk, third.pk, expert.pk, other_video.pk])
        subset.update(state=MS_TextChoices.State.OFFICIAL)
        emit.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            add_videos_to_eff_ranks(subset)
        record = self.record()
        self.assertEqual([record[stat]['video_id'] for stat in ('i', 'i2', 'i3')], [first.pk, second.pk, third.pk])
        self.assertEqual([cache.zscore(self.ranking.rank_key(stat), self.user.pk) for stat in ('sum', 'sum2', 'sum3')], [2.4, 5.2, 10])
        self.assertTrue(all(self.record(other)['ranks'][f'sum{suffix}'] is None for suffix in POWERS))
        self.assertFalse(any(call.args[2]['field'].startswith('tpe:') for call in emit.call_args_list))
        VideoModel.objects.filter(pk=first.pk).update(state=MS_TextChoices.State.IDENTIFIER)
        with patch('effranking.tpe.services.best_candidate', wraps=best_candidate) as rebuild, self.captureOnCommitCallbacks(execute=True):
            remove_videos_from_eff_ranks(VideoModel.objects.filter(pk=first.pk))
        rebuild.assert_called_once_with(self.user.pk, 'i', 1)
        self.assertEqual(self.record()['i']['video_id'], second.pk)
        self.save_video(expert, state=MS_TextChoices.State.IDENTIFIER)
        self.assertTrue(all(self.record()['ranks'][f'sum{suffix}'] is None for suffix in POWERS))
        self.save_video(expert, state=MS_TextChoices.State.OFFICIAL)
        self.assertTrue(all(self.record()['ranks'][f'sum{suffix}'] is not None for suffix in POWERS))

    def test_admin_and_rebuild_repair_complete_sum_without_sum_database_query(self):
        first = self.create_video()
        expert = self.create_video(level='e')
        url = '/api/effranking/tpe/admin/rebuild_record'
        payload = {'player_id': self.user.id, 'stat': 'i2'}
        self.assertEqual(self.client.post(url, payload).status_code, 403)
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)
        VideoModel.objects.filter(pk=first.pk).update(left=2)
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['i2']['value'], 1)
        self.assertEqual(response.json()['i']['value'], 2)
        cache.zrem(self.ranking.rank_key('sum2'), self.user.id)
        with self.assertNumQueries(0):
            rebuild_player_record(self.user.id, 'sum2')
        self.assertEqual(cache.zscore(self.ranking.rank_key('sum2'), self.user.id), 5)
        self.ranking.flush()
        call_command('rebuild_eff_ranks', ranking_name='tpe', batch_size=1, stdout=StringIO())
        self.assertEqual(self.record()['i']['video_id'], first.id)
        self.assertEqual(self.record()['e']['video_id'], expert.id)
        self.assertEqual(self.record()['i3']['video_id'], first.id)
        self.assertEqual(cache.zscore(self.ranking.rank_key('sum3'), self.user.id), 9)
        with patch('effranking.tpe.services.prepare_add_videos', side_effect=RuntimeError('failed rebuild')), self.assertRaises(RuntimeError):
            call_command('rebuild_eff_ranks', ranking_name='tpe', stdout=StringIO())
        self.assertEqual(self.record()['i']['value'], 1)
