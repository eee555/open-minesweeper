import asyncio
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Barrier, Event, Thread
from time import monotonic
from unittest import skipUnless
from unittest.mock import patch

from django.core.cache import cache
from django.db import close_old_connections, connection, connections
from django.test import SimpleTestCase, TestCase, TransactionTestCase
import httpx
from ninja.errors import HttpError

from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from .models import AccountLinkQueue, AccountSaolei, Platform
from .saolei.bind import fetch_remote_bind_request, SAOLEI_PUBLIC_BASE
from .saolei.cache import load_bind_evidence
from .saolei.services import confirm_saolei_account_link

BIND_BASE = '/api/accountlink/saolei/bind'
TOKEN = 'ab' * 24


def remote_payload(status=0, uid=101, username='扫雷网用户'):
    return {'status': status, 'uid': uid, 'username': username}


class FetchRemoteBindRequestTests(TestCase):
    def test_parses_public_payload(self):
        with patch('accountlink.saolei.bind.httpx.AsyncClient.get', return_value=httpx.Response(200, json=remote_payload())) as mock_get:
            self.assertEqual(fetch_remote_bind_request(TOKEN), remote_payload())
            self.assertEqual(mock_get.call_args.args[0], f'{SAOLEI_PUBLIC_BASE}/api/public/v1/openms/bind-request')
            self.assertEqual(mock_get.call_args.kwargs['params'], {'token': TOKEN})

    def test_total_wait_budget_interrupts_slow_upstream(self):
        """总超时必须取消请求本身，不能留下仍在运行的后台任务。"""
        cancelled = Event()

        async def blocked_request(*args, **kwargs):
            try:
                await asyncio.sleep(60)
            finally:
                cancelled.set()

        with patch('accountlink.saolei.bind.SAOLEI_PUBLIC_TOTAL_TIMEOUT', 0.1), patch('accountlink.saolei.bind.httpx.AsyncClient.get', side_effect=blocked_request):
            started = monotonic()
            with self.assertRaises(HttpError) as context:
                fetch_remote_bind_request(TOKEN)
            elapsed = monotonic() - started
        self.assertEqual(context.exception.status_code, 502)
        self.assertTrue(cancelled.is_set())
        self.assertLess(elapsed, 0.5)

    def test_missing_token_returns_none(self):
        with patch('accountlink.saolei.bind.httpx.AsyncClient.get', return_value=httpx.Response(404)):
            self.assertIsNone(fetch_remote_bind_request(TOKEN))

    def test_upstream_failures_are_502(self):
        for error in (httpx.ConnectError('unreachable'), httpx.ReadTimeout('stalled')):
            with self.subTest(error=type(error).__name__), patch('accountlink.saolei.bind.httpx.AsyncClient.get', side_effect=error):
                with self.assertRaises(HttpError) as context:
                    fetch_remote_bind_request(TOKEN)
                self.assertEqual(context.exception.status_code, 502)
        for status in (401, 429, 500):
            with self.subTest(status=status), patch('accountlink.saolei.bind.httpx.AsyncClient.get', return_value=httpx.Response(status)):
                with self.assertRaises(HttpError) as context:
                    fetch_remote_bind_request(TOKEN)
                self.assertEqual(context.exception.status_code, 502)

    def test_invalid_upstream_payload_is_502(self):
        responses = [httpx.Response(200, content=b'not JSON')]
        responses += [httpx.Response(200, json=data) for data in ([], {}, remote_payload(uid=0), remote_payload(uid=-1), remote_payload(uid=None))]
        for response in responses:
            with self.subTest(body=response.text), patch('accountlink.saolei.bind.httpx.AsyncClient.get', return_value=response):
                with self.assertRaises(HttpError) as context:
                    fetch_remote_bind_request(TOKEN)
                self.assertEqual(context.exception.status_code, 502)


class SlowBindHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.server.mode == 'fast':
            body = json.dumps(remote_payload()).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        try:
            if self.server.mode == 'headers':
                self.wfile.write(b'HTTP/1.1 200 OK\r\n')
                chunk = b'X-Slow: 1\r\n'
            else:
                self.send_response(200)
                self.send_header('Content-Length', '10000000')
                self.end_headers()
                chunk = b' '
            while not self.server.stop.wait(0.02):
                self.wfile.write(chunk)
                self.wfile.flush()
        except OSError:
            self.server.disconnected.set()
        finally:
            self.close_connection = True


class SaoleiBindHttpDeadlineTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), SlowBindHandler)
        cls.server.stop = Event()
        cls.server.disconnected = Event()
        cls.server.mode = 'fast'
        cls.server_thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop.set()
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join()
        super().tearDownClass()

    def test_slow_headers_and_repeated_slow_bodies_close_connections(self):
        base_url = f'http://127.0.0.1:{self.server.server_port}'
        with patch('accountlink.saolei.bind.SAOLEI_PUBLIC_BASE', base_url), patch('accountlink.saolei.bind.SAOLEI_PUBLIC_TOTAL_TIMEOUT', 0.2):
            for mode in ('headers', *['body'] * 5):
                with self.subTest(mode=mode):
                    self.server.mode = mode
                    self.server.disconnected.clear()
                    started = monotonic()
                    with self.assertRaises(HttpError) as context:
                        fetch_remote_bind_request(TOKEN)
                    self.assertEqual(context.exception.status_code, 502)
                    self.assertLess(monotonic() - started, 1)
                    self.assertTrue(self.server.disconnected.wait(1), 'Timed-out HTTP connection was not closed')
            self.server.mode = 'fast'
            self.assertEqual(fetch_remote_bind_request(TOKEN), remote_payload())


class SaoleiBindRequestTests(TestCase):
    def test_proxies_pending_request(self):
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            response = self.client.get(f'{BIND_BASE}/request', {'token': TOKEN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), remote_payload())

    def test_malformed_token_is_404(self):
        response = self.client.get(f'{BIND_BASE}/request', {'token': 'zz' * 24})
        self.assertEqual(response.status_code, 404)

    def test_unknown_token_is_404(self):
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=None):
            response = self.client.get(f'{BIND_BASE}/request', {'token': TOKEN})
        self.assertEqual(response.status_code, 404)


class SaoleiBindConfirmTests(TestCase):
    def setUp(self):
        self.user = UserProfile.objects.create_user(username='openms_user', email='openms_user@example.com')
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_requires_login(self):
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            response = self.client.post(f'{BIND_BASE}/confirm', {'token': TOKEN, 'sync': True}, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_creates_binding_rows_and_evidence(self):
        self.client.force_login(self.user)
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            response = self.client.post(f'{BIND_BASE}/confirm', {'token': TOKEN, 'sync': True}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'confirmed', 'uid': 101, 'sync': True})
        account = AccountSaolei.objects.get(pk=101)
        self.assertEqual((account.parent, account.name, account.auto_sync), (self.user, '扫雷网用户', True))
        # 每用户每平台恰好一条已验证关联（P2-3）
        self.assertEqual(AccountLinkQueue.objects.filter(platform=Platform.SAOLEI, userprofile=self.user, verified=True).count(), 1)
        self.assertTrue(AccountLinkQueue.objects.filter(platform=Platform.SAOLEI, identifier='101', userprofile=self.user, verified=True).exists())

    def test_sync_false_is_stored(self):
        self.client.force_login(self.user)
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            response = self.client.post(f'{BIND_BASE}/confirm', {'token': TOKEN, 'sync': False}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AccountSaolei.objects.get(pk=101).auto_sync)

    def test_profile_write_failure_rolls_back_binding(self):
        """name/auto_sync 与绑定必须同一事务，补写失败不得留下半完成状态。"""
        self.client.force_login(self.user)
        original_save = AccountSaolei.save
        reached_profile_write = []

        def fail_profile_write(account, *args, **kwargs):
            if kwargs.get('update_fields') == ['name', 'auto_sync']:
                reached_profile_write.append(AccountLinkQueue.objects.filter(platform=Platform.SAOLEI, userprofile=self.user, verified=True).exists())
                raise RuntimeError('write failed')
            return original_save(account, *args, **kwargs)

        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()), patch(
            'accountlink.saolei.services.AccountSaolei.save', autospec=True, side_effect=fail_profile_write,
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(f'{BIND_BASE}/confirm', {'token': TOKEN, 'sync': True}, content_type='application/json')
        self.assertEqual(reached_profile_write, [True])
        self.assertFalse(AccountSaolei.objects.exists())
        self.assertFalse(AccountLinkQueue.objects.exists())
        self.assertIsNone(load_bind_evidence(TOKEN))

    def test_confirm_replaces_another_pending_identifier_in_place(self):
        pending = AccountLinkQueue.objects.create(platform=Platform.SAOLEI, identifier='202', userprofile=self.user)
        self.client.force_login(self.user)
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            response = self.client.post(f'{BIND_BASE}/confirm', {'token': TOKEN, 'sync': False}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        pending.refresh_from_db()
        self.assertEqual((pending.identifier, pending.verified), ('101', True))
        self.assertEqual(AccountLinkQueue.objects.filter(platform=Platform.SAOLEI, userprofile=self.user).count(), 1)

    def test_evidence_write_failure_can_be_retried_without_duplicate_binding(self):
        self.client.force_login(self.user)
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            with patch('accountlink.saolei.bind.save_bind_evidence', side_effect=RuntimeError('cache unavailable')):
                with self.assertRaises(RuntimeError):
                    self.client.post(f'{BIND_BASE}/confirm', {'token': TOKEN, 'sync': False}, content_type='application/json')
            self.assertIsNone(load_bind_evidence(TOKEN))
            self.assertFalse(AccountSaolei.objects.get(pk=101).auto_sync)
            response = self.client.post(f'{BIND_BASE}/confirm', {'token': TOKEN, 'sync': False}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AccountSaolei.objects.count(), 1)
        self.assertEqual(AccountLinkQueue.objects.count(), 1)
        self.assertEqual(load_bind_evidence(TOKEN)['confirmer_id'], self.user.pk)

    def test_repeat_confirm_is_idempotent(self):
        self.client.force_login(self.user)
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            self.client.post(f'{BIND_BASE}/confirm', {'token': TOKEN, 'sync': True}, content_type='application/json')
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload(username='新名字')):
            response = self.client.post(f'{BIND_BASE}/confirm', {'token': TOKEN, 'sync': False}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        account = AccountSaolei.objects.get(pk=101)
        self.assertEqual((account.name, account.auto_sync), ('新名字', False))
        self.assertEqual(AccountSaolei.objects.count(), 1)
        self.assertEqual(AccountLinkQueue.objects.count(), 1)

    def test_uid_owned_by_other_user_conflicts(self):
        other = UserProfile.objects.create_user(username='other', email='other@example.com')
        AccountSaolei.objects.create(pk=101, parent=other)
        AccountLinkQueue.objects.create(platform=Platform.SAOLEI, identifier='101', userprofile=other, verified=True)
        self.client.force_login(self.user)
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            response = self.client.post(f'{BIND_BASE}/confirm', {'token': TOKEN, 'sync': True}, content_type='application/json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(AccountSaolei.objects.get(pk=101).parent, other)

    def test_user_linked_to_other_uid_conflicts(self):
        AccountSaolei.objects.create(pk=202, parent=self.user)
        AccountLinkQueue.objects.create(platform=Platform.SAOLEI, identifier='202', userprofile=self.user, verified=True)
        self.client.force_login(self.user)
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            response = self.client.post(f'{BIND_BASE}/confirm', {'token': TOKEN, 'sync': True}, content_type='application/json')
        self.assertEqual(response.status_code, 409)

    def test_non_pending_remote_is_404(self):
        self.client.force_login(self.user)
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload(status=1)):
            response = self.client.post(f'{BIND_BASE}/confirm', {'token': TOKEN, 'sync': True}, content_type='application/json')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(AccountSaolei.objects.exists())


class SaoleiBindStatusTests(TestCase):
    def setUp(self):
        self.user = UserProfile.objects.create_user(username='openms_user', email='openms_user@example.com')
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_pending_when_not_linked(self):
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            response = self.client.get(f'{BIND_BASE}/status', {'token': TOKEN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'profile': None, 'status': 'pending'})

    def test_confirmed_with_evidence(self):
        """本次令牌被确认过 → confirmed（P1-2 核心场景）。"""
        self.client.force_login(self.user)
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            self.client.post(f'{BIND_BASE}/confirm', {'token': TOKEN, 'sync': True}, content_type='application/json')
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            response = self.client.get(f'{BIND_BASE}/status', {'token': TOKEN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'profile': self.user.pk, 'status': 'confirmed'})

    def test_historical_binding_does_not_confirm_new_token(self):
        """已有绑定但本次令牌未确认 → 仍 pending（P1-2 修复点）。"""
        AccountSaolei.objects.create(pk=101, parent=self.user)
        AccountLinkQueue.objects.create(platform=Platform.SAOLEI, identifier='101', userprofile=self.user, verified=True)
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            response = self.client.get(f'{BIND_BASE}/status', {'token': TOKEN})
        self.assertEqual(response.json(), {'profile': None, 'status': 'pending'})

    def test_remote_settled_without_evidence_stays_pending(self):
        """已核销状态也不能替代本次令牌的确认者凭据。"""
        AccountSaolei.objects.create(pk=101, parent=self.user)
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload(status=1)):
            response = self.client.get(f'{BIND_BASE}/status', {'token': TOKEN})
        self.assertEqual(response.json(), {'profile': None, 'status': 'pending'})

    def test_cancelled_remote_stays_pending_even_with_evidence(self):
        """远端取消优先于本地确认凭据。"""
        self.client.force_login(self.user)
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            self.client.post(f'{BIND_BASE}/confirm', {'token': TOKEN, 'sync': True}, content_type='application/json')
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload(status=2)):
            response = self.client.get(f'{BIND_BASE}/status', {'token': TOKEN})
        self.assertEqual(response.json(), {'profile': None, 'status': 'pending'})

    def test_evidence_does_not_follow_uid_to_another_confirmer(self):
        """A 的旧令牌不得在 A 解绑、B 绑定同一 uid 后返回 B。"""
        other = UserProfile.objects.create_user(username='other', email='other@example.com')
        self.client.force_login(self.user)
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            self.client.post(f'{BIND_BASE}/confirm', {'token': TOKEN, 'sync': True}, content_type='application/json')
        AccountSaolei.objects.filter(pk=101).delete()
        AccountLinkQueue.objects.filter(platform=Platform.SAOLEI, userprofile=self.user).delete()
        AccountSaolei.objects.create(pk=101, parent=other)
        AccountLinkQueue.objects.create(platform=Platform.SAOLEI, identifier='101', userprofile=other, verified=True)
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            response = self.client.get(f'{BIND_BASE}/status', {'token': TOKEN})
        self.assertEqual(response.json(), {'profile': None, 'status': 'pending'})

    def test_unknown_token_is_404(self):
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=None):
            response = self.client.get(f'{BIND_BASE}/status', {'token': TOKEN})
        self.assertEqual(response.status_code, 404)


@skipUnless(connection.vendor == 'mysql', 'Binding concurrency requires MySQL row locks.')
class SaoleiBindConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = UserProfile.objects.create_user(username='first', email='first@example.com')
        self.other = UserProfile.objects.create_user(username='second', email='second@example.com')

    def confirm_concurrently(self, attempts):
        barrier = Barrier(2)

        def confirm(user_id, uid):
            close_old_connections()
            try:
                user = UserProfile.objects.get(pk=user_id)
                barrier.wait(timeout=5)
                try:
                    confirm_saolei_account_link(user, uid, 'Concurrent player', False)
                except ExceptionToResponse as exc:
                    self.assertEqual((exc.obj, exc.category, exc.status_code), ('accountlink', 'collision', 409))
                    return 'collision'
                return 'confirmed'
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(confirm, user_id, uid) for user_id, uid in attempts]
            return [future.result(timeout=10) for future in futures]

    def test_two_users_cannot_confirm_the_same_uid(self):
        self.assertCountEqual(self.confirm_concurrently([(self.user.pk, 101), (self.other.pk, 101)]), ['confirmed', 'collision'])
        account = AccountSaolei.objects.get(pk=101)
        link = AccountLinkQueue.objects.get(platform=Platform.SAOLEI, identifier='101', verified=True)
        self.assertEqual(link.userprofile_id, account.parent_id)
        self.assertFalse(account.auto_sync)

    def test_one_user_cannot_confirm_two_uids(self):
        self.assertCountEqual(self.confirm_concurrently([(self.user.pk, 101), (self.user.pk, 202)]), ['confirmed', 'collision'])
        account = AccountSaolei.objects.get(parent=self.user)
        link = AccountLinkQueue.objects.get(platform=Platform.SAOLEI, userprofile=self.user, verified=True)
        self.assertEqual(link.identifier, str(account.pk))
