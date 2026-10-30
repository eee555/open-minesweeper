from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.http import HttpResponse
from django.test import Client, override_settings, RequestFactory, TestCase

from config.tournaments import GSC_Defaults
from tournament.gsc.decorators import GSC_admin_required
from .decorators import admin_csrf_required, banned_blocked, login_required_error
from .models import UserProfile


@override_settings(RATELIMIT_ENABLE=False)
class AdminCsrfTests(TestCase):
    token_url = '/api/userprofile/admin/csrf'

    def setUp(self):
        self.staff = UserProfile.objects.create_user(username='csrf-staff', email='csrf-staff@example.com', is_staff=True)
        self.superuser = UserProfile.objects.create_user(username='csrf-superuser', email='csrf-superuser@example.com', is_superuser=True)
        self.ordinary = UserProfile.objects.create_user(username='csrf-ordinary', email='csrf-ordinary@example.com')
        self.client = Client(enforce_csrf_checks=True)

    def get_token(self, user=None):
        self.client.force_login(user or self.staff)
        response = self.client.get(self.token_url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn(settings.CSRF_COOKIE_NAME, response.cookies)
        self.assertIn('no-store', response['Cache-Control'])
        return response.json()['csrf_token']

    def test_token_bootstrap_only_allows_staff_and_superusers(self):
        self.assertEqual(self.client.get(self.token_url).status_code, 401)
        self.client.force_login(self.ordinary)
        self.assertEqual(self.client.get(self.token_url).status_code, 403)
        self.get_token(self.staff)
        self.get_token(self.superuser)

    def test_all_admin_write_families_reject_missing_tokens_before_processing(self):
        self.client.force_login(self.staff)
        paths = [
            ('post', '/api/common/tasks/delete'), ('post', '/api/common/tasks/restart'), ('post', '/api/common/tasks/cleanup'),
            ('post', '/api/accountlink/verify/'), ('post', '/api/accountlink/unverify/'),
            ('post', '/api/identifier/bind'), ('post', '/api/identifier/safe'),
            ('patch', '/api/userprofile/admin/update/1'), ('patch', '/api/msuser/admin/update/1'),
            ('post', '/api/video/newest_queue/remove'), ('post', '/api/video/admin/freeze'),
            ('post', '/api/video/admin/delete'), ('post', '/api/userprofile/admin/staff'),
            ('post', '/api/userprofile/admin/clear-info'), ('post', '/api/article/admin/refresh'),
            ('post', '/api/common/admin/memorial/users/1/videos'),
            ('post', '/api/medal/staff/grants'), ('post', '/api/medal/staff/grants/1/revoke'),
            ('post', '/api/medal/staff/rebuild'), ('post', '/api/medal/staff/overrides'),
            ('post', '/api/customranking/pluck/refresh'), ('post', '/api/speedranking/top/admin/rebuild_record'),
            ('post', '/api/speedranking/pb/admin/rebuild_record'), ('post', '/api/speedranking/admin/rebuild_record'),
            ('post', '/api/effranking/thrp/admin/rebuild_record'), ('post', '/api/effranking/nf_ioe/admin/rebuild_record'),
            ('post', '/api/tournament/validate'), ('post', '/api/tournament/allow'), ('post', '/api/tournament/set_staff'),
            ('post', '/api/tournament/weekly/new'), ('post', '/api/tournament/weekly/set'),
            ('post', '/api/tournament/set'), ('post', '/api/tournament/cancel'), ('delete', '/api/tournament/participant/1'),
            ('post', '/api/tournament/gsc/new'), ('post', '/api/tournament/gsc/task/finish'),
            ('post', '/api/tournament/gsc/history/prepare'), ('post', '/api/tournament/gsc/history/participants/1/identifier'),
            ('post', '/api/tournament/gsc/history/participants/1/videos'), ('post', '/api/tournament/gsc/history/scores/users'),
            ('post', '/api/tournament/gsc/history/scores/anonymous'),
            ('post', '/video/set/'), ('post', '/video/update/'), ('post', '/video/update/batch/'),
        ]
        for method, path in paths:
            with self.subTest(method=method, path=path):
                response = getattr(self.client, method)(path, {}, content_type='application/json')
                self.assertEqual(response.status_code, 403, response.content)

    def test_valid_token_runs_action_but_bad_token_and_cross_origin_do_not(self):
        token = self.get_token()
        url = '/api/common/tasks/cleanup'
        with patch('common.api.cleanup_expired_tasks', return_value=3) as cleanup:
            response = self.client.post(url, HTTP_X_CSRFTOKEN=token)
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(response.json(), 3)
            cleanup.assert_called_once()
            cleanup.reset_mock()
            for headers in ({'HTTP_X_CSRFTOKEN': 'x' * 64}, {'HTTP_X_CSRFTOKEN': token, 'HTTP_ORIGIN': 'https://evil.invalid'}):
                response = self.client.post(url, **headers)
                self.assertEqual(response.status_code, 403, response.content)
                cleanup.assert_not_called()

    def test_ordinary_host_keeps_csrf_free_contract_on_shared_endpoint(self):
        tournament = SimpleNamespace(host=self.ordinary, state='p', save=Mock())
        self.client.force_login(self.ordinary)
        with patch('tournament.api.get_object_or_404', return_value=tournament):
            response = self.client.post('/api/tournament/cancel', {'id': 1})
        self.assertEqual(response.status_code, 200, response.content)
        tournament.save.assert_called_once()
        tournament.save.reset_mock()
        self.client.force_login(self.staff)
        with patch('tournament.api.get_object_or_404', return_value=tournament):
            self.assertEqual(self.client.post('/api/tournament/cancel', {'id': 1}).status_code, 403)
        tournament.save.assert_not_called()

    def test_ordinary_user_decorators_do_not_add_csrf_even_for_staff_accounts(self):
        for user in (self.ordinary, self.staff, self.superuser):
            with self.subTest(user=user):
                request = RequestFactory().post('/ordinary-user-action')
                request.user = user
                view = Mock(return_value=HttpResponse(status=204), csrf_exempt=False)
                response = login_required_error(banned_blocked(view))(request)
                self.assertEqual(response.status_code, 204)
                view.assert_called_once()

    def test_conditional_guard_covers_superuser_without_staff_flag(self):
        request = RequestFactory().delete('/shared-action')
        request.user = self.superuser
        view = Mock(return_value=HttpResponse(status=204), csrf_exempt=False)
        self.assertEqual(admin_csrf_required(view)(request).status_code, 403)
        view.assert_not_called()

    def test_ordinary_gsc_host_remains_csrf_free(self):
        request = RequestFactory().post('/gsc-management')
        request.user = SimpleNamespace(id=GSC_Defaults.HOST_ID, is_authenticated=True, is_staff=False, is_superuser=False)
        view = Mock(return_value=HttpResponse(status=204), csrf_exempt=False)
        self.assertEqual(GSC_admin_required(view)(request).status_code, 204)
        view.assert_called_once()

    def test_admin_read_endpoints_do_not_require_a_token(self):
        self.client.force_login(self.staff)
        with patch('common.api.get_task_summary', return_value={'ready': 0, 'running': 0, 'successful': 0, 'failed': 0}):
            response = self.client.get('/api/common/tasks/detail')
        self.assertEqual(response.status_code, 200, response.content)

    def test_retired_get_writes_are_unavailable_and_replacements_are_post_only(self):
        self.client.force_login(self.staff)
        for path in ('/article/update_list/', '/userprofile/del_user_info/'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
        for path in ('/api/article/admin/refresh', '/api/userprofile/admin/clear-info'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 405)

    def test_profile_clear_requires_csrf_and_preserves_staff_target_permission(self):
        self.ordinary.realname = '可清空姓名'
        self.ordinary.signature = '可清空签名'
        self.ordinary.save(update_fields=['_realname', 'signature'])
        token = self.get_token()
        response = self.client.post('/api/userprofile/admin/clear-info', {'id': self.ordinary.pk}, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 204, response.content)
        self.ordinary.refresh_from_db()
        self.assertEqual(self.ordinary._realname, '')
        self.assertEqual(self.ordinary.signature, '')
        self.assertEqual(self.client.post('/api/userprofile/admin/clear-info', {'id': self.staff.pk}, HTTP_X_CSRFTOKEN=token).status_code, 403)

    def test_article_refresh_allows_superuser_without_staff_flag(self):
        token = self.get_token(self.superuser)
        with patch('article.api.refresh_article_list', return_value=2) as refresh:
            response = self.client.post('/api/article/admin/refresh', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), 2)
        refresh.assert_called_once()
