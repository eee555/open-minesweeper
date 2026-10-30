from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import transaction
from django.test import override_settings, SimpleTestCase, TestCase
from django.utils import timezone

from config.text_choices import MS_TextChoices, Tournament_TextChoices
from identifier.models import Identifier
from identifier.services import bind_identifier, unbind_identifier
from msuser.models import UserMS
from tournament.models import Tournament
from tournament.services import reveal_videos_for_tournament
from userprofile.models import UserProfile
from videomanager.models import ExpandVideoModel, VideoModel
from .cache import ThrpRankingCache
from .services import rebuild_player_record
from .utils import empty_record, encode_score, EPOCH, RANK_STATS, record_scores, SCORE_TIME_FACTOR
from ..cache import cache
from ..nf_ioe.cache import NFIOERankingCache
from ..services import add_videos_to_eff_ranks


class ThrpScoreTests(SimpleTestCase):
    def test_shared_encoding_keeps_precision_and_uses_latest_sum_upload(self):
        first = EPOCH.isoformat()
        last = (EPOCH + timedelta(minutes=SCORE_TIME_FACTOR - 1)).isoformat()
        for value in (0, 3.4, 10.2):
            for upload in (first, last):
                score = encode_score(value, upload)
                self.assertLess(abs(score), 2 ** 53)
                self.assertEqual(int(float(score)), score)
        self.assertLess(encode_score(1.000001, last), encode_score(1, first))
        self.assertLess(encode_score(1, first), encode_score(1, last))
        self.assertNotEqual(encode_score(1000 / 999, first), encode_score(1001 / 1000, first))
        record = empty_record()
        record['b'] = {'value': 1.0000004, 'video_id': 1, 'upload_time': first}
        record['i'] = {'value': 1.0000004, 'video_id': 2, 'upload_time': last}
        self.assertEqual(record_scores(record)['sum'], encode_score(2.0000008, last))
        self.assertEqual(record_scores(empty_record()), dict.fromkeys(RANK_STATS))


@override_settings(RATELIMIT_ENABLE=False)
class ThrpRankingTests(TestCase):
    def setUp(self):
        self.ranking = ThrpRankingCache()
        self.ranking.flush()
        self.addCleanup(self.ranking.flush)
        self.user = self.create_user('eff')

    def create_user(self, name):
        return UserProfile.objects.create_user(username=name, email=f'{name}@example.com', userms=UserMS.objects.create())

    def create_video(self, **kwargs):
        fields = {'player': self.user, 'video': ExpandVideoModel.objects.create(identifier='eff'), 'file': 'videos/eff.evf', 'software': 'e', 'state': MS_TextChoices.State.OFFICIAL, 'level': 'b', 'mode': MS_TextChoices.Mode.STD, 'bv': 2, 'timems': 1000, 'left_ce': 2, 'right_ce': 0, 'double_ce': 0}
        fields.update(kwargs)
        with self.captureOnCommitCallbacks(execute=True):
            return VideoModel.objects.create(**fields)

    def save_video(self, video, **fields):
        for name, value in fields.items():
            setattr(video, name, value)
        with self.captureOnCommitCallbacks(execute=True):
            video.save(update_fields=fields)

    def record(self, player=None):
        response = self.client.get(f'/api/effranking/thrp/player/{(player or self.user).id}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_admission_partial_totals_and_standard_includes_nf(self):
        first = self.create_video(bv=1, left_ce=1)
        self.create_video(bv=2, left_ce=1, right_ce=1)
        for fields in ({'state': MS_TextChoices.State.IDENTIFIER}, {'ongoing_tournament': True}, {'mode': MS_TextChoices.Mode.RKC}, {'level': 'c8_8_40'}, {'left_ce': None}):
            self.create_video(**fields)
        self.assertEqual(self.record()['b']['video_id'], first.id)
        self.assertIsNone(self.record()['i'])
        self.assertEqual(self.record()['ranks'], {'b': 1, 'i': None, 'e': None, 'sum': 1, 'e_nf': None})
        other = self.create_user('other')
        self.create_video(player=other, level='e', bv=3, left_ce=1, right_ce=1)
        with self.assertNumQueries(0):
            response = self.client.get('/api/effranking/thrp/rank', {'stat': 'sum', 'start': 0, 'end': 1})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['count'], 2)
        self.assertEqual(response.json()['players'][0]['player_id'], other.id)
        self.assertEqual(set(response.json()['players'][0]), {'player_id', 'b', 'i', 'e', 'e_nf'})
        self.assertEqual(self.client.get('/api/effranking/thrp/rank', {'stat': 'bad'}).status_code, 422)
        self.assertEqual(self.client.get('/api/effranking/thrp/rank', {'start': 0, 'end': 0}).json()['players'], [])

    def test_click_tracking_reloads_generated_thrp_and_backfills_deleted_record(self):
        backup = self.create_video(bv=3, left_ce=2)
        video = self.create_video(bv=6, left_ce=2, double_ce=2)
        self.assertEqual(self.record()['b']['video_id'], backup.id)
        self.save_video(video, double_ce=0)
        self.assertEqual(self.record()['b']['value'], 3)
        self.assertEqual(self.record()['b']['video_id'], video.id)
        self.save_video(video, left_ce=3)
        self.assertEqual(self.record()['b']['value'], 2)
        self.save_video(video, right_ce=2)
        self.assertEqual(self.record()['b']['video_id'], backup.id)
        self.save_video(video, bv=10)
        self.assertEqual(self.record()['b']['video_id'], video.id)
        with self.captureOnCommitCallbacks(execute=True):
            video.delete()
        self.assertEqual(self.record()['b']['video_id'], backup.id)
        with self.captureOnCommitCallbacks(execute=True):
            backup.delete()
        self.assertIsNone(self.record()['b'])
        self.assertEqual(self.record()['ranks'], dict.fromkeys(RANK_STATS))
        self.assertFalse(cache.hexists(self.ranking.detail_key, self.user.id))

    def test_ties_use_upload_time_and_sum_uses_latest_component(self):
        minute = timezone.now().replace(second=0, microsecond=0)
        older = self.create_video()
        self.save_video(older, upload_time=minute)
        newer = self.create_video()
        self.assertEqual(self.record()['b']['video_id'], older.id)
        self.save_video(newer, upload_time=minute - timedelta(microseconds=1))
        self.assertEqual(self.record()['b']['video_id'], newer.id)
        other = self.create_user('tie')
        other_b = self.create_video(player=other)
        self.save_video(other_b, upload_time=minute + timedelta(minutes=1))
        self.assertEqual(self.ranking.get_range('b', 0, 1)['players'][0]['player_id'], self.user.id)
        mine_i = self.create_video(level='i')
        self.save_video(mine_i, upload_time=minute + timedelta(minutes=4))
        other_i = self.create_video(player=other, level='i')
        self.save_video(other_i, upload_time=minute + timedelta(minutes=3))
        self.assertEqual(self.ranking.get_range('sum', 0, 1)['players'][0]['player_id'], other.id)
        self.save_video(mine_i, upload_time=minute + timedelta(minutes=2))
        self.assertEqual(self.ranking.get_range('sum', 0, 1)['players'][0]['player_id'], self.user.id)

    def test_category_moves_and_rollback(self):
        backup = self.create_video()
        moved = self.create_video(bv=3, left_ce=2)
        other = self.create_user('moved')
        self.save_video(moved, player=other, level='i')
        self.assertEqual(self.record()['b']['video_id'], backup.id)
        self.assertEqual(self.record(other)['i']['video_id'], moved.id)
        self.save_video(moved, ongoing_tournament=True)
        self.assertIsNone(self.record(other)['i'])
        self.save_video(moved, ongoing_tournament=False)
        self.assertEqual(self.record(other)['i']['video_id'], moved.id)
        with self.assertRaises(ValueError), self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                VideoModel.objects.create(player=other, video=ExpandVideoModel.objects.create(identifier='eff'), file='videos/rollback-eff.evf', software='e', state=MS_TextChoices.State.OFFICIAL, level='e', bv=2, timems=1000, left_ce=2, right_ce=0, double_ce=0)
                raise ValueError('rollback')
        self.assertIsNone(self.record(other)['e'])
        self.assertIsNone(self.record(other)['e_nf'])

    def test_bulk_identifier_and_tournament_update_both_efficiency_ranks(self):
        ioe_ranking = NFIOERankingCache()
        ioe_ranking.flush()
        self.addCleanup(ioe_ranking.flush)
        identifier = Identifier.objects.create(identifier='eff', safe=True)
        clicks = {'left': 2, 'right': 0, 'double': 0}
        video = self.create_video(state=MS_TextChoices.State.IDENTIFIER, **clicks)
        first_nf = self.create_video(level='e', state=MS_TextChoices.State.IDENTIFIER, **clicks)
        second_nf = self.create_video(level='e', state=MS_TextChoices.State.IDENTIFIER, timems=100, **clicks)
        self.assertIsNone(self.record()['b'])
        with self.captureOnCommitCallbacks(execute=True):
            bind_identifier(identifier, self.user.userms)
        self.assertEqual(self.record()['b']['video_id'], video.id)
        self.assertEqual(self.record()['e_nf']['video_ids'], [first_nf.id, second_nf.id])
        self.assertEqual(ioe_ranking.get_player(self.user.id)['e']['video_id'], second_nf.id)
        with self.captureOnCommitCallbacks(execute=True):
            add_videos_to_eff_ranks(VideoModel.objects.filter(pk__in=[first_nf.pk, second_nf.pk]))
        self.assertEqual(self.record()['e_nf']['video_ids'], [first_nf.id, second_nf.id])
        self.assertEqual(ioe_ranking.get_player(self.user.id)['e']['video_id'], second_nf.id)
        with self.captureOnCommitCallbacks(execute=True):
            unbind_identifier(identifier)
        self.assertIsNone(self.record()['b'])
        self.assertIsNone(self.record()['e_nf'])
        self.assertEqual(ioe_ranking.get_player(self.user.id)['ranks'], dict.fromkeys(('b', 'i', 'e', 'sum')))
        hidden = self.create_video(level='e', ongoing_tournament=True, **clicks)
        tournament = Tournament.objects.create(state=Tournament_TextChoices.State.AWARDED)
        tournament.videos.add(hidden)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(reveal_videos_for_tournament(tournament), 1)
        self.assertEqual(self.record()['e']['video_id'], hidden.id)
        self.assertEqual(self.record()['e_nf']['video_ids'], [hidden.id])
        self.assertEqual(ioe_ranking.get_player(self.user.id)['e']['video_id'], hidden.id)

    def test_admin_repairs_only_selected_record_and_sum_uses_cache(self):
        video = self.create_video()
        backup = self.create_video(bv=3, left_ce=2)
        url = '/api/effranking/thrp/admin/rebuild_record'
        payload = {'player_id': self.user.id, 'stat': 'b'}
        self.assertEqual(self.client.post(url, payload).status_code, 403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(url, payload).status_code, 403)
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        VideoModel.objects.filter(pk=video.pk).update(bv=6)
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['b']['video_id'], video.id)
        self.assertEqual(response.json()['b']['value'], 3)
        self.assertEqual(self.client.post(url, {'player_id': self.user.id, 'stat': 'bad'}).status_code, 422)
        cache.zrem(self.ranking.rank_key('sum'), self.user.id)
        with self.assertNumQueries(0):
            rebuild_player_record(self.user.id, 'sum')
        self.assertEqual(self.record()['ranks']['sum'], 1)
        VideoModel.objects.filter(pk=video.pk).update(state=MS_TextChoices.State.FROZEN)
        response = self.client.post(url, payload)
        self.assertEqual(response.json()['b']['video_id'], backup.id)
        first_nf = self.create_video(level='e')
        second_nf = self.create_video(level='e')
        before = self.record()
        VideoModel.objects.filter(pk=first_nf.pk).update(state=MS_TextChoices.State.FROZEN)
        response = self.client.post(url, {'player_id': self.user.id, 'stat': 'e_nf'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['e_nf']['video_ids'], [second_nf.id])
        self.assertEqual(response.json()['b'], before['b'])
        self.assertEqual(response.json()['e'], before['e'])

    def test_rebuild_publishes_complete_results_and_preserves_old_on_failure(self):
        video = self.create_video(level='e')
        second = self.create_video(level='e')
        self.ranking.flush()
        with self.assertNumQueries(0):
            self.assertIsNone(self.record()['e_nf'])
        call_command('rebuild_eff_ranks', '--ranking-name', 'thrp', batch_size=1, stdout=StringIO())
        self.assertEqual(self.record()['e_nf']['video_ids'], [video.id, second.id])
        with self.assertLogs('effranking', level='ERROR'), patch('effranking.thrp.services.prepare_add_videos', side_effect=ValueError('failed')):
            with self.assertRaises(ValueError):
                call_command('rebuild_eff_ranks', stdout=StringIO())
        self.assertEqual(self.record()['e_nf']['video_ids'], [video.id, second.id])
        VideoModel.objects.filter(player=self.user).update(state=MS_TextChoices.State.IDENTIFIER)
        call_command('rebuild_eff_ranks', stdout=StringIO())
        self.assertEqual(self.record()['ranks'], dict.fromkeys(RANK_STATS))

    def test_expert_nf_counts_every_perfect_game_and_backfills_after_changes(self):
        low = self.create_video(level='e', bv=4, left_ce=5)
        other = self.create_user('nf-other')
        self.create_video(player=other, level='e', bv=9, left_ce=10)
        self.assertEqual(self.record()['e_nf']['video_ids'], [low.id])
        self.assertEqual(self.ranking.get_range('e_nf', 0, 2)['players'][0]['player_id'], other.id)
        first = self.create_video(level='e', bv=5, left_ce=5)
        second = self.create_video(level='e', bv=5, left_ce=5)
        other_first = self.create_video(player=other, level='e', bv=5, left_ce=5)
        self.assertEqual(self.record()['e_nf']['video_ids'], [first.id, second.id])
        self.assertEqual(cache.zscore(self.ranking.rank_key('e_nf'), self.user.id), -2)
        self.assertEqual(self.ranking.get_range('e_nf', 0, 2)['players'][0]['player_id'], self.user.id)
        # 高级 NF 是独立项，不能重复计入 sum。
        self.assertEqual(cache.zscore(self.ranking.rank_key('sum'), self.user.id), encode_score(1, self.record()['e']['upload_time']))
        self.save_video(second, player=other)
        self.assertEqual(self.record()['e_nf']['video_ids'], [first.id])
        self.assertEqual(self.record(other)['e_nf']['video_ids'], [second.id, other_first.id])
        self.save_video(first, right_ce=1)
        self.assertEqual(self.record()['e_nf']['video_ids'], [low.id])
        self.assertAlmostEqual(cache.zscore(self.ranking.rank_key('e_nf'), self.user.id), -0.8)
        self.save_video(first, right_ce=0)
        self.save_video(second, mode=MS_TextChoices.Mode.RKC)
        self.assertEqual(self.record(other)['e_nf']['video_ids'], [other_first.id])
        with self.captureOnCommitCallbacks(execute=True):
            first.delete()
        self.assertEqual(self.record()['e_nf']['video_ids'], [low.id])
        with self.captureOnCommitCallbacks(execute=True):
            low.delete()
        self.assertIsNone(self.record()['e_nf'])
        self.assertIsNone(self.record()['ranks']['e_nf'])
        self.assertEqual(self.record(other)['e_nf']['value'], 1)
