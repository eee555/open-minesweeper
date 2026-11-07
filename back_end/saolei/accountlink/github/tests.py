import hashlib
import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.test import Client, override_settings, TestCase
import requests

from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from .cache import active_key, create_flow, require_active_flow
from .client import authorized_user_id
from ..models import AccountGitHub, AccountLinkQueue, Platform
from ..services import save_verified_account_link

BASE = '/api/accountlink/github'
TEST_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'github-flows'},
    'saolei_website': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'github-sessions'},
}


@override_settings(
    CACHES=TEST_CACHES, RATELIMIT_ENABLE=False, SESSION_COOKIE_SECURE=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    GITHUB_OAUTH_CLIENT_ID='test-client', GITHUB_OAUTH_CLIENT_SECRET='test-secret',
    GITHUB_OAUTH_REDIRECT_URI='https://openms.top/api/accountlink/github/callback',
    GITHUB_OAUTH_FRONTEND_URL='https://openms.top',
)
class GitHubAccountLinkTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = UserProfile.objects.create_user(username='github-owner', email='github-owner@example.test')
        self.other = UserProfile.objects.create_user(username='github-other', email='github-other@example.test')
        self.staff = UserProfile.objects.create_user(username='github-staff', email='github-staff@example.test', is_staff=True)
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.requests = []
        self.token_response = {'access_token': 'test-access-token', 'token_type': 'bearer', 'scope': ''}
        self.user_info = {'id': 123456789, 'login': 'IgnoredName', 'avatar_url': 'https://example.test/avatar', 'email': 'ignored@example.test'}
        network = patch('requests.sessions.Session.send', side_effect=self.remote_response)
        self.network = network.start()
        self.addCleanup(network.stop)

    def remote_response(self, request, **kwargs):
        self.requests.append(request)
        self.assertEqual(kwargs['timeout'], (1, 1.5))
        response = requests.Response()
        response.status_code = 200
        response.url = request.url
        response.request = request
        response.headers['Content-Type'] = 'application/json'
        if request.url == 'https://github.com/login/oauth/access_token':
            data = self.token_response
        elif request.url == 'https://api.github.com/user':
            self.assertEqual(request.headers['Authorization'], 'Bearer test-access-token')
            data = self.user_info
        else:
            raise AssertionError(f'Unexpected HTTP URL: {request.url}')
        response._content = json.dumps(data).encode()
        return response

    def start(self, client=None):
        response = (client or self.client).post(f'{BASE}/start')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn('no-store', response['Cache-Control'])
        params = parse_qs(urlsplit(response.json()['authorization_url']).query)
        return params['state'][0], params

    def callback(self, state, client=None, **params):
        return (client or self.client).get(f'{BASE}/callback', {'state': state, 'code': 'test-code', **params})

    def result(self, response):
        self.assertEqual(response.status_code, 302, response.content)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')
        self.assertTrue(response['Location'].startswith('https://openms.top/#/player/'))
        self.assertNotIn('test-code', response['Location'])
        return parse_qs(urlsplit(response['Location']).fragment.split('?', 1)[1])['github'][0]

    def test_authorization_uses_pkce_and_publishes_only_the_numeric_id(self):
        state, params = self.start()
        self.network.assert_not_called()
        self.assertEqual(params['redirect_uri'], [settings.GITHUB_OAUTH_REDIRECT_URI])
        self.assertEqual(params.get('scope', ['']), [''])
        self.assertEqual(params['code_challenge_method'], ['S256'])
        self.assertEqual(params['prompt'], ['select_account'])
        self.assertNotIn('test-secret', str(params))
        self.assertEqual(self.result(self.callback(state)), 'linked')
        token_request = self.requests[0]
        body = parse_qs(token_request.body)
        self.assertEqual(body['client_id'], ['test-client'])
        self.assertEqual(body['client_secret'], ['test-secret'])
        self.assertEqual(body['redirect_uri'], [settings.GITHUB_OAUTH_REDIRECT_URI])
        import base64
        challenge = base64.urlsafe_b64encode(hashlib.sha256(body['code_verifier'][0].encode()).digest()).rstrip(b'=').decode()
        self.assertEqual(challenge, params['code_challenge'][0])
        account = AccountGitHub.objects.get()
        self.assertEqual(account.pk, self.user_info['id'])
        self.assertEqual({field.name for field in account._meta.fields}, {'id', 'parent'})
        self.assertTrue(AccountLinkQueue.objects.get(platform='g', identifier=str(account.pk)).verified)
        self.client.logout()
        data = self.client.get(f'/api/accountlink/{self.user.pk}').json()
        self.assertEqual(data['g'], {'id': str(account.pk), 'parent': self.user.pk})
        self.assertIn('g', [link['platform'] for link in data['summary']])
        self.assertNotIn('IgnoredName', json.dumps(data))

    def test_cancelled_expired_superseded_and_replayed_flows_never_call_github(self):
        state, _ = self.start()
        self.assertEqual(self.result(self.callback(state, error='access_denied')), 'cancelled')
        self.assertEqual(self.result(self.callback(state)), 'expired')
        old, _ = self.start()
        current, _ = self.start()
        self.assertEqual(self.result(self.callback(old)), 'expired')
        cache.delete(f'accountlink:github:flow:{current}')
        self.assertEqual(self.result(self.callback(current)), 'expired')
        self.assertEqual(self.result(self.callback('invalid')), 'expired')
        self.network.assert_not_called()
        self.assertFalse(AccountGitHub.objects.exists())

    def test_another_browser_or_user_cannot_consume_the_flow(self):
        state, _ = self.start()
        for user in (self.user, self.other):
            browser = Client()
            browser.force_login(user)
            self.assertEqual(self.result(self.callback(state, browser)), 'expired')
        self.network.assert_not_called()
        self.assertEqual(self.result(self.callback(state)), 'linked')

    def test_logout_or_account_switch_invalidates_callback(self):
        for next_user in (None, self.other):
            self.client.force_login(self.user)
            state, _ = self.start()
            self.client.logout()
            if next_user:
                self.client.force_login(next_user)
            self.assertEqual(self.result(self.callback(state)), 'expired')
        self.network.assert_not_called()

    def test_session_is_checked_again_after_external_requests(self):
        state, _ = self.start()

        def logout_during_request(*args):
            self.client.logout()
            return 123456789

        with patch('accountlink.github.api.authorized_user_id', side_effect=logout_during_request):
            self.assertEqual(self.result(self.callback(state)), 'expired')
        self.assertFalse(AccountGitHub.objects.exists())

    def test_repeated_callback_cannot_exchange_the_same_code_twice(self):
        state, _ = self.start()
        observed = []
        original = self.remote_response

        def interleaved(request, **kwargs):
            if not observed:
                observed.append(self.result(self.callback(state)))
            return original(request, **kwargs)

        self.network.side_effect = interleaved
        self.assertEqual(self.result(self.callback(state)), 'linked')
        self.assertEqual(observed, ['expired'])
        self.assertEqual(self.network.call_count, 2)
        self.assertEqual(AccountGitHub.objects.count(), 1)

    def test_conflict_does_not_reassign_identity_or_leave_a_verified_queue_item(self):
        save_verified_account_link(self.other, Platform.GITHUB, str(self.user_info['id']))
        state, _ = self.start()
        self.assertEqual(self.result(self.callback(state)), 'conflict')
        self.assertEqual(AccountGitHub.objects.get().parent_id, self.other.pk)
        self.assertFalse(AccountLinkQueue.objects.filter(userprofile=self.user).exists())

    def test_database_failure_rolls_back_the_binding_and_returns_a_safe_result(self):
        state, _ = self.start()

        def fail_after_save(*args):
            save_verified_account_link(*args)
            raise RuntimeError('test-code test-secret')

        with patch('accountlink.github.api.save_verified_account_link', side_effect=fail_after_save):
            with self.assertLogs('accountlink', level='ERROR') as logs:
                self.assertEqual(self.result(self.callback(state)), 'remote_failed')
        self.assertFalse(AccountGitHub.objects.exists())
        self.assertFalse(AccountLinkQueue.objects.filter(platform='g').exists())
        self.assertNotIn('test-secret', str(logs.output))

    def test_upstream_and_invalid_identity_errors_leave_no_binding(self):
        for value in (None, 0, -1, True, '123', 2 ** 63):
            self.user_info['id'] = value
            state, _ = self.start()
            self.assertEqual(self.result(self.callback(state)), 'remote_failed')
        self.network.side_effect = requests.ReadTimeout('test-secret test-code test-access-token')
        state, _ = self.start()
        with self.assertLogs('accountlink', level='WARNING') as logs:
            self.assertEqual(self.result(self.callback(state)), 'remote_failed')
        self.assertNotIn('test-secret', str(logs.output))
        self.assertNotIn('test-code', str(logs.output))
        self.assertNotIn('test-access-token', str(logs.output))
        self.assertFalse(AccountGitHub.objects.exists())
        self.assertFalse(AccountLinkQueue.objects.filter(platform='g').exists())

    def test_missing_config_and_anonymous_start_do_not_make_network_requests(self):
        old, _ = self.start()
        with override_settings(GITHUB_OAUTH_CLIENT_SECRET=''):
            with patch('accountlink.github.api.create_flow', side_effect=AssertionError('Configuration must be checked first')):
                self.assertEqual(self.client.post(f'{BASE}/start').status_code, 503)
        self.assertEqual(cache.get(active_key(self.user.pk)), old)
        self.client.logout()
        self.assertEqual(self.client.post(f'{BASE}/start').status_code, 403)
        self.network.assert_not_called()

    def test_manual_binding_is_rejected_and_staff_unlink_requires_csrf(self):
        self.assertEqual(self.client.post('/api/accountlink/create/', {'platform': 'g', 'identifier': '123'}).status_code, 400)
        self.client.force_login(self.staff)
        body = {'id': self.user.pk, 'platform': 'g', 'identifier': '123'}
        token = self.client.get('/api/userprofile/admin/csrf').json()['csrf_token']
        self.assertEqual(self.client.post('/api/accountlink/verify/', body, HTTP_X_CSRFTOKEN=token).status_code, 400)
        save_verified_account_link(self.user, Platform.GITHUB, '123')
        self.assertEqual(self.client.post('/api/accountlink/unverify/', body).status_code, 403)
        self.assertEqual(self.client.post('/api/accountlink/unverify/', body, HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertFalse(AccountGitHub.objects.exists())

    def test_owner_can_unlink_and_rebind_and_other_user_cannot_unlink_them(self):
        state, _ = self.start()
        self.assertEqual(self.result(self.callback(state)), 'linked')
        self.assertEqual(self.client.post(f'{BASE}/start').status_code, 409)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(f'{BASE}/unlink').status_code, 200)
        self.assertTrue(AccountGitHub.objects.filter(parent=self.user).exists())
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(f'{BASE}/unlink').status_code, 200)
        self.assertFalse(AccountLinkQueue.objects.filter(platform='g').exists())
        self.user_info['id'] = 987654321
        state, _ = self.start()
        self.assertEqual(self.result(self.callback(state)), 'linked')
        self.assertEqual(AccountGitHub.objects.get().pk, 987654321)

    def test_unlink_during_network_io_invalidates_the_pending_callback(self):
        state, _ = self.start()

        def unlink_during_request(*args):
            self.assertEqual(self.client.post(f'{BASE}/unlink').status_code, 200)
            return 123456789

        with patch('accountlink.github.api.authorized_user_id', side_effect=unlink_during_request):
            self.assertEqual(self.result(self.callback(state)), 'expired')
        self.assertFalse(AccountGitHub.objects.exists())

    def test_deleting_linked_account_invalidates_outstanding_flows(self):
        save_verified_account_link(self.user, Platform.GITHUB, '123')
        state, _ = create_flow(self.user.pk, self.client.session.session_key)
        with self.captureOnCommitCallbacks(execute=True):
            AccountGitHub.objects.all().delete()
        self.assertEqual(self.result(self.callback(state)), 'expired')

    def test_unlink_rejects_inflight_callback_before_commit_hooks(self):
        save_verified_account_link(self.user, Platform.GITHUB, '123')
        state, _ = create_flow(self.user.pk, self.client.session.session_key)

        def unlink_during_request(*args):
            self.assertEqual(self.client.post(f'{BASE}/unlink').status_code, 200)
            return 123

        # 暂不执行提交回调，模拟解绑已释放行锁、缓存提交钩子尚未运行的窗口。
        with self.captureOnCommitCallbacks(execute=False):
            with patch('accountlink.github.api.authorized_user_id', side_effect=unlink_during_request):
                self.assertEqual(self.result(self.callback(state)), 'expired')
        self.assertFalse(AccountGitHub.objects.exists())
        self.assertFalse(AccountLinkQueue.objects.filter(platform='g').exists())

    def test_authlib_errors_are_controlled_failures_without_credential_logs(self):
        for payload in [
            {'error': 'bad_verification_code', 'error_description': 'test-secret test-code'},
            {'token_type': 'bearer'}, {'access_token': 'test-access-token', 'token_type': 'unsupported'},
        ]:
            with self.subTest(payload=payload):
                self.token_response = payload
                with self.assertRaises(ExceptionToResponse) as error:
                    authorized_user_id('test-code', 'v' * 64)
                self.assertEqual(error.exception.body, {'type': 'error', 'object': 'github', 'category': 'remote_failed'})
                self.assertEqual(error.exception.status_code, 502)
                state, _ = self.start()
                with self.assertLogs('accountlink', level='WARNING') as logs:
                    self.assertEqual(self.result(self.callback(state)), 'remote_failed')
                self.assertTrue(all(record.levelname == 'WARNING' for record in logs.records))
                self.assertNotIn('test-secret', str(logs.output))
                self.assertNotIn('test-code', str(logs.output))
        self.assertFalse(AccountGitHub.objects.exists())

    def test_rolled_back_deletion_preserves_binding_but_revokes_pending_authorization(self):
        save_verified_account_link(self.user, Platform.GITHUB, '123')
        state, _ = create_flow(self.user.pk, self.client.session.session_key)
        with self.assertRaises(RuntimeError), transaction.atomic():
            AccountGitHub.objects.all().delete()
            raise RuntimeError('Rollback deletion')
        self.assertTrue(AccountGitHub.objects.filter(pk=123).exists())
        with self.assertRaises(ExceptionToResponse) as error:
            require_active_flow(state, self.user.pk)
        self.assertEqual(error.exception.category, 'expired')
        self.assertEqual(self.result(self.callback(state)), 'expired')
        self.network.assert_not_called()

    def test_new_authorization_after_unlink_remains_usable(self):
        save_verified_account_link(self.user, Platform.GITHUB, '123')
        old, _ = create_flow(self.user.pk, self.client.session.session_key)
        self.assertEqual(self.client.post(f'{BASE}/unlink').status_code, 200)
        new, _ = self.start()
        require_active_flow(new, self.user.pk)
        self.assertEqual(self.result(self.callback(old)), 'expired')
        self.assertEqual(self.result(self.callback(new)), 'linked')

    def test_admin_only_unlinks_the_requested_identifier_and_preserves_unrelated_rows(self):
        save_verified_account_link(self.user, Platform.GITHUB, '123')
        stale = AccountLinkQueue.objects.create(userprofile=self.user, platform='g', identifier='456', verified=False)
        self.client.force_login(self.staff)
        token = self.client.get('/api/userprofile/admin/csrf').json()['csrf_token']
        body = {'id': self.user.pk, 'platform': 'g', 'identifier': '456'}
        self.assertEqual(self.client.post('/api/accountlink/unverify/', body, HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertFalse(AccountLinkQueue.objects.filter(pk=stale.pk).exists())
        self.assertEqual(AccountGitHub.objects.get().pk, 123)
        self.assertTrue(AccountLinkQueue.objects.filter(userprofile=self.user, platform='g', identifier='123', verified=True).exists())
        survivor = AccountLinkQueue.objects.create(userprofile=self.user, platform='g', identifier='789', verified=False)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post('/api/accountlink/unverify/', {**body, 'identifier': '123'}, HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertFalse(AccountGitHub.objects.exists())
        self.assertTrue(AccountLinkQueue.objects.filter(pk=survivor.pk).exists())

    def test_cancelling_an_old_flow_does_not_cancel_the_latest_or_another_browser(self):
        old, _ = self.start()
        new, _ = self.start()
        browser = Client()
        browser.force_login(self.user)
        self.assertEqual(browser.post(f'{BASE}/cancel', {'state': new}, content_type='application/json').status_code, 200)
        require_active_flow(new, self.user.pk)
        self.assertEqual(self.client.post(f'{BASE}/cancel', {'state': old}, content_type='application/json').status_code, 200)
        require_active_flow(new, self.user.pk)
        self.assertEqual(self.result(self.callback(old)), 'expired')
        self.assertEqual(self.client.post(f'{BASE}/cancel', {'state': new}, content_type='application/json').status_code, 200)
        self.assertEqual(self.result(self.callback(new)), 'expired')
        self.network.assert_not_called()
