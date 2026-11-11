from datetime import datetime
from io import StringIO
import json
from unittest.mock import patch

from django.conf import settings
from django.core.cache import caches
from django.core.management import call_command
from django.test import override_settings, RequestFactory, TestCase
from django_redis import get_redis_connection

from msuser.models import UserMS
from userprofile.models import UserProfile
from .cache import newest_cache, serialize_video_to_queue
from .models import ExpandVideoModel, VideoModel
from .schema import PARSED_VIDEO_FIELDS, VIDEO_METADATA_FIELDS


@override_settings(RATELIMIT_ENABLE=False)
class VideoInfoTests(TestCase):
    def setUp(self):
        self.owner = UserProfile.objects.create_user(username='video-info-owner', email='video-info-owner@example.com', userms=UserMS.objects.create())
        self.other = UserProfile.objects.create_user(username='video-info-other', email='video-info-other@example.com', userms=UserMS.objects.create())
        self.video = VideoModel.objects.create(
            player=self.owner, video=ExpandVideoModel.objects.create(identifier='Fixture'), file='fixture.evf', file_size=123,
            software='e', level='b', mode='00', bv=4, timems=1000, state='c', left=5, right=0, double=1, left_ce=3, right_ce=0, double_ce=1,
        )
        self.private = VideoModel.objects.create(
            player=self.owner, video=ExpandVideoModel.objects.create(), file='private.evf', software='e', level='b', bv=4, ongoing_tournament=True,
        )

    def test_batch_fields_and_visibility_for_guests_owners_and_staff(self):
        endpoints = (
            ('staticdetailbatch', {'ids': f'{self.private.id},{self.video.id},{self.video.id},99999999'}),
            ('abstractbulk', {'first': self.video.id, 'count': self.private.id - self.video.id + 1}),
        )
        for user, staff in ((None, False), (self.owner, False), (self.other, False), (self.owner, True), (self.other, True)):
            self.client.logout()
            if user is not None:
                user.is_staff = staff
                user.save(update_fields=['is_staff'])
                self.client.force_login(user)
            for endpoint, params in endpoints:
                with self.subTest(user=user.pk if user else None, staff=staff, endpoint=endpoint):
                    response = self.client.get(f'/api/video/{endpoint}', params)
                    self.assertEqual(response.status_code, 200, response.content)
                    rows = response.json()
                    expected = [self.video.id, self.private.id] if endpoint == 'staticdetailbatch' and user == self.owner else [self.video.id]
                    self.assertEqual(sorted(row['id'] for row in rows), sorted(expected))
                    fields = {'id', 'ongoing_tournament', 'identifier', 'tournament_identifier', *PARSED_VIDEO_FIELDS} if endpoint == 'staticdetailbatch' else {'id', 'player', 'upload_time', 'state'}
                    self.assertEqual(set(rows[0]), fields)
                    if user is None:
                        if endpoint == 'staticdetailbatch':
                            self.assertEqual(rows[0]['file_size'], 123)
                            self.assertEqual(rows[0]['identifier'], 'Fixture')

    def test_range_endpoints_cap_the_id_span_without_filling_gaps(self):
        first = self.private.pk + 100
        for endpoint, limit in (('abstractbulk', 10000), ('infobulk', 2000), ('detailbulk', 500)):
            with self.subTest(endpoint=endpoint):
                for video_id in (first - 1, first, first + limit - 1, first + limit):
                    VideoModel.objects.create(
                        pk=video_id, player=self.owner, video=ExpandVideoModel.objects.create(), file='range.evf',
                        software='e', level='b', bv=4, timems=1000,
                    )
                response = self.client.get(f'/api/video/{endpoint}', {'first': first, 'count': limit + 1})
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual({row['id'] for row in response.json()}, {first, first + limit - 1})
            first += limit + 2

    @override_settings(
        RATELIMIT_ENABLE=True,
        RATELIMIT_USE_CACHE='video-api-bandwidth-tests',
        CACHES={**settings.CACHES, 'video-api-bandwidth-tests': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'video-api-bandwidth-tests'}},
    )
    def test_data_endpoints_limit_each_ip_independently_and_allow_the_next_window(self):
        rate_cache = caches['video-api-bandwidth-tests']
        rate_cache.clear()
        self.addCleanup(rate_cache.clear)
        range_params = {'first': self.video.pk, 'count': 1}
        for endpoint, params, limit, period in (
            ('abstractbulk', range_params, 1, 2),
            ('infobulk', range_params, 1, 1),
            ('detailbulk', range_params, 1, 1),
            ('staticdetailbatch', {'ids': str(self.video.pk)}, 5, 1),
        ):
            with self.subTest(endpoint=endpoint):
                url = f'/api/video/{endpoint}'
                with patch('django_ratelimit.core.time.time', return_value=1000000000):
                    for _ in range(limit):
                        self.assertEqual(self.client.get(url, params, REMOTE_ADDR='192.0.2.1').status_code, 200)
                    self.assertEqual(self.client.get(url, params, REMOTE_ADDR='192.0.2.1').status_code, 429)
                    self.assertEqual(self.client.get(url, params, REMOTE_ADDR='192.0.2.2').status_code, 200)
                with patch('django_ratelimit.core.time.time', return_value=1000000000 + period):
                    self.assertEqual(self.client.get(url, params, REMOTE_ADDR='192.0.2.1').status_code, 200)

    def test_rejects_invalid_or_oversized_batches(self):
        for ids in ('', '0', '-1', '1,2,x', '1,', ','.join(['1'] * 101), '9' * 200):
            with self.subTest(ids=ids):
                self.assertEqual(self.client.get('/api/video/staticdetailbatch', {'ids': ids}).status_code, 400)

    def test_query_and_profile_list_only_return_website_fields(self):
        response = self.client.get('/api/video/query')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(set(response.json()['videos'][0]), {'id', 'upload_time', 'state', 'ongoing_tournament', 'player__id', 'player__realname'})
        response = self.client.get('/api/userprofile/videolist', {'user_id': self.owner.id})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(set(response.json()[0]), set(VIDEO_METADATA_FIELDS))
        self.assertEqual(len(response.json()), 1)
        self.client.force_login(self.owner)
        self.assertEqual(len(self.client.get('/api/userprofile/videolist', {'user_id': self.owner.id}).json()), 2)

    def test_query_rejects_unknown_and_legacy_parameters(self):
        for params in ({'level': 'b'}, {'page': 1}, {'o': 'timems'}, {'nf': True}, {'s[]': 'a'}, {'extra': '1'}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get('/api/video/query', params).status_code, 400)

    def test_query_rejects_invalid_filters_and_sorts(self):
        invalid_filters = (
            'not-json',
            json.dumps([{'field': 'player__realname', 'eq': 'x'}]),
            json.dumps([{'field': 'bv', 'regex': 'x'}]),
            json.dumps([{'field': 'bv', 'gte': 1}, {'field': 'bv', 'lt': 5}]),
            json.dumps([{'field': 'bv', 'gte': 'x'}]),
            json.dumps([{'field': 'state', 'in': ['a'] * 33}]),
            json.dumps([{'field': 'iqg', 'gte': 1}]),
            json.dumps([{'field': 'stnb', 'gte': 1}]),
        )
        for filters in invalid_filters:
            with self.subTest(filters=filters):
                self.assertEqual(self.client.get('/api/video/query', {'filters': filters}).status_code, 400)
        invalid_sorts = (
            json.dumps([{'field': 'path', 'direction': 'asc'}]),
            json.dumps([{'field': 'iqg', 'direction': 'asc'}]),
            json.dumps([{'field': 'timems', 'direction': 'up'}]),
            json.dumps([{'field': 'timems'}, {'field': 'timems', 'direction': 'desc'}]),
        )
        for sorts in invalid_sorts:
            with self.subTest(sorts=sorts):
                self.assertEqual(self.client.get('/api/video/query', {'sorts': sorts}).status_code, 400)

    def test_query_maps_stnb_to_iqg_for_a_single_level(self):
        filters = json.dumps([{'field': 'level', 'eq': 'b'}, {'field': 'stnb', 'gte': 36}])
        sorts = json.dumps([{'field': 'stnb', 'direction': 'desc'}])
        response = self.client.get('/api/video/query', {'filters': filters, 'sorts': sorts})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([row['id'] for row in response.json()['videos']], [self.video.pk])

    def test_batch_loads_expanded_fields_without_per_video_queries(self):
        from .api import get_static_video_detail_batch
        from .schema import ParsedVideoOut

        request = RequestFactory().get('/api/video/staticdetailbatch')
        request.user = self.owner
        with self.assertNumQueries(1):
            data = [ParsedVideoOut.model_validate(video).model_dump() for video in get_static_video_detail_batch(request, f'{self.video.id},{self.private.id}')]
        self.assertEqual(len(data), 2)

    def test_newest_queue_returns_cached_snapshot_without_database_queries(self):
        # Deliberately disagree with database state, owner and visibility; the queue is a cached snapshot.
        VideoModel.objects.filter(pk=self.video.pk).update(state='a', ongoing_tournament=True)
        payload = {'state': 'd', 'time': '2026-10-01T12:00:00Z', 'player_id': self.other.pk}
        entries = {str(self.video.pk).encode(): json.dumps(payload), b'99999999': json.dumps(payload)}
        with patch('videomanager.api.cache.hgetall', return_value=entries), self.assertNumQueries(0):
            response = self.client.get('/api/video/newest_queue')
        self.assertEqual(response.status_code, 200, response.content)
        rows = response.json()
        self.assertEqual([row['id'] for row in rows], [self.video.pk, 99999999])
        for row in rows:
            self.assertEqual(set(row), set(VIDEO_METADATA_FIELDS))
            self.assertEqual(row['player'], self.other.pk)
            self.assertEqual(row['state'], payload['state'])
            self.assertFalse(row['ongoing_tournament'])
            self.assertEqual(datetime.fromisoformat(row['upload_time']), datetime.fromisoformat(payload['time']))

    def test_review_queue_filters_unpublished_and_missing_entries(self):
        VideoModel.objects.filter(pk__in=[self.video.pk, self.private.pk]).update(state='a')
        response = self.client.get('/api/video/review_queue', {'ids': f'{self.private.id},{self.video.id},99999999'})
        self.assertEqual(response.status_code, 200, response.content)
        rows = response.json()
        self.assertEqual([row['id'] for row in rows], [self.video.id])
        self.assertEqual(set(rows[0]), set(VIDEO_METADATA_FIELDS))
        VideoModel.objects.filter(pk=self.video.pk).update(ongoing_tournament=True)
        self.assertEqual(self.client.get('/api/video/review_queue', {'ids': self.video.id}).json(), [])

    def test_queue_compaction_preserves_membership_and_cleanup_time(self):
        cache = get_redis_connection('saolei_website')
        cache.delete(newest_cache.key, 'review_queue', 'freeze_queue')
        self.addCleanup(cache.delete, newest_cache.key)
        payload = {**serialize_video_to_queue(self.video), 'time': '2026-10-22T00:00:00Z', 'timems': 1000, 'software': 'e'}
        cache.hset(newest_cache.key, self.video.id, json.dumps(payload))
        cache.hset('review_queue', self.private.id, '{}')
        call_command('compact_video_cache', stdout=StringIO())
        self.assertEqual(cache.hkeys(newest_cache.key), [str(self.video.id).encode()])
        self.assertEqual(set(json.loads(cache.hget(newest_cache.key, self.video.id))), {'state', 'time', 'player_id'})
        self.assertFalse(cache.exists('review_queue'))
        with patch.object(newest_cache, 'add') as add:
            self.video.timems = 1100
            self.video.save(update_fields=['timems'])
        add.assert_not_called()
