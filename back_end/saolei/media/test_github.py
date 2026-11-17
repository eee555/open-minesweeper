"""GitHub 仓库元数据契约、网络错误与来源边界，所有请求离线。"""

import json
from unittest.mock import patch

from django.test import SimpleTestCase
import requests

from .clients import fetch_media_metadata_optional, MediaFetchError
from .utils import MediaFormat


class GitHubRepositoryTests(SimpleTestCase):
    def setUp(self):
        self.data = {
            'id': 1296269, 'full_name': 'owner/project', 'created_at': '2020-01-01T00:00:00Z',
            'private': False, 'fork': False, 'owner': {'id': 42, 'type': 'User'},
        }
        self.calls = []
        self.responses = []
        network = patch('requests.sessions.Session.send', side_effect=self.respond)
        self.network = network.start()
        self.addCleanup(network.stop)

    def respond(self, request, **kwargs):
        self.calls.append(request)
        response = requests.Response()
        response.status_code = 200
        response.url = request.url
        response.request = request
        response.headers['Content-Type'] = 'application/json'
        response._content = json.dumps(self.data).encode()
        response._content_consumed = True
        if self.responses:
            response.status_code, headers = self.responses.pop(0)
            response.headers.update(headers)
        return response

    def fetch(self):
        return fetch_media_metadata_optional(MediaFormat.G_R, 'owner/project')

    def test_repository_and_owner_ids_are_distinct_and_no_credentials_are_sent(self):
        metadata = self.fetch()
        self.assertEqual(metadata.source_id, '1296269')
        self.assertEqual(metadata.author_id, '42')
        self.assertEqual(metadata.title, 'owner/project')
        self.assertEqual(metadata.created_at.isoformat(), '2020-01-01T00:00:00+00:00')
        self.assertEqual(self.calls[0].url, 'https://api.github.com/repos/owner/project')
        self.assertNotIn('Authorization', self.calls[0].headers)

    def test_forks_private_repositories_and_organizations_are_rejected(self):
        for field, value in (('fork', True), ('private', True), ('owner', {'id': 42, 'type': 'Organization'})):
            original = self.data.copy()
            self.data[field] = value
            with self.subTest(field=field), self.assertRaises(MediaFetchError) as caught:
                self.fetch()
            self.assertEqual(caught.exception.category, 'unsupported_repository')
            self.data = original

    def test_required_fields_and_future_dates_cannot_be_treated_as_valid(self):
        for field, value in (('id', True), ('id', 0), ('private', None), ('fork', None), ('created_at', '2999-01-01T00:00:00Z'), ('full_name', '../project')):
            original = self.data.copy()
            self.data[field] = value
            with self.subTest(field=field), self.assertRaises(MediaFetchError):
                self.fetch()
            self.data = original

    def test_404_rate_limits_and_timeouts_do_not_degrade(self):
        for status, headers, category in ((404, {}, 'not_found'), (429, {}, 'rate_limited'), (403, {'X-RateLimit-Remaining': '0'}, 'rate_limited'), (500, {}, 'upstream_error')):
            self.responses = [(status, headers)]
            with self.subTest(status=status), self.assertRaises(MediaFetchError) as caught:
                self.fetch()
            self.assertEqual(caught.exception.category, category)
        self.network.side_effect = requests.ReadTimeout()
        with self.assertRaises(MediaFetchError) as caught:
            self.fetch()
        self.assertEqual(caught.exception.category, 'timeout')

    def test_redirects_are_bounded_and_cannot_leave_the_api_host(self):
        self.responses = [(301, {'Location': 'https://api.github.com/repositories/1296269'})]
        self.assertEqual(self.fetch().source_id, '1296269')
        self.assertEqual(self.calls[-1].url, 'https://api.github.com/repositories/1296269')
        for target in ('https://evil.test/repo', 'http://api.github.com/repos/a/b', 'https://api.github.com:443/repo', 'https://user@api.github.com/repo'):
            self.responses = [(301, {'Location': target})]
            before = len(self.calls)
            with self.subTest(target=target), self.assertRaises(MediaFetchError):
                self.fetch()
            self.assertEqual(len(self.calls), before + 1)
        self.responses = [(301, {'Location': '/repositories/1296269'})] * 3
        with self.assertRaises(MediaFetchError):
            self.fetch()

    def test_overall_deadline_and_response_size_are_checked(self):
        with patch('media.clients.monotonic', side_effect=[0, 0, 9]):
            with self.assertRaises(MediaFetchError) as caught:
                self.fetch()
        self.assertEqual(caught.exception.category, 'timeout')
        with patch('media.clients.GITHUB_RESPONSE_LIMIT', 10):
            with self.assertRaises(MediaFetchError) as caught:
                self.fetch()
        self.assertEqual(caught.exception.category, 'invalid_metadata')
