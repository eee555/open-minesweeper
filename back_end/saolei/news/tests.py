import json
import time
from unittest.mock import patch

from django.test import override_settings, SimpleTestCase

from speedranking.pb.cache import PBRankingCache
from speedranking.services import _publish_lsf_news, _publish_pb_news, _write_records
from speedranking.top.cache import TopRankingCache
from speedranking.top.services import complete_update
from speedranking.top.utils import SOFT_FIELDS
from .cache import ALL_KEY, cache, EVENTS_KEY, flush, index_key, publish, read_events, TTL_SECONDS
from .services import emit


def soft(lsf):
    return {field: lsf for field in SOFT_FIELDS}


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

    def test_expired_events_are_removed_from_hash(self):
        event = publish('pb', 1, {})
        expired = (time.time() - TTL_SECONDS - 60) * 1000
        cache.zadd(ALL_KEY, {event['id']: expired})
        cache.zadd(index_key('pb'), {event['id']: expired})
        fresh = publish('lsf', 2, {})
        self.assertIsNone(cache.hget(EVENTS_KEY, event['id']))
        self.assertEqual([item['id'] for item in read_events()], [fresh['id']])

    @patch('news.cache.MAX_EVENTS', 3)
    def test_overflow_removes_oldest_hash_fields(self):
        for index in range(5):
            publish('pb', index, {'n': index})
        self.assertEqual(cache.hlen(EVENTS_KEY), 3)
        self.assertEqual([event['payload']['n'] for event in read_events(limit=10)], [4, 3, 2])

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
        previous = ({}, {}, {1: {}})
        records = {1: {'std:bt': {'videos': [{'value': 1000, 'video_id': 9}]}}}
        _write_records(previous, {}, {}, records, news_targets={1: 9})
        self.assertEqual(mocked_emit.call_count, 1)
        category, player_id, payload = mocked_emit.call_args.args
        self.assertEqual((category, player_id), ('lsf', 1))
        self.assertEqual(payload['video_id'], 9)
        self.assertEqual(payload['old'], {'lsf': 100, 'rank': 1})
        self.assertEqual(payload['new'], {'lsf': 200, 'rank': 1})

    @patch('speedranking.services.emit')
    @patch('speedranking.top.services.soft_refresh_requested.send')
    def test_remove_path_publishes_no_news(self, _send, mocked_emit):
        previous = ({}, {}, {1: {}})
        records = {1: {'std:bt': {'videos': [{'value': 1000, 'video_id': 9}]}}}
        _write_records(previous, {}, {}, records)
        mocked_emit.assert_not_called()

    @patch('speedranking.services.emit')
    def test_news_targets_supply_the_trigger_video(self, mocked_emit):
        _publish_lsf_news({1: 42}, {1: (100.0, 40)}, {1: (200.0, 28)})
        payload = mocked_emit.call_args.args[2]
        self.assertEqual(payload['video_id'], 42)
        self.assertEqual(payload['old'], {'lsf': 100.0, 'rank': 41})
        self.assertEqual(payload['new'], {'lsf': 200.0, 'rank': 29})

    @patch('speedranking.services.emit')
    def test_changes_outside_top_36_publish_no_news(self, mocked_emit):
        _publish_lsf_news({1: 42}, {1: (100.0, 40)}, {1: (200.0, 40)})
        mocked_emit.assert_not_called()

    @patch('speedranking.top.services.soft_refresh_requested.send')
    def test_forced_admin_rebuild_takes_no_snapshot(self, _send):
        records = {1: {'std:bt': {'videos': [{'value': 1000, 'video_id': 9}]}}}
        self.assertEqual(complete_update({1: {}}, records, set(), force=True), {})
