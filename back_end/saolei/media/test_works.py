"""公开作品筛选与数值游标：同值边界、精度、删除和查询成本。"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.core import signing
from django.db import connection
from django.test import override_settings, TestCase
from django.test.utils import CaptureQueriesContext

from userprofile.models import UserProfile
from . import cache, services
from .cursors import CURSOR_SALT, decode_cursor, encode_cursor
from .models import Media
from .utils import MediaStatus

REFERENCE = datetime(2026, 1, 1, tzinfo=timezone.utc)


@override_settings(RATELIMIT_ENABLE=False, EMAIL_SKIP=True)
class WorksTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = UserProfile.objects.create_user(username='works-cursor', password='test-password')

    def _media(self, pk, **overrides):
        submitted_at = overrides.pop('submitted_at', REFERENCE)
        fields = {
            'id': pk, 'user': self.user, 'title': f'Work {pk}', 'format': 'B_a', 'suffix': str(pk),
            'language': 'en', 'created_at': REFERENCE, 'hot_value_updated_at': REFERENCE,
            'hot_value': 0.0, 'likes': 0, 'status': MediaStatus.VERIFIED,
        }
        media = Media.objects.create(**(fields | overrides))
        Media.objects.filter(pk=media.pk).update(submitted_at=submitted_at)
        media.submitted_at = submitted_at
        return media

    def _get(self, **params):
        response = self.client.get('/api/media/works', params)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_all_sorts_traverse_equal_values_and_zero_scores(self):
        for pk in (9, 10, 100, 101, 102):
            self._media(pk)
        self._media(103, status=MediaStatus.PENDING)
        self._media(104, status=MediaStatus.REJECTED)
        for sort in ('hot', 'likes', 'latest', 'submitted'):
            with self.subTest(sort=sort):
                ids, cursor = [], None
                while True:
                    page = self._get(sort=sort, limit=2, **({'cursor': cursor} if cursor else {}))
                    self.assertNotIn('total', page)
                    self.assertNotIn('start', page)
                    ids.extend(row['id'] for row in page['items'])
                    if not page['has_more']:
                        self.assertIsNone(page['next_cursor'])
                        break
                    self.assertNotEqual(page['next_cursor'], cursor)
                    cursor = page['next_cursor']
                self.assertEqual(ids, [102, 101, 100, 10, 9])

    def test_default_submission_order_differs_from_publication_order(self):
        self._media(1, submitted_at=REFERENCE + timedelta(microseconds=2), created_at=REFERENCE + timedelta(days=1))
        self._media(2, submitted_at=REFERENCE + timedelta(microseconds=1), created_at=REFERENCE + timedelta(days=2))
        self._media(3, submitted_at=REFERENCE + timedelta(microseconds=2), created_at=REFERENCE)
        first = self._get(limit=2)
        self.assertEqual([row['id'] for row in first['items']], [3, 1])
        self.assertEqual([row['id'] for row in self._get(limit=2, cursor=first['next_cursor'])['items']], [2])
        self.assertEqual([row['id'] for row in self._get(sort='latest')['items']], [2, 1, 3])

    def test_language_categories_and_type_are_applied_before_cursor_limit(self):
        self._media(1, language='日本語')
        self._media(2, language='en', format='g_r')
        self._media(3, language='')
        self._media(4, language='es')
        self._media(5, language='zh-cn')
        self._media(6, language='Klingon', format='g_r')
        self.assertEqual([row['id'] for row in self._get(language='zh-cn')['items']], [5])
        self.assertEqual([row['id'] for row in self._get(language=' EN ')['items']], [2])
        self.assertEqual([row['id'] for row in self._get(language='es')['items']], [4])
        self.assertEqual([row['id'] for row in self._get(language='other')['items']], [6, 3, 1])
        page = self._get(format='B_a', language='other', limit=1)
        self.assertEqual([row['id'] for row in page['items']], [3])
        following = self._get(format='B_a', language='other', limit=1, cursor=page['next_cursor'])
        self.assertEqual([row['id'] for row in following['items']], [1])
        self.assertFalse(following['has_more'])
        self.assertEqual(len(self._get()['items']), 6)
        self.assertEqual(self._get(format='B_v')['items'], [])

    def test_deleted_boundary_does_not_require_loading_that_work(self):
        self._media(1, hot_value=1.0000000000000002)
        boundary = self._media(2, hot_value=1.0000000000000004)
        self._media(3, hot_value=2.0)
        page = self._get(sort='hot', limit=2)
        boundary.delete()
        self.assertEqual([row['id'] for row in self._get(sort='hot', limit=2, cursor=page['next_cursor'])['items']], [1])

    def test_datetime_microseconds_and_large_likes_round_trip(self):
        filters = {'format': '', 'language': ''}
        for sort, value in (('latest', REFERENCE + timedelta(microseconds=123456)), ('submitted', REFERENCE + timedelta(microseconds=123456)), ('likes', 2**53 + 1), ('hot', 1.0000000000000002)):
            with self.subTest(sort=sort):
                token = encode_cursor(sort, filters, value, 2**53 + 1)
                self.assertEqual(decode_cursor(token, sort, filters), (value, 2**53 + 1))

    def test_invalid_cursors_and_query_parameters(self):
        self._media(1)
        self._media(2)
        cursor = self._get(limit=1)['next_cursor']
        for params, code in (
            ({'cursor': cursor + 'tamper'}, 'invalid_cursor'),
            ({'cursor': cursor, 'sort': 'likes'}, 'cursor_query_mismatch'),
            ({'cursor': cursor, 'sort': 'latest'}, 'cursor_query_mismatch'),
            ({'cursor': cursor, 'language': 'en'}, 'cursor_query_mismatch'),
            ({'cursor': cursor, 'language': 'other'}, 'cursor_query_mismatch'),
            ({'cursor': ''}, 'invalid_cursor'),
            ({'limit': 51}, 'invalid_sort_or_limit'),
            ({'limit': 0}, 'invalid_sort_or_limit'),
            ({'format': 'invalid'}, 'invalid_format'),
            ({'language': 'x' * 33}, 'invalid_language'),
            ({'language': 'Klingon'}, 'invalid_language'),
            ({'language_empty': True}, 'unsupported_query_parameter'),
            ({'start': 100000}, 'unsupported_query_parameter'),
            ({'user_id': self.user.pk}, 'unsupported_query_parameter'),
        ):
            with self.subTest(params=params):
                response = self.client.get('/api/media/works', params)
                self.assertEqual(response.status_code, 400, response.content)
                self.assertEqual(response.json()['detail'], code)
        filters = {'format': '', 'language': ''}
        for value in ('nan', 'inf', '-1'):
            cursor = signing.dumps({'v': 1, 'sort': 'hot', 'filters': filters, 'value': value, 'id': '1'}, salt=CURSOR_SALT)
            self.assertEqual(self.client.get('/api/media/works', {'sort': 'hot', 'cursor': cursor}).status_code, 400)

    def test_one_database_query_without_count_offset_or_redis(self):
        for pk in range(1, 6):
            self._media(pk)
        queryset = Media.objects.filter(status=MediaStatus.VERIFIED)
        with patch.object(cache.cache, 'execute_command', side_effect=AssertionError('no ranking Redis reads')):
            with CaptureQueriesContext(connection) as queries:
                page = services.list_works(queryset, limit=2)
            self.assertEqual(len(queries), 1)
            with CaptureQueriesContext(connection) as following:
                services.list_works(queryset, limit=2, cursor=page['next_cursor'])
            self.assertEqual(len(following), 1)
        for query in (*queries, *following):
            self.assertNotIn('COUNT(', query['sql'].upper())
            self.assertNotIn('OFFSET', query['sql'].upper())
