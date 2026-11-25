from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import transaction
from django.test import override_settings, TestCase

from config.text_choices import MS_TextChoices
from msuser.models import UserMS
from userprofile.models import UserProfile
from videomanager.models import ExpandVideoModel, VideoModel
from .cache import PathRankingCache
from .services import best_candidate, prepare_remove_videos, rebuild_player_record
from .utils import candidate_for_video, METRICS, RECORD_FIELDS
from ..cache import cache
from ..services import add_videos_to_eff_ranks, remove_videos_from_eff_ranks


@override_settings(RATELIMIT_ENABLE=False)
class PathRankingTests(TestCase):
    def setUp(self):
        self.ranking = PathRankingCache()
        self.ranking.flush()
        self.addCleanup(self.ranking.flush)
        self.user = self.create_user('path')

    def create_user(self, name):
        return UserProfile.objects.create_user(username=name, email=f'{name}@example.com', userms=UserMS.objects.create())

    def create_video(self, **kwargs):
        fields = {'player': self.user, 'video': ExpandVideoModel.objects.create(identifier='path'), 'file': 'videos/path.evf', 'software': 'e', 'state': MS_TextChoices.State.OFFICIAL, 'level': 'b', 'mode': MS_TextChoices.Mode.STD, 'bv': 2, 'timems': 1000, 'left': 4, 'right': 0, 'double': 0, 'left_ce': 2, 'right_ce': 0, 'double_ce': 0, 'path': 10, 'cpath': 20, 'epath': 30}
        fields.update(kwargs)
        with self.captureOnCommitCallbacks(execute=True):
            return VideoModel.objects.create(**fields)

    def save_video(self, video, **fields):
        for name, value in fields.items():
            setattr(video, name, value)
        with self.captureOnCommitCallbacks(execute=True):
            video.save(update_fields=fields)

    def record(self, player=None):
        response = self.client.get(f'/api/effranking/path/player/{(player or self.user).id}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_independent_metrics_admission_zero_and_cache_only_queries(self):
        first = self.create_video()
        self.create_video()
        second = self.create_video(path=15, cpath=5, epath=None)
        third = self.create_video(path=None, cpath=None, epath=0, right_ce=1)
        for fields in ({'level': 'c8_8_40'}, {'mode': MS_TextChoices.Mode.RKC}, {'state': MS_TextChoices.State.IDENTIFIER}, {'ongoing_tournament': True}):
            self.create_video(path=0, cpath=0, epath=0, **fields)
        record = self.record()
        self.assertEqual([record[f'b_{metric}']['video_id'] for metric in METRICS], [first.id, second.id, third.id])
        self.create_video(level='i')
        self.create_video(level='e', cpath=None)
        with self.assertNumQueries(0):
            record = self.record()
            response = self.client.get('/api/effranking/path/rank', {'stat': 'sum_epath'})
        self.assertEqual(record['b_epath']['value'], 0)
        self.assertEqual(record['ranks']['sum_path'], 1)
        self.assertIsNone(record['ranks']['sum_cpath'])
        self.assertEqual(cache.zscore(self.ranking.rank_key('sum_epath'), self.user.id), 60)
        self.assertEqual(set(response.json()['players'][0]), {'player_id', *RECORD_FIELDS})
        self.assertEqual(self.client.get('/api/effranking/path/rank', {'stat': 'sum'}).status_code, 422)
        video = {'id': 1, 'level': 'b', 'mode': '00', 'state': MS_TextChoices.State.OFFICIAL, 'ongoing_tournament': False}
        for value in (None, -1, float('inf'), float('nan')):
            self.assertIsNone(candidate_for_video({**video, 'path': value}, 'path'))

    def test_partial_updates_only_rebuild_held_metrics_and_write_changed_indices(self):
        backup = self.create_video()
        best = self.create_video(path=5, cpath=10, epath=15)
        self.create_video(level='i')
        self.create_video(level='e')
        with patch('effranking.path.services.best_candidate', wraps=best_candidate) as rebuild, patch.object(PathRankingCache, 'write_changes', autospec=True, side_effect=PathRankingCache.write_changes) as writes:
            self.save_video(best, cpath=3)
        rebuild.assert_not_called()
        self.assertEqual(writes.call_args.args[1][0][2], {'b_cpath': 3, 'sum_cpath': 43})
        with patch('effranking.path.services.best_candidate', wraps=best_candidate) as rebuild:
            self.save_video(best, path=50, epath=None)
        self.assertEqual(rebuild.call_count, 2)
        self.assertEqual(self.record()['b_path']['video_id'], backup.id)
        self.assertEqual(self.record()['b_cpath']['video_id'], best.id)
        with patch('effranking.path.services.best_candidate', wraps=best_candidate) as rebuild:
            self.save_video(backup, cpath=100)
        rebuild.assert_not_called()

    def test_category_moves_delete_and_rollback(self):
        backup = self.create_video(path=20)
        best = self.create_video(path=5)
        other = self.create_user('path-other')
        self.save_video(best, player=other, level='e')
        self.assertEqual(self.record()['b_path']['video_id'], backup.id)
        self.assertEqual(self.record(other)['e_path']['video_id'], best.id)
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(ValueError), transaction.atomic():
                best.path = 0
                best.save(update_fields=['path'])
                raise ValueError('rollback')
        self.assertEqual(self.record(other)['e_path']['value'], 5)
        with self.captureOnCommitCallbacks(execute=True):
            best.delete()
        self.assertFalse(cache.hexists(self.ranking.detail_key, other.id))
        self.save_video(backup, ongoing_tournament=True)
        self.assertIsNone(self.record()['b_path'])

    def test_bulk_add_and_remove_use_per_metric_queries_not_per_player(self):
        ids = []
        backups = {}
        for index in range(3):
            user = self.user if index == 0 else self.create_user(f'path-bulk-{index}')
            backups[user.id] = {}
            for level in ('b', 'i'):
                backups[user.id][level] = self.create_video(player=user, level=level, path=100, cpath=100, epath=100)
                for metric in METRICS:
                    video = self.create_video(player=user, level=level, state=MS_TextChoices.State.IDENTIFIER, **{metric: 0})
                    ids.append(video.id)
        videos = VideoModel.objects.filter(id__in=ids)
        videos.update(state=MS_TextChoices.State.OFFICIAL)
        with self.captureOnCommitCallbacks(execute=True):
            add_videos_to_eff_ranks(videos)
        previous = self.ranking.read_records(backups)
        self.assertTrue(all(part['value'] == 0 for record in previous.values() for part in record.values() if part is not None))
        videos.update(state=MS_TextChoices.State.IDENTIFIER)
        with self.assertNumQueries(4):
            records = prepare_remove_videos(videos, previous)
        for player_id, levels in backups.items():
            for level, backup in levels.items():
                self.assertTrue(all(records[player_id][f'{level}_{metric}']['video_id'] == backup.id for metric in METRICS))
        with self.captureOnCommitCallbacks(execute=True):
            remove_videos_from_eff_ranks(videos)
        self.assertEqual(self.record()['b_epath']['value'], 100)

    @patch('effranking.news.emit')
    def test_news_reports_first_and_lower_raw_values_including_zero_and_sum(self, emit):
        first = self.create_video()
        self.create_video(level='i')
        self.create_video(level='e')
        fields = {call.args[2]['field'] for call in emit.call_args_list}
        self.assertIn('path:sum_epath', fields)
        total = next(call.args[2] for call in emit.call_args_list if call.args[2]['field'] == 'path:sum_epath')
        self.assertIsNone(total['new']['video_id'])
        emit.reset_mock()
        self.save_video(first, epath=0)
        changes = {call.args[2]['field']: call.args[2] for call in emit.call_args_list if call.args[2]['field'].startswith('path:')}
        self.assertEqual(set(changes), {'path:b_epath', 'path:sum_epath'})
        self.assertEqual(changes['path:b_epath']['new']['value'], 0)
        self.assertEqual(changes['path:b_epath']['old']['value'], 30)
        emit.reset_mock()
        self.save_video(first, epath=40)
        self.assertFalse(any(call.args[2]['field'].startswith('path:') for call in emit.call_args_list))

    def test_admin_single_and_cache_only_sum_repair_and_full_rebuild(self):
        first = self.create_video()
        self.create_video(level='i')
        self.create_video(level='e')
        url = '/api/effranking/path/admin/rebuild_record'
        payload = {'player_id': self.user.id, 'stat': 'b_cpath'}
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)
        VideoModel.objects.filter(id=first.id).update(cpath=2)
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['b_cpath']['value'], 2)
        cache.zrem(self.ranking.rank_key('sum_cpath'), self.user.id)
        with self.assertNumQueries(0):
            rebuild_player_record(self.user.id, 'sum_cpath')
        self.assertEqual(cache.zscore(self.ranking.rank_key('sum_cpath'), self.user.id), 42)
        self.ranking.flush()
        call_command('rebuild_eff_ranks', ranking_name='path', batch_size=1, stdout=StringIO())
        self.assertEqual(self.record()['b_cpath']['video_id'], first.id)
        self.assertEqual(cache.zscore(self.ranking.rank_key('sum_cpath'), self.user.id), 42)
