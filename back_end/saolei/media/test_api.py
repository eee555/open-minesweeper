"""作品页 API 单测：读接口、投稿降级、管理员审核与 CSRF 回归；见 MEDIA_PLAN.md 第 8、12 节。"""

from datetime import datetime, timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.test import Client, override_settings, TestCase
from django.utils import timezone

from accountlink.models import AccountLinkQueue
from userprofile.models import UserProfile
from . import cache, services
from .clients import MediaFetchError, MediaMetadata
from .models import Media, UserMedia
from .utils import MediaFormat, MediaStatus

REFERENCE = datetime(2026, 1, 1, tzinfo=datetime_timezone.utc)
VIDEO_URL = 'https://www.bilibili.com/video/BV1xx411c7mD/'


@override_settings(RATELIMIT_ENABLE=False)
class MediaApiTests(TestCase):
    def setUp(self):
        cache.clear_rankings()
        cache.set_hot_reference(REFERENCE)
        self.user = UserProfile.objects.create_user(
            username='media-api-user', password='test-password', email='media-api-user@example.com',
        )
        UserProfile.objects.filter(pk=self.user.pk).update(date_joined=timezone.now() - timedelta(days=10))
        self.user.refresh_from_db()
        self.staff = UserProfile.objects.create_user(
            username='media-api-staff', password='test-password', email='media-api-staff@example.com', is_staff=True,
        )
        self.superuser = UserProfile.objects.create_user(
            username='media-api-super', password='test-password', email='media-api-super@example.com', is_superuser=True,
        )
        self.staff_client = Client()
        self.staff_client.force_login(self.staff)
        self.client.force_login(self.user)

    def tearDown(self):
        cache.clear_rankings()

    def _create_media(self, suffix='BV1xx411c7mD', **kwargs):
        return services.create_media(
            self.user, media_format=MediaFormat.B_V, suffix=suffix, title='test title',
            created_at=timezone.now() - timedelta(days=1), language='', **kwargs,
        )

    def _bind(self, identifier='42', user=None, verified=True):
        return AccountLinkQueue.objects.create(
            platform='B', identifier=identifier, userprofile=user or self.user, verified=verified,
        )

    def _metadata(self, author_id='42'):
        return MediaMetadata(title='auto title', created_at=timezone.now() - timedelta(days=2), author_id=author_id)

    def _submit(self, url=VIDEO_URL):
        return self.client.post('/api/media/submit', {'url': url, 'language': ''}, content_type='application/json')

    def test_ranking_and_user_ranking(self):
        media = self._create_media()
        services.like_media(self.user, media.pk, 3)
        with self.captureOnCommitCallbacks(execute=True):
            services.verify_media(media.pk, self.staff.pk)
        response = self.client.get('/api/media/ranking?sort=hot')
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body['total'], 1)
        self.assertEqual(body['items'][0]['id'], media.pk)
        self.assertEqual(body['items'][0]['url'], VIDEO_URL)
        self.assertIn('hot_now', body['items'][0])
        self.assertIn('anchor', body)
        self.assertNotIn('external_author_id', body['items'][0])
        user_rank = self.client.get('/api/media/user-ranking?sort=likes')
        self.assertEqual(user_rank.status_code, 200, user_rank.content)
        self.assertEqual(user_rank.json()['items'][0]['user_id'], self.user.pk)
        self.assertEqual(user_rank.json()['items'][0]['likes'], 3)

    def test_latest_pending_and_detailbatch(self):
        verified = self._create_media('BV1verified001')
        with self.captureOnCommitCallbacks(execute=True):
            services.verify_media(verified.pk, self.staff.pk)
        pending = self._create_media('BV1pending0001')
        latest = self.client.get('/api/media/latest')
        self.assertEqual(latest.status_code, 200, latest.content)
        self.assertEqual([item['id'] for item in latest.json()['items']], [verified.pk])
        pending_body = self.client.get('/api/media/pending')
        self.assertEqual(pending_body.status_code, 200, pending_body.content)
        self.assertEqual([item['id'] for item in pending_body.json()['items']], [pending.pk])
        detail = self.client.get(f'/api/media/detailbatch?ids={verified.pk},{pending.pk}')
        self.assertEqual(detail.status_code, 200, detail.content)
        self.assertEqual(len(detail.json()), 2)
        self.assertEqual(self.client.get('/api/media/detailbatch?ids=abc').status_code, 400)

    def test_query_and_user_page_show_rejected(self):
        media = self._create_media()
        services.reject_media(media.pk, self.staff.pk, 'not minesweeper related')
        query = self.client.get('/api/media/query/icontains?value=test&field=title')
        self.assertEqual(query.status_code, 200, query.content)
        self.assertEqual(query.json()['total'], 1)
        self.assertEqual(query.json()['items'][0]['status'], MediaStatus.REJECTED)
        page = self.client.get(f'/api/media/user/{self.user.pk}?pageSize=20')
        self.assertEqual(page.status_code, 200, page.content)
        item = page.json()['items'][0]
        self.assertEqual(item['reject_reason'], 'not minesweeper related')
        self.assertEqual(item['rejected_by'], self.staff.pk)
        self.assertEqual(self.client.get('/api/media/query/nope?value=x').status_code, 400)

    def test_me_requires_login_and_returns_zero_defaults(self):
        self.client.logout()
        self.assertEqual(self.client.get('/api/media/me').status_code, 403)
        self.client.force_login(self.user)
        response = self.client.get('/api/media/me')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertGreaterEqual(response.json()['balance'], 9)
        self.assertEqual(response.json()['likes_sent'], 0)
        self.assertFalse(UserMedia.objects.filter(pk=self.user.pk).exists())

    def test_submit_requires_verified_link(self):
        self._bind('42', verified=False)
        with patch('media.clients.fetch_media_metadata_optional', return_value=self._metadata()):
            response = self._submit()
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(Media.objects.exists())

    def test_submit_success_and_author_mismatch(self):
        self._bind('42')
        with patch('media.clients.fetch_media_metadata_optional', return_value=self._metadata('999')):
            mismatch = self._submit()
        self.assertEqual(mismatch.status_code, 403, mismatch.content)
        with patch('media.clients.fetch_media_metadata_optional', return_value=self._metadata('42')):
            success = self._submit()
        self.assertEqual(success.status_code, 200, success.content)
        body = success.json()
        self.assertEqual(body['title'], 'auto title')
        self.assertFalse(body['metadata_pending'])
        self.assertNotIn('external_author_id', body)

    def test_submit_degraded_and_structural_error(self):
        self._bind('42')
        with patch('media.clients.fetch_media_metadata_optional', return_value=None):
            degraded = self._submit()
        self.assertEqual(degraded.status_code, 200, degraded.content)
        self.assertEqual(degraded.json()['title'], '')
        self.assertTrue(degraded.json()['metadata_pending'])
        other_url = VIDEO_URL.replace('BV1xx411c7mD', 'BV1xx411c7mE')
        with patch('media.clients.fetch_media_metadata_optional', side_effect=MediaFetchError('parse_error', 502)):
            rejected = self._submit(other_url)
        self.assertEqual(rejected.status_code, 502, rejected.content)
        self.assertFalse(Media.objects.filter(suffix='BV1xx411c7mE').exists())

    def test_submit_duplicate_returns_409(self):
        self._bind('42')
        self._create_media()
        with patch('media.clients.fetch_media_metadata_optional', return_value=self._metadata()):
            response = self._submit()
        self.assertEqual(response.status_code, 409, response.content)

    def test_like_endpoint(self):
        media = self._create_media()
        response = self.client.post('/api/media/like', {'media_id': media.pk, 'count': 3}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['likes'], 3)
        self.assertEqual(response.json()['status'], MediaStatus.PENDING)
        self.assertEqual(self.client.post('/api/media/like', {'media_id': media.pk, 'count': 0}, content_type='application/json').status_code, 422)

    def test_two_level_bans(self):
        self._bind('42')
        UserMedia.objects.create(user=self.user, banned=True)
        with patch('media.clients.fetch_media_metadata_optional', return_value=None):
            self.assertEqual(self._submit().status_code, 403)
        self.assertEqual(self.client.get('/api/media/ranking').status_code, 200)
        media = self._create_media('BV1banned00001')
        self.assertEqual(self.client.post('/api/media/like', {'media_id': media.pk, 'count': 1}, content_type='application/json').status_code, 200)
        UserProfile.objects.filter(pk=self.user.pk).update(is_banned=True)
        self.assertEqual(self.client.post('/api/media/like', {'media_id': media.pk, 'count': 1}, content_type='application/json').status_code, 403)

    def test_admin_verify_degraded_checks_link_without_persisting_id(self):
        media = services.create_media(
            self.user, media_format=MediaFormat.B_V, suffix='BV1degraded001', language='', metadata_pending=True,
        )
        url = '/api/media/admin/verify'
        payload = {'id': media.pk, 'title': 'manual title', 'external_author_id': '42'}
        self.assertEqual(self.staff_client.post(url, payload, content_type='application/json').status_code, 403)
        self._bind('7')
        self.assertEqual(self.staff_client.post(url, payload, content_type='application/json').status_code, 403)
        self._bind('42')
        self.assertEqual(self.staff_client.post(url, {'id': media.pk, 'external_author_id': '42'}, content_type='application/json').status_code, 400)
        self.assertEqual(self.staff_client.post(url, {'id': media.pk, 'title': 'manual title'}, content_type='application/json').status_code, 400)
        media.refresh_from_db()
        self.assertEqual(media.status, MediaStatus.PENDING)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.staff_client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        media.refresh_from_db()
        self.assertEqual(media.status, MediaStatus.VERIFIED)
        self.assertEqual(media.title, 'manual title')
        self.assertFalse(media.metadata_pending)
        self.assertNotIn('external_author_id', response.json())

    def test_admin_reject_reopen_ban_edit(self):
        media = self._create_media()
        services.like_media(self.user, media.pk, 2)
        response = self.staff_client.post('/api/media/admin/reject', {'id': media.pk, 'reason': 'not minesweeper'}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        media.refresh_from_db()
        self.assertEqual(media.status, MediaStatus.REJECTED)
        self.assertEqual(media.likes, 0)
        self.assertEqual(response.json()['reject_reason'], 'not minesweeper')
        response = self.staff_client.post('/api/media/admin/reopen', {'id': media.pk}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['status'], MediaStatus.PENDING)
        self.assertEqual(self.staff_client.post('/api/media/admin/ban', {'user_id': self.user.pk}, content_type='application/json').status_code, 200)
        self.assertTrue(UserMedia.objects.get(pk=self.user.pk).banned)
        self.assertEqual(self.staff_client.post('/api/media/admin/unban', {'user_id': self.user.pk}, content_type='application/json').status_code, 200)
        self.assertFalse(UserMedia.objects.get(pk=self.user.pk).banned)
        response = self.staff_client.post('/api/media/admin/edit', {'id': media.pk, 'title': 'edited'}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        media.refresh_from_db()
        self.assertEqual(media.title, 'edited')

    def test_admin_edit_rejects_verified_and_duplicate_url(self):
        media = self._create_media()
        with self.captureOnCommitCallbacks(execute=True):
            services.verify_media(media.pk, self.staff.pk)
        response = self.staff_client.post('/api/media/admin/edit', {'id': media.pk, 'title': 'x'}, content_type='application/json')
        self.assertEqual(response.status_code, 409, response.content)
        other = self._create_media('BV1second00001')
        response = self.staff_client.post('/api/media/admin/edit', {'id': other.pk, 'url': VIDEO_URL}, content_type='application/json')
        self.assertEqual(response.status_code, 409, response.content)

    def test_admin_delete_requires_superuser(self):
        media = self._create_media()
        with self.captureOnCommitCallbacks(execute=True):
            services.verify_media(media.pk, self.staff.pk)
        self.assertEqual(self.staff_client.post('/api/media/admin/delete', {'id': media.pk}, content_type='application/json').status_code, 401)
        client = Client()
        client.force_login(self.superuser)
        response = client.post('/api/media/admin/delete', {'id': media.pk}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['deleted'])
        self.assertFalse(Media.objects.filter(pk=media.pk).exists())

    def test_admin_writes_require_staff(self):
        paths = (
            '/api/media/admin/verify', '/api/media/admin/reject', '/api/media/admin/reopen',
            '/api/media/admin/ban', '/api/media/admin/unban', '/api/media/admin/edit',
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path, {}, content_type='application/json').status_code, 403)
        self.assertEqual(self.client.get('/api/media/admin/rejected').status_code, 403)
        self.assertEqual(self.staff_client.get('/api/media/admin/rejected').status_code, 200)


@override_settings(RATELIMIT_ENABLE=False)
class MediaApiCsrfTests(TestCase):
    token_url = '/api/userprofile/admin/csrf'

    def setUp(self):
        cache.clear_rankings()
        cache.set_hot_reference(REFERENCE)
        self.user = UserProfile.objects.create_user(
            username='media-csrf-user', password='test-password', email='media-csrf-user@example.com',
        )
        self.staff = UserProfile.objects.create_user(
            username='media-csrf-staff', password='test-password', email='media-csrf-staff@example.com', is_staff=True,
        )
        self.superuser = UserProfile.objects.create_user(
            username='media-csrf-super', password='test-password', email='media-csrf-super@example.com', is_superuser=True,
        )
        self.client = Client(enforce_csrf_checks=True)

    def tearDown(self):
        cache.clear_rankings()

    def _token(self, user=None):
        self.client.force_login(user or self.staff)
        response = self.client.get(self.token_url)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()['csrf_token']

    def _media(self, suffix='BV1csrf000001'):
        return services.create_media(
            self.user, media_format=MediaFormat.B_V, suffix=suffix, title='csrf title',
            created_at=timezone.now() - timedelta(days=1), language='',
        )

    def test_admin_writes_reject_missing_token(self):
        self.client.force_login(self.staff)
        paths = (
            '/api/media/admin/verify', '/api/media/admin/reject', '/api/media/admin/reopen',
            '/api/media/admin/ban', '/api/media/admin/unban', '/api/media/admin/edit',
        )
        for path in paths:
            with self.subTest(path=path):
                response = self.client.post(path, {}, content_type='application/json')
                self.assertEqual(response.status_code, 403, response.content)

    def test_valid_token_runs_but_bad_token_and_cross_origin_do_not(self):
        token = self._token()
        media = self._media()
        payload = {'id': media.pk, 'reason': 'wrong'}
        response = self.client.post('/api/media/admin/reject', payload, content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200, response.content)
        media.refresh_from_db()
        self.assertEqual(media.status, MediaStatus.REJECTED)
        other = self._media('BV1csrf000002')
        for headers in ({'HTTP_X_CSRFTOKEN': 'x' * 64}, {'HTTP_X_CSRFTOKEN': token, 'HTTP_ORIGIN': 'https://evil.invalid'}):
            with self.subTest(headers=headers):
                response = self.client.post('/api/media/admin/reject', {'id': other.pk}, content_type='application/json', **headers)
                self.assertEqual(response.status_code, 403, response.content)
        other.refresh_from_db()
        self.assertEqual(other.status, MediaStatus.PENDING)

    def test_superuser_delete_requires_csrf(self):
        media = self._media('BV1csrf000003')
        with self.captureOnCommitCallbacks(execute=True):
            services.verify_media(media.pk, self.staff.pk)
        token = self._token(self.superuser)
        self.assertEqual(self.client.post('/api/media/admin/delete', {'id': media.pk}, content_type='application/json').status_code, 403)
        response = self.client.post('/api/media/admin/delete', {'id': media.pk}, content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(Media.objects.filter(pk=media.pk).exists())

    def test_ordinary_user_writes_keep_csrf_free_contract(self):
        self._bind()
        self.client.force_login(self.user)
        with patch('media.clients.fetch_media_metadata_optional', return_value=None):
            response = self.client.post('/api/media/submit', {'url': VIDEO_URL, 'language': ''}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)

    def _bind(self):
        AccountLinkQueue.objects.create(platform='B', identifier='42', userprofile=self.user, verified=True)
