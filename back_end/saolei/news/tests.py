import json
import time
from unittest.mock import patch

from django.test import override_settings, SimpleTestCase

from effranking.news import prepare_news, publish_news
from effranking.nf_ioe.cache import NFIOERankingCache
from effranking.services import _write_with_news
from effranking.thrp.cache import ThrpRankingCache
from speedranking.pb.cache import PBRankingCache
from speedranking.services import _news_targets, _publish_lsf_news, _publish_pb_news, _write_records
from speedranking.top.cache import TopRankingCache
from speedranking.top.services import complete_update
from speedranking.top.utils import SOFT_FIELDS
from .cache import ALL_KEY, cache, EVENTS_KEY, flush, index_key, publish, read_events, TTL_SECONDS
from .services import emit


def soft(lsf):
    return {field: lsf for field in SOFT_FIELDS}


def thrp_part(value, video_id):
    return {'value': value, 'video_id': video_id, 'upload_time': '2026-01-01T00:00:00+00:00'}


def ioe_part(value, video_id, timems=10000):
    return {'value': value, 'video_id': video_id, 'timems': timems}


def thrp_record(b=None, i=None, e=None, e_nf=None):
    return {'b': b, 'i': i, 'e': e, 'e_nf': e_nf}


def ioe_record(b=None, i=None, e=None):
    return {'b': b, 'i': i, 'e': e}


class NewsCacheTests(SimpleTestCase):
    def setUp(self):
        flush()
        self.addCleanup(flush)

    def test_publish_and_read_by_category(self):
        publish('pb', 1, {'field': 'std:b:10'})
        publish('lsf', 2, {'video_id': 3})
        self.assertEqual(len(read_events()), 2)
        self.assertEqual(len(read_events('pb')), 1)
        self.assertEqual(read_events('lsf')[0]['payload']['video_id'], 3)
        self.assertEqual(read_events('lsf')[0]['player_id'], 2)

    def test_events_are_newest_first(self):
        first = publish('pb', 1, {'n': 1})
        time.sleep(0.002)
        second = publish('pb', 2, {'n': 2})
        self.assertEqual([event['id'] for event in read_events()], [second['id'], first['id']])

    @patch('news.cache.KEEP_LATEST_EVENTS', 3)
    def test_expired_events_are_removed_from_hash(self):
        for index in range(3):
            publish('pb', index, {'n': index})
        expired_id = read_events(limit=10)[-1]['id']
        cache.zadd(ALL_KEY, {expired_id: (time.time() - TTL_SECONDS - 60) * 1000})
        cache.zadd(index_key('pb'), {expired_id: (time.time() - TTL_SECONDS - 60) * 1000})
        publish('pb', 9, {'n': 9})
        self.assertIsNone(cache.hget(EVENTS_KEY, expired_id))
        self.assertEqual(cache.hlen(EVENTS_KEY), 3)

    @patch('news.cache.time.time')
    @patch('news.cache.KEEP_LATEST_EVENTS', 3)
    def test_overflow_keeps_events_when_within_ttl(self, mocked_time):
        now = 1_000_000_000
        mocked_time.return_value = now
        for index in range(5):
            publish('pb', index, {'n': index})
        # 5 条都发布于 now，彼此不超时，因此即使超出 KEEP=3 也全部保留
        self.assertEqual(cache.hlen(EVENTS_KEY), 5)

    def test_eff_events_get_their_own_index(self):
        publish('eff', 3, {'field': 'thrp:b'})
        self.assertEqual(len(read_events()), 1)
        self.assertEqual(read_events('eff')[0]['payload']['field'], 'thrp:b')
        self.assertEqual(read_events('pb'), [])

    def test_emit_writes_through_signal(self):
        emit('pb', 7, {'field': 'std:b:10'})
        events = read_events('pb')
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['player_id'], 7)
        self.assertEqual(events[0]['payload']['field'], 'std:b:10')


@override_settings(RATELIMIT_ENABLE=False)
class NewsApiTests(SimpleTestCase):
    def setUp(self):
        flush()
        self.addCleanup(flush)

    def test_events_endpoint_filters_by_category(self):
        publish('pb', 1, {'field': 'std:b:10'})
        publish('lsf', 2, {'video_id': 3})
        response = self.client.get('/api/news/events?category=pb')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['category'], 'pb')
        self.assertEqual(data[0]['payload'], {'field': 'std:b:10'})

    def test_events_endpoint_filters_eff_category(self):
        publish('eff', 3, {'field': 'nf_ioe:e'})
        response = self.client.get('/api/news/events?category=eff')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['category'], 'eff')
        self.assertEqual(data[0]['payload'], {'field': 'nf_ioe:e'})


class PBNewsTests(SimpleTestCase):
    def setUp(self):
        flush()
        self.addCleanup(flush)
        ranking = PBRankingCache()
        ranking.flush()
        self.addCleanup(ranking.flush)

    @patch('speedranking.services.emit')
    def test_only_top_ten_pb_refreshes_publish_news(self, mocked_emit):
        ranking = PBRankingCache()
        cache.hset(ranking.player_key(1), 'std:b:10', json.dumps({'timems': 9000, 'video_id': 20, 'rank': 3}))
        cache.hset(ranking.player_key(2), 'std:b:10', json.dumps({'timems': 9000, 'video_id': 21, 'rank': 15}))
        old_pb = {
            1: {'std:b:10': {'timems': 12000, 'video_id': 10, 'rank': 8}},
            2: {'std:b:10': {'timems': 12000, 'video_id': 11, 'rank': 20}},
        }
        changes = {(1, 'std:b:10'): (20, 0), (2, 'std:b:10'): (21, 0)}
        _publish_pb_news(old_pb, changes, ranking, {1: 20, 2: 21})
        self.assertEqual(mocked_emit.call_count, 1)
        category, player_id, payload = mocked_emit.call_args.args
        self.assertEqual((category, player_id), ('pb', 1))
        self.assertEqual(payload['old']['rank'], 8)
        self.assertEqual(payload['new']['rank'], 3)
        self.assertEqual(payload['new']['video_id'], 20)

    @patch('speedranking.services.emit')
    def test_unchanged_pb_does_not_publish_news(self, mocked_emit):
        ranking = PBRankingCache()
        record = {'timems': 9000, 'video_id': 20, 'rank': 3}
        cache.hset(ranking.player_key(1), 'std:b:10', json.dumps(record))
        _publish_pb_news({1: {'std:b:10': record}}, {(1, 'std:b:10'): (20, 0)}, ranking, {1: 20})
        mocked_emit.assert_not_called()

    @patch('speedranking.services.emit')
    def test_pb_news_only_covers_targeted_players(self, mocked_emit):
        ranking = PBRankingCache()
        cache.hset(ranking.player_key(1), 'std:b:10', json.dumps({'timems': 9000, 'video_id': 20, 'rank': 3}))
        _publish_pb_news({1: {'std:b:10': {'timems': 12000, 'video_id': 10, 'rank': 8}}}, {(1, 'std:b:10'): (20, 0)}, ranking, {2: 21})
        mocked_emit.assert_not_called()

    @patch('speedranking.services.emit')
    def test_pb_progress_without_rank_change_publishes(self, mocked_emit):
        # 成绩进步（timems 更优）但名次未变，只要名次仍在范围内就推送 PB 新闻。
        ranking = PBRankingCache()
        cache.hset(ranking.player_key(1), 'std:b:10', json.dumps({'timems': 9000, 'video_id': 20, 'rank': 3}))
        old_pb = {1: {'std:b:10': {'timems': 12000, 'video_id': 10, 'rank': 3}}}
        _publish_pb_news(old_pb, {(1, 'std:b:10'): (20, 0)}, ranking, {1: 20})
        mocked_emit.assert_called_once()
        category, player_id, payload = mocked_emit.call_args.args
        self.assertEqual((category, player_id), ('pb', 1))
        self.assertEqual(payload['old']['timems'], 12000)
        self.assertEqual(payload['new']['timems'], 9000)
        self.assertEqual(payload['new']['rank'], 3)


class LSFNewsTests(SimpleTestCase):
    def setUp(self):
        flush()
        self.addCleanup(flush)
        ranking = TopRankingCache()
        ranking.flush()
        self.addCleanup(ranking.flush)
        pb = PBRankingCache()
        pb.flush()
        self.addCleanup(pb.flush)

    @patch('speedranking.services.emit')
    @patch('speedranking.top.services.soft_refresh_requested.send')
    @patch('speedranking.top.services.soft_values', side_effect=[soft(100), soft(200)])
    def test_write_records_publishes_snapshots_before_and_after(self, _soft, _send, mocked_emit):
        ranking = TopRankingCache()
        cache.zadd(ranking.soft_key('lsf'), {'1': 100})
        previous = ({}, {}, {}, {1: {}})
        records = {1: {'std:bt': {'videos': [{'value': 1000, 'video_id': 9}]}}}
        _write_records(previous, {}, {}, {}, records, news_targets={1: [9]})
        self.assertEqual(mocked_emit.call_count, 1)
        category, player_id, payload = mocked_emit.call_args.args
        self.assertEqual((category, player_id), ('lsf', 1))
        self.assertEqual(payload['video_id'], 9)
        self.assertEqual(payload['video_ids'], [9])
        self.assertEqual(payload['old'], {'lsf': 100, 'rank': 1})
        self.assertEqual(payload['new'], {'lsf': 200, 'rank': 1})

    @patch('speedranking.services.emit')
    @patch('speedranking.top.services.soft_refresh_requested.send')
    def test_remove_path_publishes_no_news(self, _send, mocked_emit):
        previous = ({}, {}, {}, {1: {}})
        records = {1: {'std:bt': {'videos': [{'value': 1000, 'video_id': 9}]}}}
        _write_records(previous, {}, {}, {}, records)
        mocked_emit.assert_not_called()

    @patch('speedranking.services.emit')
    def test_changes_outside_top_36_publish_no_news(self, mocked_emit):
        _publish_lsf_news({1: [42]}, {1: (100.0, 40)}, {1: (200.0, 40)})
        mocked_emit.assert_not_called()

    @patch('speedranking.top.services.soft_refresh_requested.send')
    def test_forced_admin_rebuild_takes_no_snapshot(self, _send):
        records = {1: {'std:bt': {'videos': [{'value': 1000, 'video_id': 9}]}}}
        self.assertEqual(complete_update({1: {}}, records, set(), force=True), {})


class NewsTargetsTests(SimpleTestCase):
    def test_each_change_uses_its_own_trigger_video(self):
        old_top = {
            1: {'std:bt': {'videos': [{'video_id': 10, 'value': 1000}]}},
            2: {'std:bt': {'videos': [{'video_id': 20, 'value': 1000}]}},
            3: {'std:bt': {'videos': [{'video_id': 30, 'value': 1000}]}},
        }
        top_records = {
            1: {'std:bt': {'videos': [{'video_id': 91, 'value': 900}, {'video_id': 10, 'value': 1000}]}},
            2: {'std:bt': {'videos': [{'video_id': 92, 'value': 900}, {'video_id': 20, 'value': 1000}]}},
            3: old_top[3],
        }
        targets = _news_targets(old_top, top_records, {(3, 'std:b:10'): (93, 0)})
        self.assertEqual(targets, {1: [91], 2: [92], 3: [93]})

    def test_unchanged_players_are_not_news_targets(self):
        old_top = {1: {'std:bt': {'videos': [{'video_id': 10, 'value': 1000}]}}}
        self.assertEqual(_news_targets(old_top, old_top, {}), {})

    def test_multiple_new_videos_all_in_targets(self):
        # 同玩家同批新增 91、92 两条录像，triggers 含两条，全部保留为 video_ids
        # （升序），最小者 91 仍作为主链接 video_id；见 _news_targets 文档。
        old_top = {1: {'std:bt': {'videos': [{'video_id': 10, 'value': 1000}]}}}
        top_records = {1: {'std:bt': {'videos': [{'video_id': 10, 'value': 1000}, {'video_id': 91, 'value': 900}, {'video_id': 92, 'value': 1100}]}}}
        self.assertEqual(_news_targets(old_top, top_records, {}), {1: [91, 92]})

    def test_pb_progress_without_rank_change_is_targeted(self):
        # 玩家仅在 PB 小榜进步（成绩更优、名次不变），top 大榜（LSF）未变，
        # 因而不会出现在 top_records 中；仍应被纳入 targets，使新闻在名次范围内推送。
        old_top = {1: {'std:bt': {'videos': [{'video_id': 10, 'value': 1000}]}}}
        top_records = {}
        pb_changes = {(1, 'std:b:10'): (11, 0)}
        self.assertEqual(_news_targets(old_top, top_records, pb_changes), {1: [11]})


class LSFNewsPublishTests(SimpleTestCase):
    @patch('speedranking.services.emit')
    def test_each_lsf_change_publishes_its_own_event(self, mocked_emit):
        _publish_lsf_news({1: [91], 2: [92]}, {1: (100.0, 5), 2: (200.0, 10)}, {1: (150.0, 3), 2: (250.0, 8)})
        self.assertEqual(mocked_emit.call_count, 2)
        payloads = [item.args[2] for item in mocked_emit.call_args_list]
        self.assertEqual([payload['video_id'] for payload in payloads], [91, 92])
        self.assertEqual([payload['video_ids'] for payload in payloads], [[91], [92]])
        self.assertEqual([(payload['old']['rank'], payload['new']['rank']) for payload in payloads], [(6, 4), (11, 9)])


class EffNewsTests(SimpleTestCase):
    def setUp(self):
        for ranking in (ThrpRankingCache(), NFIOERankingCache()):
            ranking.flush()
            self.addCleanup(ranking.flush)

    def test_only_improved_stats_become_candidates(self):
        ranking = ThrpRankingCache()
        previous = {1: thrp_record(b=thrp_part(0.9, 10))}
        records = {1: thrp_record(b=thrp_part(1.0, 11))}
        self.assertEqual([item[2] for item in prepare_news([(ranking, previous, records)])], ['b', 'sum'])

    def test_worse_records_publish_no_news(self):
        ranking = ThrpRankingCache()
        previous = {1: thrp_record(b=thrp_part(1.0, 10))}
        records = {1: thrp_record(b=thrp_part(0.9, 11))}
        self.assertEqual(prepare_news([(ranking, previous, records)]), [])

    def test_all_efficiency_rankings_are_covered(self):
        thrp = ThrpRankingCache()
        ioe = NFIOERankingCache()
        previous_thrp = {1: thrp_record(e_nf={'value': 1.0, 'video_ids': [20]})}
        records_thrp = {1: thrp_record(e_nf={'value': 1.0, 'video_ids': [20, 21]})}
        previous_ioe = {2: ioe_record()}
        records_ioe = {2: ioe_record(e=ioe_part(1.0, 30))}
        candidates = prepare_news([(thrp, previous_thrp, records_thrp), (ioe, previous_ioe, records_ioe)])
        self.assertEqual([(item[0].ranking_name, item[2]) for item in candidates], [('thrp', 'e_nf'), ('nf_ioe', 'e'), ('nf_ioe', 'sum')])

    def test_sum_is_derived_and_has_no_replay_link(self):
        ranking = ThrpRankingCache()
        previous = {1: thrp_record()}
        records = {1: thrp_record(b=thrp_part(1.0, 11))}
        totals = [item for item in prepare_news([(ranking, previous, records)]) if item[2] == 'sum']
        self.assertEqual(len(totals), 1)
        self.assertEqual((totals[0][3], totals[0][4], totals[0][5], totals[0][6]), (None, None, 1.0, None))

    @patch('effranking.news.emit')
    def test_payload_follows_pb_format(self, mocked_emit):
        publish_news([(ThrpRankingCache(), 1, 'b', 0.9, 10, 1.0, 11)], [6], [2])
        category, player_id, payload = mocked_emit.call_args.args
        self.assertEqual((category, player_id), ('eff', 1))
        self.assertEqual(payload['field'], 'thrp:b')
        self.assertEqual(payload['old'], {'value': 0.9, 'video_id': 10, 'rank': 7})
        self.assertEqual(payload['new'], {'value': 1.0, 'video_id': 11, 'rank': 3})

    @patch('effranking.news.emit')
    def test_first_record_has_no_old_value(self, mocked_emit):
        publish_news([(NFIOERankingCache(), 2, 'e', None, None, 1.0, 30)], [None], [0])
        payload = mocked_emit.call_args.args[2]
        self.assertIsNone(payload['old'])
        self.assertEqual(payload['new'], {'value': 1.0, 'video_id': 30, 'rank': 1})

    @patch('effranking.news.emit')
    def test_write_publishes_rank_after_the_write(self, mocked_emit):
        ranking = ThrpRankingCache()
        previous = {1: thrp_record()}
        records = {1: thrp_record(b=thrp_part(1.0, 11))}
        _write_with_news([(ranking, previous, records)])
        payloads = [item.args[2] for item in mocked_emit.call_args_list]
        self.assertEqual([item['field'] for item in payloads], ['thrp:b', 'thrp:sum'])
        self.assertTrue(all(item['old'] is None and item['new']['rank'] == 1 for item in payloads))

    @patch('effranking.news.emit')
    def test_remove_path_publishes_no_news(self, mocked_emit):
        ranking = ThrpRankingCache()
        previous = {1: thrp_record(b=thrp_part(1.0, 10))}
        records = {1: thrp_record(b=thrp_part(0.9, 11))}
        _write_with_news([(ranking, previous, records)], publish=False)
        mocked_emit.assert_not_called()
