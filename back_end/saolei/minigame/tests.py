from dataclasses import replace
from io import StringIO
import json
from unittest.mock import patch
from uuid import uuid4

from django.core.management import call_command
from django.db import connection, IntegrityError, transaction
from django.test import override_settings, TestCase
from django.test.utils import CaptureQueriesContext
from redis.exceptions import ConnectionError as RedisConnectionError

from config.global_settings import MAX_SAFE_INTEGER
from userprofile.models import UserProfile
from .archive import pack_replay, unpack_replay
from .cache import MiniGameRankingCache
from .models import MiniGameBestScore
from .services import get_player_scores, get_ranking, submit_score
from .utils import GAME_RANKINGS, RANKINGS


@override_settings(RATELIMIT_ENABLE=False)
class MiniGameRankingTests(TestCase):
    def setUp(self):
        namespace = patch.object(MiniGameRankingCache, 'prefix', f'test:minigame:{uuid4().hex}')
        namespace.start()
        self.addCleanup(namespace.stop)
        self.cache = MiniGameRankingCache()
        self.addCleanup(lambda: self.cache.client.delete(*self.cache.keys))
        self.player = self.make_player('minigame')
        self.ranking_key = GAME_RANKINGS['left-click'][0].key
        self.replay = {'version': 1, 'cellSize': 32, 'initialBoard': 'AAAAAP////8', 'events': [], 'specialEvents': []}

    def make_player(self, name):
        return UserProfile.objects.create_user(username=name, email=f'{name}@example.com')

    def submit(self, score, ranking_key=None, player=None, replay=None):
        with self.captureOnCommitCallbacks(execute=True):
            return submit_score(player or self.player, ranking_key or self.ranking_key, score, self.replay if replay is None else replay)

    def post_data(self, score, replay=None):
        return {'score': score, 'replay': json.dumps(self.replay if replay is None else replay)}

    def test_best_score_and_unique_constraint(self):
        first = self.submit(2000)
        achieved_at = first['record'].achieved_at
        self.assertTrue(first['improved'])
        for score in (2000, 3000):
            with patch('minigame.services.update_cached_score') as update:
                result = self.submit(score)
            self.assertFalse(result['improved'])
            self.assertEqual(result['record'].achieved_at, achieved_at)
            update.assert_not_called()
        improved = self.submit(1000)
        self.assertTrue(improved['improved'])
        self.assertGreater(improved['record'].achieved_at, achieved_at)
        self.assertEqual(self.cache.client.zscore(self.cache.rank_key(self.ranking_key), self.player.id), 1000)
        with transaction.atomic(), self.assertRaises(IntegrityError):
            MiniGameBestScore.objects.create(player=self.player, ranking_key=self.ranking_key, score=4000, replay_archive=pack_replay(self.replay))
        second_ranking_key = GAME_RANKINGS['left-click'][1].key
        self.submit(5000, second_ranking_key)
        self.assertEqual(MiniGameBestScore.objects.filter(player=self.player).count(), 2)

    def test_upload_without_realname_profile_or_link_and_auth_boundaries(self):
        url = f'/api/minigame/{self.ranking_key}/score'
        self.assertFalse(self.player.has_realname())
        self.assertIsNone(self.player.userms_id)
        self.assertEqual(self.client.post(url, self.post_data(1000)).status_code, 403)
        self.client.force_login(self.player)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, {**self.post_data(1000), 'player_id': 999})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['record']['player_id'], self.player.id)
        self.assertEqual(response.json()['record']['ranking_key'], self.ranking_key)
        self.assertNotIn('replay', response.json()['record'])
        self.assertEqual(unpack_replay(MiniGameBestScore.objects.get(player=self.player, ranking_key=self.ranking_key).replay_archive), self.replay)
        self.player.is_banned = True
        self.player.save(update_fields=['is_banned'])
        self.assertEqual(self.client.post(url, self.post_data(500)).status_code, 403)

    def test_input_errors_and_slashless_routes(self):
        self.client.force_login(self.player)
        for score in ('no', '1.5', 0, -1, MAX_SAFE_INTEGER + 1):
            self.assertEqual(self.client.post(f'/api/minigame/{self.ranking_key}/score', self.post_data(score)).status_code, 422)
        self.assertEqual(self.client.post('/api/minigame/no/score', self.post_data(1000)).status_code, 404)
        with patch.dict(RANKINGS, {self.ranking_key: replace(RANKINGS[self.ranking_key], accept_submissions=False)}):
            response = self.client.post(f'/api/minigame/{self.ranking_key}/score', self.post_data(1000))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'ranking_closed')
        for path in ('/api/minigame/no/rank', '/api/minigame/left-click/rank?sort=no', '/api/minigame/no/player/1', '/api/minigame/left-click/player/999999999'):
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.get('/api/minigame/left-click/rank', {'sort': 'flag-chord-b-v1'}).status_code, 422)
        self.assertEqual(self.client.get('/api/minigame/rankings/').status_code, 404)
        self.assertEqual(self.client.post(f'/api/minigame/{self.ranking_key}/score/', self.post_data(1000)).status_code, 404)

    def test_replay_follows_best_score_and_is_never_cached(self):
        first = self.submit(2000)['record']
        replacement = {'version': 1, 'cellSize': 32, 'initialBoard': '/////wAAAAA', 'events': [[0, 16, 144, 2]], 'specialEvents': []}
        for score in (2000, 3000):
            self.assertFalse(self.submit(score, replay=replacement)['improved'])
            first.refresh_from_db()
            self.assertEqual(unpack_replay(first.replay_archive), self.replay)
        self.assertTrue(self.submit(1000, replay=replacement)['improved'])
        first.refresh_from_db()
        self.assertEqual(unpack_replay(first.replay_archive), replacement)
        self.assertEqual(first.score, 1000)
        with CaptureQueriesContext(connection) as queries:
            self.cache.rebuild(self.ranking_key)
        self.assertEqual(len(queries), 1)
        self.assertNotIn('replay', queries[0]['sql'].lower())
        detail = json.loads(self.cache.client.hget(self.cache.detail_key(self.ranking_key), str(self.player.id)))
        self.assertEqual(detail, {'score': 1000, 'achieved_at': first.achieved_at.isoformat()})
        self.assertEqual(self.cache.client.zscore(self.cache.rank_key(self.ranking_key), str(self.player.id)), 1000)

    def test_replay_json_is_required_and_supports_all_games(self):
        self.client.force_login(self.player)
        url = f'/api/minigame/{self.ranking_key}/score'
        self.assertEqual(self.client.post(url, {'score': 1000}).status_code, 422)
        for replay in ('not json', '[]', 'null', '123'):
            self.assertEqual(self.client.post(url, {'score': 1000, 'replay': replay}).status_code, 422)
        recordings = {
            'left-click': self.replay,
            'multi-touch': {'version': 1, 'cellSize': 32, 'initialBoard': 'AAAAAP////8', 'events': [[0, 16, 16, 0, 0], [10, 32, 0, 1, 0]]},
            'flag-chord': {'version': 1, 'cellSize': 32, 'initialBoard': [[1, 1, 0], [1, 5, 2], [5, 1, 5], [5, 5, 7]], 'events': [], 'specialEvents': []},
            'missing-cell': {'version': 1, 'rounds': [{'board': 'gAAAAAAAAAA', 'target': [7, 7], 'timeMs': 100} for _ in range(10)]},
        }
        for game, replay in recordings.items():
            ranking_key = GAME_RANKINGS[game][0].key
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(f'/api/minigame/{ranking_key}/score', self.post_data(1000, replay))
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(unpack_replay(MiniGameBestScore.objects.get(player=self.player, ranking_key=ranking_key).replay_archive), replay)

    def test_public_replay_returns_stored_7z_without_gzip_or_redis(self):
        archive = pack_replay({**self.replay, 'events': [[index, index % 31, index % 47, 0] for index in range(1000)]})
        self.assertGreater(len(archive), 200)
        for game, rankings in GAME_RANKINGS.items():
            with self.subTest(game=game):
                ranking_key = rankings[0].key
                MiniGameBestScore.objects.create(player=self.player, ranking_key=ranking_key, score=1234, replay_archive=archive)
                with patch('minigame.services.MiniGameRankingCache') as cache, patch('minigame.services.pack_replay') as compress, self.assertNumQueries(1):
                    response = self.client.get(f'/api/minigame/{game}/replay', {'player': self.player.id, 'key': ranking_key.removeprefix(f'{game}-')}, HTTP_ACCEPT_ENCODING='gzip', HTTP_ORIGIN='http://localhost:5173')
                cache.assert_not_called()
                compress.assert_not_called()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, archive)
                self.assertEqual(response['Content-Type'], 'application/x-7z-compressed')
                self.assertEqual(response['Content-Encoding'], 'identity')
                self.assertEqual(response['Content-Length'], str(len(archive)))
                self.assertEqual(response['X-Minigame-Score'], '1234')
                self.assertIn('X-Minigame-Score', response['Access-Control-Expose-Headers'])
                self.assertIn('no-transform', response['Cache-Control'])

    def test_replay_missing_or_unknown_ranking_returns_404(self):
        MiniGameBestScore.objects.create(player=self.player, ranking_key=self.ranking_key, score=1000)
        for game, key, player in (('left-click', 'b-50-v1', self.player.id), ('left-click', 'b-50-v1', 999999999), ('left-click', 'no', self.player.id), ('no', 'b-50-v1', self.player.id)):
            response = self.client.get(f'/api/minigame/{game}/replay', {'player': player, 'key': key})
            self.assertEqual(response.status_code, 404)
        record = self.submit(500)['record']
        self.assertEqual(self.client.get('/api/minigame/left-click/replay', {'player': self.player.id, 'key': 'b-50-v1'}).content, record.replay_archive)
        for query in ({'player': self.player.id}, {'key': 'b-50-v1'}, {'player': 'invalid', 'key': 'b-50-v1'}):
            self.assertEqual(self.client.get('/api/minigame/left-click/replay', query).status_code, 422)

    def test_multi_touch_accepts_all_modes_and_caches_scores_without_replays(self):
        first_key = GAME_RANKINGS['multi-touch'][0].key
        self.assertFalse(self.player.has_realname())
        self.assertEqual(self.client.post(f'/api/minigame/{first_key}/score', self.post_data(1000)).status_code, 403)
        self.client.force_login(self.player)
        group = next(group for group in self.client.get('/api/minigame/rankings').json() if group['game'] == 'multi-touch')
        self.assertEqual(len(group['rankings']), 9)
        self.assertTrue(all(ranking['accept_submissions'] for ranking in group['rankings']))
        for ranking in GAME_RANKINGS['multi-touch']:
            rows, columns = {'b': (8, 8), 'i': (16, 16), 'e': (16, 30)}[ranking.level]
            replay = {'version': 1, 'cellSize': 32, 'initialBoard': 'A' * ((rows * columns + 5) // 6), 'events': [[0, 16, 16, 0, 0], [10, 32, 0, 1, 0]]}
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(f'/api/minigame/{ranking.key}/score', self.post_data(1000, replay))
            self.assertEqual(response.status_code, 200, response.content)
            self.assertTrue(response.json()['improved'])
            record = MiniGameBestScore.objects.get(player=self.player, ranking_key=ranking.key)
            self.assertEqual(unpack_replay(record.replay_archive), replay)
            detail = json.loads(self.cache.client.hget(self.cache.detail_key(ranking.key), str(self.player.id)))
            self.assertEqual(set(detail), {'score', 'achieved_at'})
            self.assertEqual(self.cache.client.zscore(self.cache.rank_key(ranking.key), self.player.id), 1000)
        response = self.client.get('/api/minigame/multi-touch/rank')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)
        records = response.json()['players'][0]['records']
        self.assertEqual(len(records), 9)
        self.assertTrue(all(record['score'] == 1000 for record in records.values()))
        self.player.is_banned = True
        self.player.save(update_fields=['is_banned'])
        self.assertEqual(self.client.post(f'/api/minigame/{first_key}/score', self.post_data(500)).status_code, 403)

    def test_groups_sort_columns_nulls_pagination_and_personal(self):
        other = self.make_player('minigame-other')
        empty_player = self.make_player('minigame-empty')
        for game, rankings in GAME_RANKINGS.items():
            for index, ranking in enumerate(rankings):
                MiniGameBestScore.objects.create(player=self.player, ranking_key=ranking.key, score=1000 + index, replay_archive=pack_replay(self.replay))
            MiniGameBestScore.objects.create(player=other, ranking_key=rankings[-1].key, score=500, replay_archive=pack_replay(self.replay))
            response = self.client.get(f'/api/minigame/{game}/rank', {'sort': rankings[-1].key})
            self.assertEqual(response.status_code, 200, response.content)
            ranking = response.json()
            self.assertEqual(ranking['count'], 2)
            self.assertEqual([row['player_id'] for row in ranking['players']], [other.id, self.player.id])
            self.assertEqual(list(ranking['players'][0]['records']), [ranking.key for ranking in rankings])
            self.assertEqual(ranking['players'][0]['records'][rankings[0].key], None)
            page = self.client.get(f'/api/minigame/{game}/rank', {'sort': rankings[-1].key, 'start': 1, 'end': 2}).json()
            self.assertEqual(page['players'][0]['rank'], 2)
            personal = self.client.get(f'/api/minigame/{game}/player/{self.player.id}').json()
            self.assertEqual(personal['records'][rankings[-1].key]['rank'], 2)
            empty = self.client.get(f'/api/minigame/{game}/player/{empty_player.id}').json()
            self.assertTrue(all(record is None for record in empty['records'].values()))
            with self.assertNumQueries(0):
                self.client.get(f'/api/minigame/{game}/rank')
            for start, end in ((0, 0), (1, 1), (10, 20), (2, -1)):
                empty = self.client.get(f'/api/minigame/{game}/rank', {'start': start, 'end': end}).json()
                self.assertEqual(empty['players'], [])
        definitions = self.client.get('/api/minigame/rankings').json()
        self.assertEqual([len(group['rankings']) for group in definitions], [9, 9, 2, 3])

    def test_empty_and_large_rankings_initialize_once(self):
        for size in (0, 1, 105):
            with self.subTest(size=size):
                self.cache.client.delete(*self.cache.keys)
                if size:
                    players = [self.make_player(f'size-{size}-{index}') for index in range(size)]
                    MiniGameBestScore.objects.bulk_create([MiniGameBestScore(player=player, ranking_key=self.ranking_key, score=1000, replay_archive=pack_replay(self.replay)) for player in players])
                count = MiniGameBestScore.objects.filter(ranking_key=self.ranking_key).count()
                self.assertEqual(get_ranking('left-click', self.ranking_key, 0, 100)['count'], count)
                with self.assertNumQueries(0):
                    result = get_ranking('left-click', self.ranking_key, 0, 100)
                self.assertEqual(len(result['players']), min(100, count))
                self.assertTrue(self.cache.client.exists(self.cache.ready_key(self.ranking_key)))
                response = self.client.get('/api/minigame/left-click/rank', {'start': -2, 'end': 999}).json()
                self.assertEqual(len(response['players']), min(100, count))

    def test_partial_upload_rebuild_delete_and_rollback(self):
        record = self.submit(1000)['record']
        self.assertFalse(self.cache.client.exists(self.cache.ready_key(self.ranking_key)))
        get_ranking('left-click', self.ranking_key, 0, 20)
        with self.captureOnCommitCallbacks(execute=True), transaction.atomic():
            submit_score(self.player, self.ranking_key, 500, self.replay)
            transaction.set_rollback(True)
        self.assertEqual(self.cache.client.zscore(self.cache.rank_key(self.ranking_key), self.player.id), 1000)
        output = StringIO()
        call_command('rebuild_minigame_ranks', ranking_key=self.ranking_key, stdout=output)
        self.assertIn(': 1', output.getvalue())
        with self.captureOnCommitCallbacks(execute=True):
            self.player.delete()
        self.assertFalse(MiniGameBestScore.objects.filter(pk=record.id).exists())
        with self.assertNumQueries(0):
            self.assertEqual(get_ranking('left-click', self.ranking_key, 0, 20), {'count': 0, 'players': []})
        self.assertIsNone(self.cache.client.hget(self.cache.detail_key(self.ranking_key), str(record.player_id)))

    def test_redis_failure_preserves_writes_and_batch_database_fallback(self):
        with patch('minigame.services.MiniGameRankingCache', side_effect=RedisConnectionError), self.assertLogs('minigame.services', 'ERROR'):
            self.submit(1000)
            self.submit(2000, GAME_RANKINGS['left-click'][1].key)
            with self.assertNumQueries(3), CaptureQueriesContext(connection) as queries:
                result = get_ranking('left-click', self.ranking_key, 0, 20)
            self.assertTrue(all('replay' not in query['sql'].lower() for query in queries))
            self.assertEqual(result['players'][0]['records'][self.ranking_key]['score'], 1000)
            with self.assertNumQueries(1), CaptureQueriesContext(connection) as queries:
                personal = get_player_scores('left-click', self.player.id)
            self.assertTrue(all('replay' not in query['sql'].lower() for query in queries))
            self.assertIsNone(personal['records'][self.ranking_key]['rank'])

    def test_descending_support(self):
        with patch.dict(RANKINGS, {self.ranking_key: replace(RANKINGS[self.ranking_key], order='desc')}):
            self.submit(1000)
            self.assertTrue(self.submit(2000)['improved'])
            other = self.make_player('descending')
            self.submit(1500, player=other)
            ranking = get_ranking('left-click', self.ranking_key, 0, 20)
            self.assertEqual(ranking['players'][0]['player_id'], self.player.id)

    @override_settings(RATELIMIT_ENABLE=True)
    def test_submission_limits_accounts_independently_of_ip(self):
        address = f'2001:db8::{uuid4().hex[:4]}:{uuid4().hex[:4]}'
        url = f'/api/minigame/{self.ranking_key}/score'
        with patch('django_ratelimit.core.time.time', return_value=1800000000):
            for index, submissions in enumerate((60, 60, 1)):
                player = self.player if index == 0 else self.make_player(f'submit-rate-{index}')
                self.client.force_login(player)
                for _ in range(submissions):
                    response = self.client.post(url, self.post_data(1000), REMOTE_ADDR=address)
                    self.assertEqual(response.status_code, 200, response.content)
                if index == 0:
                    response = self.client.post(url, self.post_data(1000), REMOTE_ADDR='2001:db8::1')
                    self.assertEqual(response.status_code, 429)

    @override_settings(RATELIMIT_ENABLE=True)
    def test_replay_query_rate_limit(self):
        self.submit(1000)
        address = f'2001:db8::{uuid4().hex[:4]}:{uuid4().hex[:4]}'
        with patch('django_ratelimit.core.time.time', return_value=1800000000):
            statuses = [self.client.get('/api/minigame/left-click/replay', {'player': self.player.id, 'key': 'b-50-v1'}, REMOTE_ADDR=address).status_code for _ in range(6)]
        self.assertEqual(statuses, [200] * 5 + [429])

    @override_settings(RATELIMIT_ENABLE=True)
    def test_real_query_rate_limit(self):
        address = f'2001:db8::{uuid4().hex[:4]}:{uuid4().hex[:4]}'
        with patch('django_ratelimit.core.time.time', return_value=1800000000):
            statuses = [self.client.get('/api/minigame/rankings', REMOTE_ADDR=address).status_code for _ in range(6)]
        self.assertEqual(statuses, [200] * 5 + [429])
