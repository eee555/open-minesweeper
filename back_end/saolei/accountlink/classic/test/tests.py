from datetime import timedelta
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
from unittest import SkipTest
from unittest.mock import patch

from django.db import connection
from django.test import override_settings, SimpleTestCase, TestCase
from django.utils import timezone
import requests

from accountlink.classic.client import request_classic_bind, verify_classic_callback
from accountlink.classic.services import _store_classic_request
from accountlink.models import AccountClassicMinesweeper, AccountLinkQueue, ClassicBindRequest, ClassicReplay, Platform
from config.text_choices import MS_TextChoices
from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from videomanager.models import ExpandVideoModel, VideoModel

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
        self.raw = json.dumps(data).encode('utf-8') if data is not None else b''

    def iter_content(self, chunk_size=1):
        for index in range(0, len(self.raw), chunk_size):
            yield self.raw[index:index + chunk_size]

    def close(self):
        pass


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


class ClassicDripServer:
    """按固定间隔逐字节返回的本地服务：requests 的单次读超时挡不住这种慢速响应。"""

    def __init__(self, total_bytes=40, interval=0.2):
        handler = type('DripHandler', (_DripHandler,), {'total_bytes': total_bytes, 'interval': interval})
        self._server = ThreadingHTTPServer(('127.0.0.1', 0), handler)

    def __enter__(self) -> str:
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return f'http://127.0.0.1:{self._server.server_address[1]}/v1/ext/bind/request'

    def __exit__(self, *exc_info):
        self._server.shutdown()
        self._server.server_close()


class _DripHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    total_bytes = 40
    interval = 0.2

    def do_POST(self):
        # 客户端会在截止时间主动断开，关掉长连接避免服务端在读下一行时报错刷屏。
        self.close_connection = True
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(self.total_bytes))
        self.send_header('Connection', 'close')
        self.end_headers()
        try:
            for _ in range(self.total_bytes):
                self.wfile.write(b' ')
                self.wfile.flush()
                time.sleep(self.interval)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass


@override_settings(**CLASSIC_TEST_SETTINGS)
class ClassicRequestDeadlineTestCase(SimpleTestCase):
    def test_slow_drip_response_is_cut_by_the_overall_deadline(self):
        with ClassicDripServer() as url, override_settings(
            CLASSIC_BIND_URL=url, CLASSIC_TIMEOUT=1.0, CLASSIC_CONNECT_TIMEOUT=1.0,
        ), patch('accountlink.classic.client.read_secret', side_effect=read_secret):
            started = time.monotonic()
            with self.assertRaises(ExceptionToResponse) as caught:
                request_classic_bind(12345678, 'classic_user', 'https://example.test/cb', 86400)
            elapsed = time.monotonic() - started

        # 服务端每秒才给一个字节，单次读超时永远不会触发；整体截止时间必须在 1s 左右放行。
        self.assertEqual(caught.exception.category, 'timeout')
        self.assertLess(elapsed, 4)


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
    def test_repeat_request_keeps_denied_state(self, requests_post):
        requests_post.return_value = bind_accepted()
        self.client.post('/api/accountlink/classic/start/', {'uid': '12345678'})
        ClassicBindRequest.objects.filter(uid=12345678).update(
            status=ClassicBindRequest.Status.DENIED, handled_at=timezone.now(),
        )

        response = self.client.post('/api/accountlink/classic/start/', {'uid': '12345678'})

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['status'], 'deny')
        self.assertEqual(ClassicBindRequest.objects.get(uid=12345678).status, ClassicBindRequest.Status.DENIED)

    def test_idempotent_repeat_keeps_allowed_state(self):
        ClassicBindRequest.objects.create(
            uid=12345678,
            request_id=1024,
            userprofile=self.user,
            account='classic_user',
            status=ClassicBindRequest.Status.ALLOWED,
            handled_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
        )

        record = _store_classic_request(self.user, 12345678, 1024, timezone.now() + timedelta(hours=1))

        self.assertEqual(record.status, ClassicBindRequest.Status.ALLOWED)
        stored = ClassicBindRequest.objects.get(uid=12345678)
        self.assertEqual(stored.status, ClassicBindRequest.Status.ALLOWED)
        self.assertIsNotNone(stored.handled_at)

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

    def test_stale_callback_after_uid_takeover_binds_nobody(self):
        # 同一 UID 的新申请覆盖旧申请：requestId 与 account 都已改变。
        other = UserProfile.objects.create_user(username='classic_takeover', email='classic_takeover@test.com')
        self.record.request_id = 2048
        self.record.userprofile = other
        self.record.account = 'classic_takeover'
        self.record.save(update_fields=['request_id', 'userprofile', 'account', 'updated_at'])

        # 旧申请（requestId=1024，account=classic_callback）的确认回调不得绑定到新申请人。
        response = self.callback('allow')

        self.assertEqual(response.status_code, 404, response.content)
        self.assertEqual(self.callback('deny').status_code, 404)
        self.assertEqual(self.callback('revoke').status_code, 404)
        self.assertFalse(AccountClassicMinesweeper.objects.exists())
        self.assertFalse(AccountLinkQueue.objects.exists())

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

    def test_status_keeps_completed_result_after_expiry(self):
        self.client.force_login(self.user)
        ClassicBindRequest.objects.create(
            uid=12345678, request_id=1024, userprofile=self.user, account='classic_viewer',
            status=ClassicBindRequest.Status.ALLOWED, expires_at=timezone.now() - timedelta(seconds=1),
        )

        response = self.client.get('/api/accountlink/classic/status/')

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['status'], 'allow')
        self.assertEqual(ClassicBindRequest.objects.get(uid=12345678).status, ClassicBindRequest.Status.ALLOWED)


@override_settings(**CLASSIC_TEST_SETTINGS)
class ClassicReplayPushTestCase(TestCase):
    def setUp(self):
        if ClassicReplay._meta.db_table not in connection.introspection.table_names():
            raise SkipTest('ClassicReplay migration has not been generated yet.')
        self.user = UserProfile.objects.create_user(username='classic_replay', email='classic_replay@test.com')
        AccountClassicMinesweeper.objects.create(id=12345678, parent=self.user)
        AccountLinkQueue.objects.create(platform=Platform.CLASSIC, identifier='12345678', userprofile=self.user, verified=True)
        self.video = VideoModel.objects.create(
            player=self.user, video=ExpandVideoModel.objects.create(identifier='classic_replay'),
            file='classic.evf', software=MS_TextChoices.Software.EVF, level=MS_TextChoices.Level.EXPERT,
            mode=MS_TextChoices.Mode.STD, timems=61234, bv=183,
        )
        patcher = patch('accountlink.classic.client.read_secret', side_effect=read_secret)
        patcher.start()
        self.addCleanup(patcher.stop)

    def push(self, *, body=b'evf-bytes', secret='test-app-secret', timestamp=None, overrides=None):
        meta = {
            'X-Ext-Event': 'replay', 'X-Ext-Uid': '12345678', 'X-Ext-Sync-Id': '88',
            'X-Ext-Key': '263-81', 'X-Ext-Season': '263', 'X-Ext-Platform': 'pc',
            'X-Ext-Difficulty': 'expert', 'X-Ext-Played-At': '1761510000000',
            'X-Ext-Time-Ms': '61234', 'X-Ext-Bv3': '183',
            'X-Ext-Nf': '0', 'X-Ext-Sha256': hashlib.sha256(body).hexdigest(), 'X-Ext-Format': 'evf',
        }
        meta.update(overrides or {})
        timestamp = str(int(timezone.now().timestamp()) if timestamp is None else timestamp)
        signature = hmac.new(secret.encode(), f'{timestamp}.'.encode() + body, hashlib.sha256).hexdigest()
        return self.client.post(
            '/api/accountlink/classic/callback', data=body, content_type='application/octet-stream',
            HTTP_X_EXT_TIMESTAMP=timestamp, HTTP_X_EXT_SIGNATURE=signature,
            **{f'HTTP_{name.upper().replace("-", "_")}': value for name, value in meta.items()},
        )

    def fake_import(self, replay, data):
        replay.import_video = self.video
        replay.save(update_fields=['import_video'])
        return self.video

    @patch('accountlink.classic.services._import_classic_replay')
    def test_replay_is_imported_once_and_idempotent(self, import_replay):
        import_replay.side_effect = self.fake_import

        response = self.push()

        self.assertEqual(response.status_code, 200, response.content)
        replay = ClassicReplay.objects.get(uid=12345678, key='263-81')
        self.assertEqual(replay.sync_id, 88)
        self.assertEqual(replay.season, 263)
        self.assertEqual(replay.platform, 'pc')
        self.assertEqual(replay.difficulty, 'e')
        self.assertEqual(replay.time_ms, 61234)
        self.assertEqual(replay.bv3, 183)
        self.assertFalse(replay.nf)
        self.assertEqual(replay.file_size, len(b'evf-bytes'))
        self.assertEqual(replay.sha256, hashlib.sha256(b'evf-bytes').hexdigest())
        self.assertEqual(replay.import_video, self.video)
        self.assertEqual(replay.error_category, '')
        self.assertEqual(import_replay.call_count, 1)

        # 重试使用同一 syncId，不再解析或新增记录。
        self.assertEqual(self.push().status_code, 200)
        self.assertEqual(import_replay.call_count, 1)
        self.assertEqual(ClassicReplay.objects.count(), 1)

    @patch('accountlink.classic.services._import_classic_replay')
    def test_new_sync_id_overwrites_the_same_key(self, import_replay):
        import_replay.side_effect = self.fake_import
        self.push()

        response = self.push(overrides={'X-Ext-Sync-Id': '99'})

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(ClassicReplay.objects.count(), 1)
        self.assertEqual(ClassicReplay.objects.get().sync_id, 99)
        self.assertEqual(import_replay.call_count, 1)

    @patch('accountlink.classic.services._import_classic_replay')
    def test_sync_id_cannot_be_reused_for_another_key(self, import_replay):
        import_replay.side_effect = self.fake_import
        self.push()

        response = self.push(overrides={'X-Ext-Key': '263-82'})

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()['category'], 'sync_id_conflict')
        self.assertEqual(ClassicReplay.objects.count(), 1)

    @patch('accountlink.classic.services._import_classic_replay')
    def test_key_cannot_belong_to_another_uid(self, import_replay):
        import_replay.side_effect = self.fake_import
        self.push()

        response = self.push(overrides={'X-Ext-Uid': '87654321', 'X-Ext-Sync-Id': '99'})

        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['category'], 'key_conflict')
        replay = ClassicReplay.objects.get(key='263-81')
        self.assertEqual(replay.uid, 12345678)
        self.assertEqual(import_replay.call_count, 1)

    def test_rejects_bad_signature_and_checksum(self):
        self.assertEqual(self.push(secret='wrong-secret').status_code, 401)
        self.assertFalse(ClassicReplay.objects.exists())

        response = self.push(overrides={'X-Ext-Sha256': '0' * 64})

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()['category'], 'bad_checksum')
        self.assertFalse(ClassicReplay.objects.exists())

    def test_rejects_malformed_headers(self):
        for overrides in (
            {'X-Ext-Event': 'bind'}, {'X-Ext-Format': 'avf'}, {'X-Ext-Key': '81'},
            {'X-Ext-Season': '264'}, {'X-Ext-Platform': 'web'}, {'X-Ext-Difficulty': 'custom'},
            {'X-Ext-Nf': '2'}, {'X-Ext-Uid': '12345'},
        ):
            with self.subTest(overrides=overrides):
                self.assertEqual(self.push(overrides=overrides).status_code, 400)
        self.assertFalse(ClassicReplay.objects.exists())

    @patch('accountlink.classic.services.CLASSIC_REPLAY_MAX_BYTES', 16)
    def test_rejects_oversized_body(self):
        self.assertEqual(self.push(body=b'x' * 17).status_code, 413)
        self.assertFalse(ClassicReplay.objects.exists())

    @patch('accountlink.classic.services._import_classic_replay', side_effect=ExceptionToResponse('file', 'incomplete', status_code=400))
    def test_import_failure_keeps_the_record_for_retry(self, import_replay):
        response = self.push()

        self.assertEqual(response.status_code, 400, response.content)
        replay = ClassicReplay.objects.get(uid=12345678, key='263-81')
        self.assertEqual(replay.error_category, 'incomplete')
        self.assertIsNone(replay.import_video_id)

    def test_unbound_player_is_acknowledged_without_import(self):
        AccountClassicMinesweeper.objects.all().delete()
        AccountLinkQueue.objects.all().delete()

        response = self.push()

        self.assertEqual(response.status_code, 200, response.content)
        replay = ClassicReplay.objects.get(uid=12345678, key='263-81')
        self.assertEqual(replay.error_category, 'unbound')
        self.assertIsNone(replay.import_video_id)
