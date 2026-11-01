from datetime import timedelta
import hashlib
import hmac
import json
from unittest import SkipTest
from unittest.mock import patch

from django.db import connection
from django.test import override_settings, SimpleTestCase, TestCase
from django.utils import timezone
import requests

from accountlink.classic.client import verify_classic_callback
from accountlink.models import AccountClassicMinesweeper, AccountLinkQueue, ClassicBindRequest, Platform
from userprofile.models import UserProfile

CLASSIC_TEST_SETTINGS = {
    'RATELIMIT_ENABLE': False,
    'CLASSIC_BIND_URL': 'https://classic.example.test/v1/ext/bind/request',
    'CLASSIC_BIND_CALLBACK_URL': 'https://openms.example.test/api/accountlink/classic/callback',
    'CLASSIC_BIND_EXPIRES_IN': 86400,
    'CLASSIC_TIMEOUT': 5,
    'CLASSIC_CALLBACK_TOLERANCE_SECONDS': 300,
}

CLASSIC_SECRETS = {'classic_bind_api_key': 'test-api-key', 'classic_callback_app_secret': 'test-app-secret'}


class ClassicFakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self.data = data

    def json(self):
        if self.data is None:
            raise ValueError
        return self.data


def bind_accepted(request_id=1024):
    return ClassicFakeResponse(data={
        'code': 0,
        'message': 'ok',
        'now': 1761520000000,
        'data': {'requestId': request_id, 'status': 0, 'expiresAt': '2026-10-28T01:00:00'},
    })


def read_secret(key, *args, **kwargs):
    return CLASSIC_SECRETS[key]


@override_settings(**CLASSIC_TEST_SETTINGS)
class ClassicCallbackSignatureTestCase(SimpleTestCase):
    def test_accepts_matching_signature(self):
        body = b'{"requestId":1}'
        signature = hmac.new(b'test-app-secret', b'1761520300.' + body, hashlib.sha256).hexdigest()

        with patch('accountlink.classic.client.time.time', return_value=1761520300):
            self.assertTrue(verify_classic_callback('test-app-secret', '1761520300', body, signature))

    def test_rejects_stale_timestamp(self):
        body = b'{"requestId":1}'
        signature = hmac.new(b'test-app-secret', b'1761520300.' + body, hashlib.sha256).hexdigest()

        with patch('accountlink.classic.client.time.time', return_value=1761520300 + 301):
            self.assertFalse(verify_classic_callback('test-app-secret', '1761520300', body, signature))

    def test_rejects_tampered_body_and_missing_secret(self):
        signature = hmac.new(b'test-app-secret', b'1761520300.{"requestId":1}', hashlib.sha256).hexdigest()

        with patch('accountlink.classic.client.time.time', return_value=1761520300):
            self.assertFalse(verify_classic_callback('test-app-secret', '1761520300', b'{"requestId":2}', signature))
            self.assertFalse(verify_classic_callback('', '1761520300', b'{"requestId":1}', signature))
            self.assertFalse(verify_classic_callback('test-app-secret', 'not-a-number', b'{"requestId":1}', signature))


@override_settings(**CLASSIC_TEST_SETTINGS)
class ClassicStartTestCase(TestCase):
    def setUp(self):
        if ClassicBindRequest._meta.db_table not in connection.introspection.table_names():
            raise SkipTest('ClassicBindRequest migration has not been generated yet.')
        self.user = UserProfile.objects.create_user(username='classic_user', email='classic_user@test.com')
        self.client.force_login(self.user)
        patcher = patch('accountlink.classic.client.read_secret', side_effect=read_secret)
        patcher.start()
        self.addCleanup(patcher.stop)

    @patch('accountlink.classic.client.requests.post')
    def test_start_requests_binding_and_stores_pending_request(self, requests_post):
        requests_post.return_value = bind_accepted()

        response = self.client.post('/api/accountlink/classic/start/', {'uid': '12345678'})

        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body['status'], 'pending')
        self.assertEqual(body['uid'], 12345678)
        self.assertEqual(body['request_id'], 1024)
        self.assertIsNotNone(body['expires_at'])
        _, kwargs = requests_post.call_args
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer test-api-key')
        self.assertEqual(kwargs['json']['uid'], 12345678)
        self.assertEqual(kwargs['json']['account'], 'classic_user')
        self.assertEqual(kwargs['json']['callback'], CLASSIC_TEST_SETTINGS['CLASSIC_BIND_CALLBACK_URL'])
        self.assertEqual(kwargs['json']['method'], 'POST')
        record = ClassicBindRequest.objects.get(uid=12345678)
        self.assertEqual(record.status, ClassicBindRequest.Status.PENDING)
        # 受理不等于绑定：待确认阶段不写入关联队列。
        self.assertFalse(AccountLinkQueue.objects.filter(userprofile=self.user, platform=Platform.CLASSIC).exists())

    @patch('accountlink.classic.client.requests.post')
    def test_start_reuses_pending_request_without_calling_remote_again(self, requests_post):
        requests_post.return_value = bind_accepted()
        self.client.post('/api/accountlink/classic/start/', {'uid': '12345678'})

        response = self.client.post('/api/accountlink/classic/start/', {'uid': '12345678'})

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['request_id'], 1024)
        self.assertEqual(requests_post.call_count, 1)

    @patch('accountlink.classic.client.requests.post')
    def test_start_rejects_invalid_uid_and_existing_binding(self, requests_post):
        for uid in ('1234567', '123456789'):
            with self.subTest(uid=uid):
                response = self.client.post('/api/accountlink/classic/start/', {'uid': uid})
                self.assertEqual(response.status_code, 400, response.content)
                self.assertEqual(response.json()['category'], 'bad_request')
        self.assertEqual(self.client.post('/api/accountlink/classic/start/', {'uid': 'abcdefgh'}).status_code, 422)
        requests_post.assert_not_called()

        AccountClassicMinesweeper.objects.create(id=12345678, parent=self.user)
        response = self.client.post('/api/accountlink/classic/start/', {'uid': '12345678'})
        self.assertEqual(response.json()['category'], 'already_linked')

    @patch('accountlink.classic.client.requests.post')
    def test_start_rejects_uid_owned_by_another_user_or_pending_elsewhere(self, requests_post):
        other = UserProfile.objects.create_user(username='classic_other', email='classic_other@test.com')
        AccountClassicMinesweeper.objects.create(id=12345678, parent=other)

        response = self.client.post('/api/accountlink/classic/start/', {'uid': '12345678'})

        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['category'], 'identifier_conflict')

        AccountClassicMinesweeper.objects.all().delete()
        ClassicBindRequest.objects.create(
            uid=12345678, request_id=99, userprofile=other, account='classic_other',
            expires_at=timezone.now() + timedelta(hours=1),
        )
        response = self.client.post('/api/accountlink/classic/start/', {'uid': '12345678'})
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['category'], 'pending')
        requests_post.assert_not_called()

    @patch('accountlink.classic.client.requests.post')
    def test_start_maps_remote_errors(self, requests_post):
        cases = [
            (404, 40401, 'uid_not_found', 404),
            (409, 40901, 'already_bound', 409),
            (409, 40902, 'denied_recently', 409),
            (409, 40903, 'revoked_recently', 409),
            (429, 42901, 'rate_limited', 429),
            (400, 40001, 'bad_request', 400),
            (401, 40101, 'unauthorized', 502),
        ]
        for _, code, category, status_code in cases:
            with self.subTest(code=code):
                requests_post.return_value = ClassicFakeResponse(status_code=status_code, data={'code': code, 'message': 'error'})
                response = self.client.post('/api/accountlink/classic/start/', {'uid': '12345678'})
                self.assertEqual(response.status_code, status_code, response.content)
                self.assertEqual(response.json()['category'], category)
        self.assertFalse(ClassicBindRequest.objects.exists())

    @patch('accountlink.classic.client.requests.post')
    def test_start_reports_missing_credentials_and_network_failures(self, requests_post):
        with patch('accountlink.classic.client.read_secret', side_effect=FileNotFoundError('secrets.json')):
            with self.assertRaises(FileNotFoundError):
                self.client.post('/api/accountlink/classic/start/', {'uid': '12345678'})

        requests_post.side_effect = requests.exceptions.Timeout()
        response = self.client.post('/api/accountlink/classic/start/', {'uid': '12345678'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['category'], 'timeout')

    def test_start_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.post('/api/accountlink/classic/start/', {'uid': '12345678'}).status_code, 403)


@override_settings(**CLASSIC_TEST_SETTINGS)
class ClassicCallbackTestCase(TestCase):
    def setUp(self):
        if ClassicBindRequest._meta.db_table not in connection.introspection.table_names():
            raise SkipTest('ClassicBindRequest migration has not been generated yet.')
        self.user = UserProfile.objects.create_user(username='classic_callback', email='classic_callback@test.com')
        self.record = ClassicBindRequest.objects.create(
            uid=12345678,
            request_id=1024,
            userprofile=self.user,
            account='classic_callback',
            expires_at=timezone.now() + timedelta(hours=1),
        )
        patcher = patch('accountlink.classic.client.read_secret', side_effect=read_secret)
        patcher.start()
        self.addCleanup(patcher.stop)

    def callback(self, result, *, uid=12345678, request_id=1024, account='classic_callback', secret='test-app-secret', timestamp=None):
        payload = {
            'requestId': request_id,
            'uid': uid,
            'app': 'OpenMS',
            'account': account,
            'result': result,
            'handledAt': 1761520300,
            'revokedAt': None,
        }
        body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        timestamp = str(int(timezone.now().timestamp()) if timestamp is None else timestamp)
        signature = hmac.new(secret.encode(), f'{timestamp}.'.encode() + body, hashlib.sha256).hexdigest()
        return self.client.post(
            '/api/accountlink/classic/callback', data=body, content_type='application/json',
            HTTP_X_EXT_TIMESTAMP=timestamp, HTTP_X_EXT_SIGNATURE=signature,
        )

    def test_allow_creates_binding_and_is_idempotent(self):
        response = self.callback('allow')

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(AccountClassicMinesweeper.objects.filter(pk=12345678, parent=self.user).exists())
        self.assertTrue(AccountLinkQueue.objects.filter(
            platform=Platform.CLASSIC, identifier='12345678', userprofile=self.user, verified=True,
        ).exists())
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, ClassicBindRequest.Status.ALLOWED)

        self.assertEqual(self.callback('allow').status_code, 200)
        self.assertEqual(AccountLinkQueue.objects.filter(platform=Platform.CLASSIC).count(), 1)

    def test_allow_conflict_is_recorded_without_binding(self):
        other = UserProfile.objects.create_user(username='classic_conflict', email='classic_conflict@test.com')
        AccountClassicMinesweeper.objects.create(id=12345678, parent=other)

        response = self.callback('allow')

        self.assertEqual(response.status_code, 200, response.content)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, ClassicBindRequest.Status.CONFLICT)
        self.assertEqual(AccountClassicMinesweeper.objects.get(pk=12345678).parent, other)

    def test_deny_records_decision_without_binding(self):
        self.assertEqual(self.callback('deny').status_code, 200)

        self.record.refresh_from_db()
        self.assertEqual(self.record.status, ClassicBindRequest.Status.DENIED)
        self.assertFalse(AccountClassicMinesweeper.objects.exists())
        self.assertFalse(AccountLinkQueue.objects.exists())

    def test_revoke_removes_binding_and_queue(self):
        self.callback('allow')

        self.assertEqual(self.callback('revoke').status_code, 200)

        self.record.refresh_from_db()
        self.assertEqual(self.record.status, ClassicBindRequest.Status.REVOKED)
        self.assertFalse(AccountClassicMinesweeper.objects.exists())
        self.assertFalse(AccountLinkQueue.objects.exists())
        # 重复的 revoke 同样幂等。
        self.assertEqual(self.callback('revoke').status_code, 200)

    def test_callback_rejects_bad_signature_payload_and_unknown_request(self):
        self.assertEqual(self.callback('allow', secret='wrong-secret').status_code, 401)
        self.assertFalse(AccountClassicMinesweeper.objects.exists())

        self.assertEqual(self.callback('allow', timestamp='1').status_code, 401)

        self.assertEqual(self.callback('allow', uid=87654321).status_code, 400)
        self.assertEqual(self.callback('allow', account='someone-else').status_code, 400)

        self.assertEqual(self.callback('allow', request_id=2048).status_code, 404)
        self.assertFalse(AccountClassicMinesweeper.objects.exists())

    def test_callback_rejects_malformed_body(self):
        timestamp = str(int(timezone.now().timestamp()))
        body = b'not json'
        signature = hmac.new(b'test-app-secret', f'{timestamp}.'.encode() + body, hashlib.sha256).hexdigest()

        response = self.client.post(
            '/api/accountlink/classic/callback', data=body, content_type='application/json',
            HTTP_X_EXT_TIMESTAMP=timestamp, HTTP_X_EXT_SIGNATURE=signature,
        )

        self.assertEqual(response.status_code, 400, response.content)


@override_settings(RATELIMIT_ENABLE=False)
class ClassicManualLinkRejectionTestCase(TestCase):
    def setUp(self):
        self.user = UserProfile.objects.create_user(username='classic_manual', email='classic_manual@test.com', is_staff=True)
        self.client.force_login(self.user)

    def test_generic_create_rejects_classic(self):
        response = self.client.post('/api/accountlink/create/', {'platform': Platform.CLASSIC, 'identifier': '12345678'})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(AccountLinkQueue.objects.exists())

    def test_staff_verify_and_unverify_reject_classic(self):
        AccountLinkQueue.objects.create(platform=Platform.CLASSIC, identifier='12345678', userprofile=self.user)

        verify = self.client.post('/api/accountlink/verify/', {'id': self.user.id, 'platform': Platform.CLASSIC, 'identifier': '12345678'})
        self.assertEqual(verify.status_code, 400, verify.content)
        self.assertEqual(verify.json()['category'], 'manual_link_not_supported')

        unverify = self.client.post('/api/accountlink/unverify/', {'id': self.user.id, 'platform': Platform.CLASSIC, 'identifier': '12345678'})
        self.assertEqual(unverify.status_code, 409, unverify.content)
        self.assertEqual(unverify.json()['category'], 'unlink_not_supported')

    def test_self_unlink_and_refresh_reject_classic(self):
        AccountLinkQueue.objects.create(platform=Platform.CLASSIC, identifier='12345678', userprofile=self.user, verified=True)

        delete = self.client.post('/accountlink/delete/', {'platform': Platform.CLASSIC})
        self.assertEqual(delete.status_code, 409, delete.content)

        update = self.client.post('/accountlink/update/', {'platform': Platform.CLASSIC})
        self.assertEqual(update.status_code, 400, update.content)
        self.assertEqual(update.json()['category'], 'update_not_supported')


@override_settings(**CLASSIC_TEST_SETTINGS)
class ClassicAccountLinksTestCase(TestCase):
    def setUp(self):
        self.user = UserProfile.objects.create_user(username='classic_viewer', email='classic_viewer@test.com')
        AccountClassicMinesweeper.objects.create(id=12345678, parent=self.user)
        AccountLinkQueue.objects.create(platform=Platform.CLASSIC, identifier='12345678', userprofile=self.user, verified=True)

    def test_complete_response_includes_classic_details(self):
        response = self.client.get(f'/api/accountlink/{self.user.pk}')

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['x']['id'], 12345678)

    def test_status_returns_latest_request(self):
        self.client.force_login(self.user)
        ClassicBindRequest.objects.create(
            uid=12345678, request_id=1024, userprofile=self.user, account='classic_viewer',
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        response = self.client.get('/api/accountlink/classic/status/')

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['status'], 'expired')

    def test_status_without_request(self):
        self.client.force_login(self.user)
        ClassicBindRequest.objects.all().delete()

        response = self.client.get('/api/accountlink/classic/status/')

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['status'], 'none')
        self.assertIsNone(response.json()['uid'])
