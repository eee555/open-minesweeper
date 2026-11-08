"""外站元数据适配单测：字段映射与错误分类，全部离线；author_id 仅作一次性归属核验输入、不落库；见 MEDIA_PLAN.md 第 7.1、12 节。"""

from datetime import datetime, timedelta, timezone as datetime_timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils import timezone
from saolei_api import TransportError

from .clients import fetch_media_metadata, fetch_media_metadata_optional, MediaFetchError
from .utils import MediaFormat


def _raise_timeout(coroutine):
    coroutine.close()
    raise TimeoutError


class MediaClientsTests(SimpleTestCase):
    def setUp(self):
        self.timestamp = int((timezone.now() - timedelta(days=1)).timestamp())

    def _video_data(self, **overrides):
        data = {'title': 'video title', 'pubdate': self.timestamp, 'owner': {'mid': 42}}
        data.update(overrides)
        return data

    def test_bilibili_video_mapping(self):
        with patch('media.clients._call_bilibili', return_value=self._video_data()):
            metadata = fetch_media_metadata(MediaFormat.B_V, 'BV1xx411c7mD')
        self.assertEqual(metadata.title, 'video title')
        self.assertEqual(metadata.author_id, '42')
        self.assertEqual(metadata.created_at, datetime.fromtimestamp(self.timestamp, tz=datetime_timezone.utc))

    def test_bilibili_article_uses_publish_time(self):
        data = {
            'title': 'article title', 'publish_time': self.timestamp,
            'ctime': self.timestamp - 100, 'author': {'mid': 7},
        }
        with patch('media.clients._call_bilibili', return_value=data):
            metadata = fetch_media_metadata(MediaFormat.B_A, '1646742')
        self.assertEqual(metadata.author_id, '7')
        self.assertEqual(metadata.created_at, datetime.fromtimestamp(self.timestamp, tz=datetime_timezone.utc))

    def test_saolei_post_mapping(self):
        post = SimpleNamespace(title='post title', post_time=self.timestamp, user_id=9)
        response = SimpleNamespace(items=[post])
        client = MagicMock()
        client.__enter__.return_value.post_info.return_value = response
        with patch('media.clients.Client', return_value=client), patch('media.clients.read_secret', return_value='key'):
            metadata = fetch_media_metadata(MediaFormat.C_P, '9786')
        self.assertEqual(metadata.title, 'post title')
        self.assertEqual(metadata.author_id, '9')
        self.assertEqual(metadata.created_at, datetime.fromtimestamp(self.timestamp, tz=datetime_timezone.utc))

    def test_missing_field_is_parse_error(self):
        with patch('media.clients._call_bilibili', return_value={'title': 'video title'}):
            with self.assertRaises(MediaFetchError) as caught:
                fetch_media_metadata(MediaFormat.B_V, 'BV1xx411c7mD')
        self.assertEqual(caught.exception.category, 'parse_error')
        self.assertEqual(caught.exception.status_code, 502)

    def test_bilibili_timeout_is_504(self):
        settings = MagicMock()
        settings.get_timeout.return_value = 30.0
        with patch('media.clients.sync', side_effect=_raise_timeout), patch('media.clients.request_settings', settings):
            with self.assertRaises(MediaFetchError) as caught:
                fetch_media_metadata(MediaFormat.B_V, 'BV1xx411c7mD')
        self.assertEqual(caught.exception.category, 'timeout')
        self.assertEqual(caught.exception.status_code, 504)
        settings.set_timeout.assert_called_with(30.0)

    def test_saolei_transport_error_is_timeout(self):
        client = MagicMock()
        client.__enter__.side_effect = TransportError('timeout')
        with patch('media.clients.Client', return_value=client), patch('media.clients.read_secret', return_value='key'):
            with self.assertRaises(MediaFetchError) as caught:
                fetch_media_metadata(MediaFormat.C_P, '9786')
        self.assertEqual(caught.exception.category, 'timeout')

    def test_invalid_metadata_rejected(self):
        future = int((timezone.now() + timedelta(days=1)).timestamp())
        invalid = [
            self._video_data(title=''),
            self._video_data(title='x' * 201),
            self._video_data(pubdate='yesterday'),
            self._video_data(pubdate=future),
            self._video_data(owner={'mid': ''}),
            self._video_data(owner={'mid': True}),
        ]
        for data in invalid:
            with self.subTest(data=data), patch('media.clients._call_bilibili', return_value=data):
                with self.assertRaises(MediaFetchError) as caught:
                    fetch_media_metadata(MediaFormat.B_V, 'BV1xx411c7mD')
            self.assertEqual(caught.exception.category, 'invalid_metadata')

    def test_string_author_id_accepted(self):
        data = self._video_data(owner={'mid': 'UCxxxxxxxxxxxxxxxxxxxxxx'})
        with patch('media.clients._call_bilibili', return_value=data):
            metadata = fetch_media_metadata(MediaFormat.B_V, 'BV1xx411c7mD')
        self.assertEqual(metadata.author_id, 'UCxxxxxxxxxxxxxxxxxxxxxx')

    def test_degraded_fetch_returns_none_for_timeout(self):
        with patch('media.clients.fetch_media_metadata', side_effect=MediaFetchError('timeout', 504)):
            self.assertIsNone(fetch_media_metadata_optional(MediaFormat.B_V, 'BV1xx411c7mD'))

    def test_degraded_fetch_returns_none_for_upstream_error(self):
        with patch('media.clients.fetch_media_metadata', side_effect=MediaFetchError('upstream_error', 502)):
            self.assertIsNone(fetch_media_metadata_optional(MediaFormat.C_P, '9786'))

    def test_structural_error_is_not_degraded(self):
        with patch('media.clients.fetch_media_metadata', side_effect=MediaFetchError('parse_error', 502)):
            with self.assertRaises(MediaFetchError) as caught:
                fetch_media_metadata_optional(MediaFormat.B_V, 'BV1xx411c7mD')
        self.assertEqual(caught.exception.category, 'parse_error')

    def test_unknown_format_rejected(self):
        with self.assertRaises(MediaFetchError) as caught:
            fetch_media_metadata('B_o', '1')
        self.assertEqual(caught.exception.category, 'invalid_metadata')
