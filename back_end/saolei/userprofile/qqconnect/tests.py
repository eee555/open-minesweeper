from importlib import import_module
import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.core.cache import caches
from django.db import transaction
from django.test import Client, override_settings, SimpleTestCase, TestCase
import requests

from msuser.models import UserMS
from utils.exceptions import ExceptionToResponse
from . import client
from ..models import EmailVerifyRecord, QQConnectIdentity, UserProfile

BASE = '/api/userprofile/qq'
IDENTITY = {'appid': '12345', 'openid': 'A' * 32, 'unionid': None, 'nickname': 'QQ Player', 'avatar_url': 'https://q.qlogo.cn/qqapp/avatar/40'}
QQ_SETTINGS = {
    'QQ_OAUTH_CLIENT_ID': '12345', 'QQ_OAUTH_CLIENT_SECRET': 'fake-test-secret',
    'QQ_OAUTH_REDIRECT_URI': 'https://openms.top/api/userprofile/qq/callback',
    'QQ_OAUTH_FRONTEND_URL': 'https://openms.top', 'QQ_OAUTH_LOGIN_ENABLED': True,
    'RATELIMIT_ENABLE': False,
}


@override_settings(**QQ_SETTINGS)
class QQClientTests(SimpleTestCase):
    def setUp(self):
        self.calls = []
        self.payloads = {
            '/oauth2.0/token': {'access_token': 'fake-test-token', 'expires_in': 7200},
            '/oauth2.0/me': {'client_id': '12345', 'openid': 'A' * 32},
            '/user/get_user_info': {'ret': 0, 'nickname': 'QQ Player', 'figureurl_qq_1': 'http://q.qlogo.cn/qqapp/avatar/40'},
        }
        network = patch('requests.sessions.Session.send', side_effect=self.respond)
        self.network = network.start()
        self.addCleanup(network.stop)

    def respond(self, request, **kwargs):
        self.calls.append(request)
        response = requests.Response()
        response.status_code = 200
        response.url = request.url
        response.request = request
        response._content = json.dumps(self.payloads[urlsplit(request.url).path]).encode()
        response._content_consumed = True
        return response

    def test_documented_protocol_and_minimum_scope(self):
        with client.oauth_client() as oauth:
            params = parse_qs(urlsplit(client.authorization_url(oauth, 'state')).query)
        self.assertEqual(params['scope'], ['get_user_info'])
        self.assertEqual(client.authorized_identity('authorization-code'), IDENTITY)
        query = parse_qs(urlsplit(self.calls[0].url).query)
        self.assertEqual(self.calls[0].method, 'GET')
        self.assertEqual(query['client_id'], ['12345'])
        self.assertEqual(query['client_secret'], ['fake-test-secret'])
        self.assertEqual(query['fmt'], ['json'])
        self.assertEqual(query['redirect_uri'], [QQ_SETTINGS['QQ_OAUTH_REDIRECT_URI']])
        self.assertEqual(parse_qs(urlsplit(self.calls[1].url).query)['access_token'], ['fake-test-token'])
        self.assertNotIn('Authorization', self.calls[1].headers)

    def test_identity_must_match_app_and_openid_format(self):
        for data in ({'client_id': 'other', 'openid': 'A' * 32}, {'client_id': '12345', 'openid': 'bad'}):
            self.payloads['/oauth2.0/me'] = data
            with self.subTest(data=data), self.assertRaises(ExceptionToResponse):
                client.authorized_identity('code')

    def test_authlib_errors_are_classified_without_credential_logs(self):
        self.payloads['/oauth2.0/token'] = {'error': 'invalid_grant', 'error_description': 'fake-test-secret'}
        with self.assertLogs('userprofile', level='WARNING') as logs, self.assertRaises(ExceptionToResponse) as caught:
            client.authorized_identity('code')
        self.assertEqual(caught.exception.category, 'remote_failed')
        self.assertNotIn('fake-test-secret', ''.join(logs.output))

    def test_profile_failure_does_not_invalidate_identity(self):
        self.payloads['/user/get_user_info'] = {'ret': 1002}
        with self.assertLogs('userprofile', level='WARNING'):
            data = client.authorized_identity('code')
        self.assertEqual(data['openid'], IDENTITY['openid'])
        self.assertEqual(data['nickname'], '')
        self.assertEqual(data['avatar_url'], '')

    def test_network_failure_and_unconfigured_client(self):
        self.network.side_effect = requests.ReadTimeout('fake-test-secret')
        with self.assertLogs('userprofile', level='WARNING'), self.assertRaises(ExceptionToResponse):
            client.authorized_identity('code')
        with override_settings(QQ_OAUTH_CLIENT_SECRET=''):
            self.assertFalse(client.configured())
            with self.assertRaises(ExceptionToResponse) as caught:
                client.oauth_client()
        self.assertEqual(caught.exception.category, 'not_configured')


@override_settings(**QQ_SETTINGS, CACHES={
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'qq-login-tests'},
    'saolei_website': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'qq-login-sessions'},
})
class QQLoginTests(TestCase):
    def setUp(self):
        caches['default'].clear()
        caches['saolei_website'].clear()
        self.user = UserProfile.objects.create_user(username='existing', email='existing@example.com', password='valid-password')

    def start(self, mode='login', browser=None):
        browser = browser or self.client
        response = browser.post(f'{BASE}/start', {'mode': mode}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        return parse_qs(urlsplit(response.json()['authorization_url']).query)['state'][0]

    def callback(self, state, browser=None, **kwargs):
        with patch('userprofile.qqconnect.client.authorized_identity', return_value=IDENTITY, **kwargs):
            return (browser or self.client).get(f'{BASE}/callback', {'state': state, 'code': 'code'})

    def test_unconfigured_start_creates_no_flow_or_account(self):
        with override_settings(QQ_OAUTH_CLIENT_ID=''):
            response = self.client.post(f'{BASE}/start', {'mode': 'login'}, content_type='application/json')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['category'], 'not_configured')
        self.assertEqual(UserProfile.objects.count(), 1)
        self.assertIsNone(self.client.session.get('qq_oauth_nonce'))

    def test_unknown_identity_requires_confirmation_and_registers_once(self):
        state = self.start()
        response = self.callback(state)
        self.assertIn('result=pending', response['Location'])
        self.assertEqual(UserProfile.objects.count(), 1)
        self.assertEqual(UserMS.objects.count(), 0)
        status = self.client.get(f'{BASE}/status')
        self.assertEqual(status.json()['pending']['nickname'], 'QQ Player')
        for private in ('openid', 'access_token', 'unionid', 'appid'):
            self.assertNotIn(private, status.content.decode())
        self.assertIn('no-store', status['Cache-Control'])
        response = self.client.post(f'{BASE}/register')
        self.assertEqual(response.status_code, 200, response.content)
        user = UserProfile.objects.get(pk=response.json()['user']['id'])
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_memorial)
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.email.endswith('@accounts.invalid'))
        self.assertIsNotNone(user.userms_id)
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))
        self.assertEqual(self.client.post(f'{BASE}/register').status_code, 409)
        self.assertEqual(UserProfile.objects.count(), 2)

    def test_existing_identity_logs_in_without_creating_user(self):
        QQConnectIdentity.objects.create(parent=self.user, **IDENTITY)
        response = self.callback(self.start())
        self.assertIn('result=logged_in', response['Location'])
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))
        self.assertEqual(UserProfile.objects.count(), 1)

    def test_bind_requires_current_user_and_refuses_transfer(self):
        response = self.client.post(f'{BASE}/start', {'mode': 'bind'}, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.user)
        self.assertIn('result=linked', self.callback(self.start('bind'))['Location'])
        other = UserProfile.objects.create_user(username='other', email='other@example.com', password='valid-password')
        self.client.force_login(other)
        self.assertIn('result=conflict', self.callback(self.start('bind'))['Location'])
        self.assertEqual(QQConnectIdentity.objects.get().parent_id, self.user.pk)

    def test_cross_session_and_replayed_callbacks_are_rejected(self):
        state = self.start()
        self.assertIn('result=expired', self.callback(state, browser=Client())['Location'])
        self.assertIn('result=pending', self.callback(state)['Location'])
        self.assertIn('result=expired', self.callback(state)['Location'])

    def test_cancellation_and_new_authorization_revoke_old_flows(self):
        old = self.start()
        state = self.start()
        self.assertIn('result=expired', self.callback(old)['Location'])
        response = self.client.get(f'{BASE}/callback', {'state': state, 'error': 'access_denied'})
        self.assertIn('result=cancelled', response['Location'])
        state = self.start()
        self.callback(state)
        self.assertEqual(self.client.post(f'{BASE}/cancel').status_code, 200)
        self.assertEqual(self.client.post(f'{BASE}/register').status_code, 409)
        self.assertEqual(UserProfile.objects.count(), 1)

    def test_deleted_session_cannot_be_resurrected_after_upstream_io(self):
        state = self.start()
        session_key = self.client.session.session_key

        def delete_session(*args):
            import_module(settings.SESSION_ENGINE).SessionStore(session_key).delete()
            return IDENTITY

        response = self.callback(state, side_effect=delete_session)
        self.assertIn('result=expired', response['Location'])
        self.assertFalse(QQConnectIdentity.objects.exists())
        self.assertIsNone(self.client.session.get(SESSION_KEY))

    def test_unlink_revokes_in_flight_binding(self):
        self.client.force_login(self.user)
        QQConnectIdentity.objects.create(parent=self.user, **IDENTITY)
        state = self.start('bind')

        def unlink(*args):
            with transaction.atomic():
                QQConnectIdentity.objects.filter(parent=self.user).delete()
            return IDENTITY

        self.assertIn('result=expired', self.callback(state, side_effect=unlink)['Location'])
        self.assertFalse(QQConnectIdentity.objects.exists())

    def test_inactive_identity_never_logs_in(self):
        QQConnectIdentity.objects.create(parent=self.user, **IDENTITY)
        UserProfile.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertIn('result=disabled', self.callback(self.start())['Location'])
        self.assertIsNone(self.client.session.get(SESSION_KEY))

    def test_registration_conflict_rolls_back_profile_and_userms(self):
        self.callback(self.start())
        QQConnectIdentity.objects.create(parent=self.user, **IDENTITY)
        response = self.client.post(f'{BASE}/register')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(UserProfile.objects.count(), 1)
        self.assertEqual(UserMS.objects.count(), 0)

    def test_recovery_email_before_unlink_and_password_reset(self):
        self.callback(self.start())
        response = self.client.post(f'{BASE}/register')
        user = UserProfile.objects.get(pk=response.json()['user']['id'])
        self.assertEqual(self.client.post(f'{BASE}/unlink').status_code, 409)
        EmailVerifyRecord.objects.create(email='recovery@example.com', code='123456', hashkey='recovery-key')
        response = self.client.post(f'{BASE}/recovery-email', {'email': 'recovery@example.com', 'email_key': 'recovery-key', 'email_captcha': '123456'}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        EmailVerifyRecord.objects.create(email='recovery@example.com', code='654321', hashkey='password-key')
        response = self.client.post('/userprofile/retrieve/', {'email': 'recovery@example.com', 'password': 'new-valid-password', 'email_key': 'password-key', 'email_captcha': '654321'})
        self.assertEqual(response.status_code, 200, response.content)
        user.refresh_from_db()
        self.assertTrue(user.check_password('new-valid-password'))
        self.assertEqual(self.client.post(f'{BASE}/unlink').status_code, 200)
        self.assertFalse(QQConnectIdentity.objects.filter(parent=user).exists())

    def test_admin_binding_requires_csrf_and_normal_user_does_not(self):
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.user)
        self.start('bind', browser)
        UserProfile.objects.filter(pk=self.user.pk).update(is_staff=True)
        self.assertEqual(browser.post(f'{BASE}/start', {'mode': 'bind'}, content_type='application/json').status_code, 403)
        browser.get('/api/userprofile/admin/csrf')
        response = browser.post(f'{BASE}/start', {'mode': 'bind'}, content_type='application/json', HTTP_X_CSRFTOKEN=browser.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200, response.content)

    def test_prebinding_switch_and_private_status(self):
        with override_settings(QQ_OAUTH_LOGIN_ENABLED=False):
            self.assertEqual(self.client.post(f'{BASE}/start', {'mode': 'login'}, content_type='application/json').status_code, 409)
            self.client.force_login(self.user)
            self.callback(self.start('bind'))
        self.assertTrue(self.client.get(f'{BASE}/status').json()['linked'])
        self.assertFalse(Client().get(f'{BASE}/status').json()['linked'])

    def test_generated_username_is_optional_moderated_and_set_once(self):
        self.callback(self.start())
        self.client.post(f'{BASE}/register')
        with patch('userprofile.qqconnect.services.verify_text', return_value=False):
            response = self.client.post(f'{BASE}/username', {'username': 'chosen'}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        with patch('userprofile.qqconnect.services.verify_text', return_value=True):
            response = self.client.post(f'{BASE}/username', {'username': 'chosen'}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['user']['username'], 'chosen')
        self.assertFalse(self.client.get(f'{BASE}/status').json()['can_set_username'])
        self.assertEqual(self.client.post(f'{BASE}/username', {'username': 'again'}, content_type='application/json').status_code, 409)
