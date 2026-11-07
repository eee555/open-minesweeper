from datetime import timedelta
from io import StringIO
import json
from unittest.mock import patch

from django.core.management import call_command
from django.db import transaction
from django.test import override_settings, SimpleTestCase, TestCase
from django.utils import timezone

from config.text_choices import MS_TextChoices
from msuser.models import UserMS
from userprofile.models import UserProfile
from userprofile.services import has_sub200_expert_video
from videomanager.models import ExpandVideoModel, VideoModel
from .cache import SpeedRankingCache
from .services import best_candidate
from .utils import encode_zset_score, is_better, MAX_RECORD_UNITS, RANK_STATS, RANKING_NAMES, SCORE_TIME_FACTOR, TIME_STATS, TOTAL_PARTS
from ..cache import cache
from ..pb.cache import PBRankingCache
from ..services import add_videos_to_speed_ranks, remove_videos_from_speed_ranks
from ..utils import upload_microseconds


class SpeedRankingScoreTests(SimpleTestCase):
    def test_score_precision_order_and_admission_boundaries(self):
        for stat in RANK_STATS:
            with self.subTest(stat=stat):
                maximum = MAX_RECORD_UNITS * (3 if stat in TOTAL_PARTS else 1)
                value = maximum if stat in TIME_STATS else maximum / 10000
                for upload in (0, SCORE_TIME_FACTOR - 1):
                    encoded = encode_zset_score(stat, value, upload * 60_000_000)
                    self.assertLess(abs(encoded), 2 ** 53)
                    self.assertEqual(int(float(encoded)), encoded)
                    self.assertEqual(float(encoded) + 1, encoded + 1)
                step = 1 if stat in TIME_STATS else 0.0001
                better, worse = (value - step, value) if stat in TIME_STATS else (value, value - step)
                self.assertLess(encode_zset_score(stat, better, (SCORE_TIME_FACTOR - 1) * 60_000_000), encode_zset_score(stat, worse, 0))
                for invalid in (-1, value + step / 10, float('inf'), float('nan')):
                    self.assertIsNone(encode_zset_score(stat, invalid, 0))
                self.assertIsNone(encode_zset_score(stat, value, SCORE_TIME_FACTOR * 60_000_000))
        self.assertEqual(encode_zset_score('bb', 1.23445, 0), -12345 * SCORE_TIME_FACTOR)
        self.assertEqual(encode_zset_score('bb', 1.23441, 1), encode_zset_score('bb', 1.23442, 2))
        self.assertTrue(is_better('bb', {'value': 1.23442, 'upload': 2}, {'bb': 1.23441, '_uploads': {'bb': 1}}))


@override_settings(RATELIMIT_ENABLE=False)
class SpeedRankingTests(TestCase):
    def setUp(self):
        pb = PBRankingCache()
        pb.flush()
        self.addCleanup(pb.flush)
        for ranking_name in RANKING_NAMES:
            ranking = SpeedRankingCache(ranking_name, stats=RANK_STATS)
            ranking.flush()
            self.addCleanup(ranking.flush)
        self.user = self.create_user('speed')

    def create_user(self, name):
        return UserProfile.objects.create_user(username=name, email=f'{name}@example.com', userms=UserMS.objects.create())

    def create_video(self, **kwargs):
        fields = {'player': self.user, 'video': ExpandVideoModel.objects.create(identifier='speed'), 'file': 'videos/speed.evf', 'software': 'e', 'state': MS_TextChoices.State.OFFICIAL, 'level': 'b', 'mode': '00', 'bv': 4, 'timems': 1000, 'right_ce': 0}
        fields.update(kwargs)
        with self.captureOnCommitCallbacks(execute=True):
            return VideoModel.objects.create(**fields)

    def save_video(self, video, **fields):
        for field, value in fields.items():
            setattr(video, field, value)
        with self.captureOnCommitCallbacks(execute=True):
            video.save(update_fields=fields)

    def record(self, ranking_name='saolei', player=None):
        response = self.client.get(f'/api/speedranking/player/{(player or self.user).id}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()[ranking_name]

    def test_player_api_returns_both_rankings_and_ranks_in_one_pipeline(self):
        for ranking_name in RANKING_NAMES:
            self.assertEqual(self.record(ranking_name)['ranks'], dict.fromkeys(RANK_STATS))
        standard = self.create_video(timems=2000, right_ce=1)
        nf = self.create_video(timems=3000)
        other = self.create_user('faster')
        self.create_video(player=other, timems=1000)
        with self.assertNumQueries(0), patch.object(cache, 'pipeline', wraps=cache.pipeline) as pipeline:
            response = self.client.get(f'/api/speedranking/player/{self.user.id}')
            self.assertEqual(response.status_code, 200, response.content)
            pipeline.assert_called_once_with()
        records = response.json()
        self.assertEqual(set(records), set(RANKING_NAMES))
        for ranking_name, video in (('saolei', standard), ('saolei_nf', nf)):
            self.assertEqual(records[ranking_name]['bt_id'], video.id)
            self.assertEqual(records[ranking_name]['bt'], video.timems)
            self.assertEqual(records[ranking_name]['ranks'], {'bt': 2, 'bb': 2, 'it': None, 'ib': None, 'et': None, 'eb': None, 'sumt': 2, 'sumb': 2})

    def test_thresholds_partial_totals_and_independent_nf(self):
        beginner = self.create_video(bv=2, right_ce=None)
        record = self.record()
        self.assertEqual(record['bt_id'], beginner.id)
        self.assertIsNone(record['bb'])
        self.assertEqual(record['sumt'], 1000 + 2 * 999999)
        self.assertEqual(record['sumb'], 0)
        self.assertIsNone(self.record('saolei_nf')['bt'])
        self.create_video(bv=4, timems=2000)
        self.create_video(level='i', bv=29, timems=1000)
        self.create_video(level='e', bv=99, timems=1000)
        record = self.record()
        self.assertEqual(record['bb'], 2)
        self.assertIsNone(record['it'])
        self.assertIsNone(record['et'])
        self.assertEqual(self.record('saolei_nf')['bt'], 2000)
        self.create_video(level='i', bv=30, timems=10000)
        self.create_video(level='e', bv=100, timems=100000)
        self.assertEqual(self.record()['sumt'], 111000)
        self.assertEqual(self.record()['sumb'], 6)

    def test_upload_time_breaks_ties_not_timems(self):
        older = self.create_video(bv=8, timems=2000)
        self.save_video(older, upload_time=timezone.now() - timedelta(minutes=2))
        newer = self.create_video(bv=4, timems=1000)
        self.assertEqual(self.record()['bb_id'], older.id)
        self.save_video(newer, upload_time=older.upload_time - timedelta(days=1))
        self.assertEqual(self.record()['bb_id'], newer.id)
        self.save_video(newer, upload_time=timezone.now())
        self.assertEqual(self.record()['bb_id'], older.id)
        other = self.create_user('other')
        self.create_video(player=other, bv=4, timems=1000)
        response = self.client.get('/api/speedranking/rank', {'stat': 'bb', 'start': 0, 'end': 1})
        self.assertEqual(response.json()['count'], 2)
        self.assertEqual(response.json()['players'][0]['player_id'], self.user.id)

    def test_personal_best_keeps_upload_precision_when_redis_scores_tie(self):
        minute = timezone.now().replace(second=0, microsecond=0)
        first = self.create_video(timems=100000)
        second = self.create_video(timems=100000)
        self.save_video(first, upload_time=minute + timedelta(seconds=50))
        for fields, expected in (
            ({'upload_time': minute + timedelta(seconds=55)}, first),
            ({'upload_time': first.upload_time - timedelta(microseconds=1)}, second),
        ):
            self.save_video(second, **fields)
            expected.refresh_from_db()
            self.assertEqual(self.record()['bb'], expected.bvs)
            self.assertEqual(self.record()['sumb'], expected.bvs)
            self.assertEqual(self.record()['bb_id'], expected.id)
            self.assertEqual(best_candidate(self.user.id, 'saolei', 'bb')['id'], expected.id)
            call_command('rebuild_speed_ranks', stdout=StringIO())
            self.assertEqual(self.record()['bb_id'], expected.id)
            self.assertEqual(cache.zscore(SpeedRankingCache('saolei').rank_key('bb'), self.user.id), encode_zset_score('bb', 0.04, upload_microseconds(minute)))

    def test_over_limit_records_stay_in_hash_and_totals_rank_independently(self):
        video = self.create_video()
        self.create_video(level='i', bv=30, timems=1000)
        for bv, timems, ranked in (
            (200, 1000, {'bt', 'sumt', 'sumb'}),
            (400, 1000, {'bt', 'sumt'}),
            (4, 1000000, {'bb', 'sumt', 'sumb'}),
            (4, 3000000, {'bb', 'sumb'}),
            (4, 999999, {'bt', 'bb', 'sumt', 'sumb'}),
        ):
            with self.subTest(bv=bv, timems=timems):
                self.save_video(video, bv=bv, timems=timems)
                video.refresh_from_db()
                for rebuild in (False, True):
                    if rebuild:
                        call_command('rebuild_speed_ranks', stdout=StringIO())
                    for ranking_name in RANKING_NAMES:
                        record = self.record(ranking_name)
                        self.assertEqual((record['bt'], record['bb']), (video.timems, video.bvs))
                        self.assertEqual((record['bt_id'], record['bb_id']), (video.id, video.id))
                        self.assertEqual(record['sumt'], video.timems + 1000 + 999999)
                        self.assertEqual(record['sumb'], video.bvs + 30)
                        for stat in ('bt', 'bb', 'sumt', 'sumb'):
                            self.assertEqual(record['ranks'][stat], 1 if stat in ranked else None)
                            response = self.client.get('/api/speedranking/rank', {'ranking_name': ranking_name, 'stat': stat})
                            self.assertEqual(response.status_code, 200)
                            self.assertEqual(response.json()['count'], int(stat in ranked))

    def test_worsening_and_deletion_backfill_only_held_records(self):
        first = self.create_video(timems=1000)
        backup = self.create_video(timems=2000)
        with patch('speedranking.saolei.services.best_candidate', wraps=best_candidate) as best:
            self.save_video(backup, timems=3000)
            best.assert_not_called()
        self.save_video(first, timems=4000)
        self.assertEqual(self.record()['bt_id'], backup.id)
        self.assertEqual(self.record()['bb_id'], backup.id)
        with self.captureOnCommitCallbacks(execute=True):
            backup.delete()
        self.assertEqual(self.record()['bt_id'], first.id)
        with self.captureOnCommitCallbacks(execute=True):
            first.delete()
        self.assertIsNone(self.record()['bt'])
        self.assertEqual(self.client.get('/api/speedranking/rank').json()['count'], 0)

    def test_category_changes_and_qualification(self):
        video = self.create_video()
        other = self.create_user('newowner')
        self.save_video(video, player=other, level='e', bv=100, timems=199999, right_ce=1)
        self.assertIsNone(self.record()['bt'])
        self.assertEqual(self.record(player=other)['et_id'], video.id)
        self.assertIsNone(self.record('saolei_nf', other)['et'])
        with self.assertNumQueries(0):
            self.assertTrue(has_sub200_expert_video(other))
        for fields in ({'timems': 200000}, {'bv': 99}, {'mode': MS_TextChoices.Mode.JSW}, {'state': MS_TextChoices.State.IDENTIFIER}, {'ongoing_tournament': True}):
            with self.subTest(fields=fields):
                self.save_video(video, timems=199999, bv=100, mode='00', state=MS_TextChoices.State.OFFICIAL, ongoing_tournament=False)
                self.save_video(video, **fields)
                self.assertFalse(has_sub200_expert_video(other))

    def test_bulk_add_and_remove_rebuild_affected_records(self):
        backup = self.create_video(timems=2000)
        video = self.create_video(state=MS_TextChoices.State.IDENTIFIER)
        videos = VideoModel.objects.filter(pk=video.pk)
        with self.captureOnCommitCallbacks(execute=True):
            videos.update(state=MS_TextChoices.State.OFFICIAL)
            add_videos_to_speed_ranks(videos)
        self.assertEqual(self.record()['bt_id'], video.id)
        with patch('speedranking.saolei.services.best_candidate', wraps=best_candidate) as best:
            with self.captureOnCommitCallbacks(execute=True):
                videos.update(state=MS_TextChoices.State.IDENTIFIER)
                remove_videos_from_speed_ranks(videos)
            self.assertEqual(best.call_count, 2)
        self.assertEqual(self.record()['bt_id'], backup.id)
        self.assertEqual(self.record('saolei_nf')['bt_id'], backup.id)

    def test_rollback_does_not_write_cache(self):
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(ValueError), transaction.atomic():
                VideoModel.objects.create(player=self.user, video=ExpandVideoModel.objects.create(), file='rollback.evf', software='e', state=MS_TextChoices.State.OFFICIAL, level='b', bv=4, timems=1000)
                raise ValueError('rollback')
        self.assertIsNone(self.record()['bt'])

    def test_rebuild_replaces_stale_entries_and_api_reads_only_redis(self):
        video = self.create_video()
        SpeedRankingCache('saolei', stats=RANK_STATS).flush()
        with self.assertNumQueries(0):
            self.assertIsNone(self.record()['bt'])
        call_command('rebuild_speed_ranks', '--ranking-name', 'saolei', batch_size=1, stdout=StringIO())
        self.assertEqual(self.record()['bt_id'], video.id)
        with patch('speedranking.saolei.services._add_videos', side_effect=ValueError('failed')):
            with self.assertRaises(ValueError):
                call_command('rebuild_speed_ranks', stdout=StringIO())
        self.assertEqual(self.record()['bt_id'], video.id)
        VideoModel.objects.filter(pk=video.pk).update(state=MS_TextChoices.State.IDENTIFIER)
        call_command('rebuild_speed_ranks', stdout=StringIO())
        self.assertIsNone(self.record()['bt'])
        self.assertEqual(self.client.get('/api/speedranking/rank', {'ranking_name': 'invalid'}).status_code, 422)
        self.assertEqual(self.client.get('/api/speedranking/rank', {'stat': 'invalid'}).status_code, 422)

    def test_admin_rebuild_repairs_one_record_and_missing_index(self):
        first = self.create_video(timems=1000)
        backup = self.create_video(timems=2000)
        VideoModel.objects.filter(pk=first.pk).update(timems=3000)
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)
        payload = {'player_id': self.user.id, 'ranking_name': 'saolei', 'stat': 'bt'}
        response = self.client.post('/api/speedranking/admin/rebuild_record', payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual((response.json()['bt'], response.json()['bt_id']), (2000, backup.id))
        self.assertEqual(response.json()['bb_id'], first.id)
        self.assertEqual(response.json()['sumt'], 2000 + 2 * 999999)
        self.assertEqual(self.record('saolei_nf')['bt_id'], first.id)
        ranking = SpeedRankingCache('saolei')
        cache.zrem(ranking.rank_key('bt'), self.user.id)
        response = self.client.post('/api/speedranking/admin/rebuild_record', payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.record()['ranks']['bt'], 1)
        VideoModel.objects.filter(player=self.user).update(state=MS_TextChoices.State.IDENTIFIER)
        response = self.client.post('/api/speedranking/admin/rebuild_record', payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(response.json()['bt'])
        self.assertIsNone(response.json()['bt_id'])
        self.assertIsNone(self.record()['ranks']['bt'])

    def test_admin_rebuild_totals_uses_cached_parts(self):
        self.create_video(right_ce=1)
        intermediate = self.create_video(level='i', bv=30, timems=10000)
        expert = self.create_video(level='e', bv=100, timems=100000)
        ranking = SpeedRankingCache('saolei_nf')
        record = ranking.get_record(self.user.id)
        record['sumt'] = 0
        record['sumb'] = 0
        cache.hset(ranking.detail_key, self.user.id, json.dumps(record))
        VideoModel.objects.filter(player=self.user).update(state=MS_TextChoices.State.IDENTIFIER)
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)
        payload = {'player_id': self.user.id, 'ranking_name': 'saolei_nf', 'stat': 'sumt'}
        response = self.client.post('/api/speedranking/admin/rebuild_record', payload)
        self.assertEqual(response.status_code, 200, response.content)
        record = response.json()
        self.assertEqual((record['it_id'], record['et_id']), (intermediate.id, expert.id))
        self.assertIsNone(record['bt'])
        self.assertEqual(record['sumt'], 999999 + 10000 + 100000)
        payload['stat'] = 'sumb'
        response = self.client.post('/api/speedranking/admin/rebuild_record', payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['sumb'], 4)
        self.assertIsNone(response.json()['bb'])
        self.assertEqual(response.json()['sumt'], record['sumt'])

    def test_admin_rebuild_requires_staff_and_valid_parameters(self):
        payload = {'player_id': self.user.id, 'ranking_name': 'saolei', 'stat': 'bt'}
        url = '/api/speedranking/admin/rebuild_record'
        self.assertEqual(self.client.post(url, payload).status_code, 403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(url, payload).status_code, 403)
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        for invalid in ({'ranking_name': 'invalid'}, {'stat': 'invalid'}, {'player_id': 'invalid'}):
            self.assertEqual(self.client.post(url, {**payload, **invalid}).status_code, 422)
        self.assertEqual(self.client.post(url, {**payload, 'player_id': self.user.id + 1000}).status_code, 404)
        for ranking_name in RANKING_NAMES:
            for stat in RANK_STATS:
                response = self.client.post(url, {**payload, 'ranking_name': ranking_name, 'stat': stat})
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()['player_id'], self.user.id)
                self.assertEqual(response.json()[stat], {'sumt': 2999997, 'sumb': 0}.get(stat))

    def test_deletion_shares_standard_and_nf_backfill_queries(self):
        for case, backup_modes, expected_queries in (
            ('empty', (), 1), ('nf', (0,), 1), ('mixed', (1, 0), 2),
        ):
            with self.subTest(case=case):
                player = self.create_user(f'backfill-{case}')
                held = self.create_video(player=player, bv=2)
                backups = [self.create_video(player=player, bv=2, right_ce=right_ce, timems=2000 + index * 1000) for index, right_ce in enumerate(backup_modes)]
                with patch('speedranking.saolei.services.best_candidate', wraps=best_candidate) as best:
                    with self.captureOnCommitCallbacks(execute=True):
                        held.delete()
                    self.assertEqual(best.call_count, expected_queries)
                standard = backups[0].id if backups else None
                nf = next((video.id for video in backups if video.right_ce == 0), None)
                self.assertEqual(self.record('saolei', player)['bt_id'], standard)
                self.assertEqual(self.record('saolei_nf', player)['bt_id'], nf)
