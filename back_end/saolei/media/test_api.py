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
        # 缓存同步在部署中是后台任务；单测里同步执行以便断言排行榜响应。
        patcher = patch(
            'media.services.enqueue_media_score_sync',
            side_effect=lambda media_id, author_id: cache.sync_media_scores(media_id, author_id),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

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

    def _submit(self, suffix='BV1xx411c7mD', media_format=MediaFormat.B_V):
        return self.client.post(
            '/api/media/submit',
            {'format': media_format, 'suffix': suffix, 'language': ''},
            content_type='application/json',
        )

    def test_ranking_and_user_ranking(self):
        media = self._create_media()
        for _ in range(3):
            services.like_media(self.user, media.pk)
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

    def test_verified_zero_score_work_is_ranked_in_hot_and_likes(self):
        """审核通过但未投喂的 0 分作品必须同时进入热门与精品，避免只在《最新》可见。"""
        media = self._create_media()
        services.verify_media(media.pk, self.staff.pk)
        for sort in ('hot', 'likes'):
            with self.subTest(sort=sort):
                response = self.client.get(f'/api/media/ranking?sort={sort}')
                self.assertEqual(response.status_code, 200, response.content)
                body = response.json()
                self.assertEqual(body['total'], 1)
                self.assertEqual([item['id'] for item in body['items']], [media.pk])

    def test_latest_pending_and_detailbatch(self):
        verified = self._create_media('BV1verified001')
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
        with patch('media.clients.fetch_media_metadata_optional', side_effect=MediaFetchError('parse_error', 502)):
            rejected = self._submit('BV1xx411c7mE')
        self.assertEqual(rejected.status_code, 502, rejected.content)
        self.assertFalse(Media.objects.filter(suffix='BV1xx411c7mE').exists())

    def test_submit_duplicate_returns_409(self):
        self._bind('42')
        self._create_media()
        with patch('media.clients.fetch_media_metadata_optional', return_value=self._metadata()):
            response = self._submit()
        self.assertEqual(response.status_code, 409, response.content)

    def test_submit_normalizes_numeric_suffix(self):
        self._bind('42')
        with patch('media.clients.fetch_media_metadata_optional', return_value=self._metadata()):
            first = self._submit('01646742', MediaFormat.B_A)
            second = self._submit('1646742', MediaFormat.B_A)
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 409, second.content)
        self.assertEqual(Media.objects.filter(format=MediaFormat.B_A).count(), 1)
        self.assertEqual(Media.objects.get(format=MediaFormat.B_A).suffix, '1646742')

    def test_submit_rejects_unknown_format_or_mismatched_suffix(self):
        self._bind('42')
        with patch('media.clients.fetch_media_metadata_optional', return_value=self._metadata()):
            unknown = self.client.post(
                '/api/media/submit',
                {'format': 'B_o', 'suffix': '9786', 'language': ''},
                content_type='application/json',
            )
            mismatch = self.client.post(
                '/api/media/submit',
                {'format': MediaFormat.B_V, 'suffix': 'https://www.bilibili.com/read/cv1646742', 'language': ''},
                content_type='application/json',
            )
        self.assertEqual(unknown.status_code, 400, unknown.content)
        self.assertEqual(mismatch.status_code, 400, mismatch.content)
        self.assertFalse(Media.objects.exists())

    def test_like_endpoint(self):
        media = self._create_media()
        response = self.client.post('/api/media/like', {'media_id': media.pk}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['likes'], 1)
        self.assertEqual(response.json()['status'], MediaStatus.PENDING)
        counted = self.client.post('/api/media/like', {'media_id': media.pk, 'count': 5}, content_type='application/json')
        self.assertEqual(counted.status_code, 200, counted.content)
        self.assertEqual(counted.json()['likes'], 2)

    def test_like_daily_limit_returns_429(self):
        UserProfile.objects.filter(pk=self.user.pk).update(date_joined=timezone.now() - timedelta(days=30))
        self.user.refresh_from_db()
        media = self._create_media()
        for _ in range(10):
            self.assertEqual(self.client.post('/api/media/like', {'media_id': media.pk}, content_type='application/json').status_code, 200)
        limited = self.client.post('/api/media/like', {'media_id': media.pk}, content_type='application/json')
        self.assertEqual(limited.status_code, 429, limited.content)
        self.assertEqual(UserMedia.objects.get(pk=self.user.pk).daily_likes, 10)

    def test_two_level_bans(self):
        self._bind('42')
        UserMedia.objects.create(user=self.user, banned=True)
        with patch('media.clients.fetch_media_metadata_optional', return_value=None):
            self.assertEqual(self._submit().status_code, 403)
        self.assertEqual(self.client.get('/api/media/ranking').status_code, 200)
        media = self._create_media('BV1banned00001')
        self.assertEqual(self.client.post('/api/media/like', {'media_id': media.pk}, content_type='application/json').status_code, 200)
        UserProfile.objects.filter(pk=self.user.pk).update(is_banned=True)
        self.assertEqual(self.client.post('/api/media/like', {'media_id': media.pk}, content_type='application/json').status_code, 403)

    def test_admin_verify_normal_submission_needs_no_external_author_id(self):
        """投稿时已核对上游作者归属，审核只提交 id；任何信息修改字段都显式拒绝。"""
        url = '/api/media/admin/verify'
        media = self._create_media()
        response = self.staff_client.post(url, {'id': media.pk}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        media.refresh_from_db()
        self.assertEqual(media.status, MediaStatus.VERIFIED)
        self.assertEqual(media.title, 'test title')
        self.assertFalse(media.metadata_pending)
        self.assertNotIn('external_author_id', response.json())
        untouched = self._create_media('BV1untouch01')
        for extra in ({'title': 'admin edit'}, {'created_at': REFERENCE.isoformat()}, {'external_author_id': '42'}):
            with self.subTest(extra=extra):
                response = self.staff_client.post(url, {'id': untouched.pk, **extra}, content_type='application/json')
                self.assertEqual(response.status_code, 400, response.content)
        untouched.refresh_from_db()
        self.assertEqual(untouched.status, MediaStatus.PENDING)
        self.assertEqual(untouched.title, 'test title')

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
        response = self.staff_client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        media.refresh_from_db()
        self.assertEqual(media.status, MediaStatus.VERIFIED)
        self.assertEqual(media.title, 'manual title')
        self.assertFalse(media.metadata_pending)
        self.assertNotIn('external_author_id', response.json())

    def test_admin_reject_reopen_ban_edit(self):
        media = self._create_media()
        for _ in range(2):
            services.like_media(self.user, media.pk)
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
        degraded = services.create_media(
            self.user, media_format=MediaFormat.B_V, suffix='BV1edit000001', language='', metadata_pending=True,
        )
        response = self.staff_client.post('/api/media/admin/edit', {'id': degraded.pk, 'title': 'edited'}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        degraded.refresh_from_db()
        self.assertEqual(degraded.title, 'edited')

    def test_admin_edit_only_accepts_degraded_metadata_corrections(self):
        """管理员只能给降级投稿补录元数据；改 URL / format / suffix 与改正常投稿一律拒绝。"""
        url = '/api/media/admin/edit'
        verified = self._create_media('BV1verified002')
        services.verify_media(verified.pk, self.staff.pk)
        self.assertEqual(self.staff_client.post(url, {'id': verified.pk, 'title': 'x'}, content_type='application/json').status_code, 409)
        normal = self._create_media('BV1normal0002')
        self.assertEqual(self.staff_client.post(url, {'id': normal.pk, 'title': 'x'}, content_type='application/json').status_code, 400)
        degraded = services.create_media(
            self.user, media_format=MediaFormat.B_V, suffix='BV1degraded002', language='', metadata_pending=True,
        )
        payload = {'id': degraded.pk, 'title': 'manual title', 'language': 'zh', 'created_at': REFERENCE.isoformat()}
        response = self.staff_client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        degraded.refresh_from_db()
        self.assertEqual(degraded.title, 'manual title')
        self.assertEqual(degraded.language, 'zh')
        self.assertEqual(degraded.created_at, REFERENCE)
        for forbidden in ('url', 'format', 'suffix'):
            with self.subTest(field=forbidden):
                response = self.staff_client.post(url, {'id': degraded.pk, forbidden: VIDEO_URL}, content_type='application/json')
                self.assertIn(response.status_code, (400, 422), response.content)
        degraded.refresh_from_db()
        self.assertEqual(degraded.format, MediaFormat.B_V)
        self.assertEqual(degraded.suffix, 'BV1degraded002')

    def test_admin_delete_requires_superuser(self):
        media = self._create_media()
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
            response = self.client.post(
                '/api/media/submit',
                {'format': MediaFormat.B_V, 'suffix': 'BV1xx411c7mD', 'language': ''},
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200, response.content)

    def _bind(self):
        AccountLinkQueue.objects.create(platform='B', identifier='42', userprofile=self.user, verified=True)
