from unittest.mock import patch

from django.test import TestCase

from userprofile.models import UserProfile
from .models import AccountLinkQueue, AccountSaolei, Platform
from .saolei.bind import fetch_remote_bind_request, SAOLEI_PUBLIC_BASE

BIND_BASE = '/api/accountlink/saolei/bind'
TOKEN = 'ab' * 24


def remote_payload(status=0, uid=101, username='扫雷网用户'):
    return {'status': status, 'uid': uid, 'username': username}


class FetchRemoteBindRequestTests(TestCase):
    def test_parses_public_payload(self):
        with patch('accountlink.saolei.bind.httpx.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = remote_payload()
            self.assertEqual(fetch_remote_bind_request(TOKEN), remote_payload())
            self.assertEqual(mock_get.call_args.args[0], f'{SAOLEI_PUBLIC_BASE}/api/public/v1/openms/bind-request')
            self.assertEqual(mock_get.call_args.kwargs['params'], {'token': TOKEN})

    def test_missing_token_returns_none(self):
        with patch('accountlink.saolei.bind.httpx.get') as mock_get:
            mock_get.return_value.status_code = 404
            self.assertIsNone(fetch_remote_bind_request(TOKEN))


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

    def test_requires_login(self):
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            response = self.client.post(f'{BIND_BASE}/confirm', {'token': TOKEN, 'sync': True}, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_creates_binding_rows(self):
        self.client.force_login(self.user)
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            response = self.client.post(f'{BIND_BASE}/confirm', {'token': TOKEN, 'sync': True}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'confirmed', 'uid': 101, 'sync': True})
        account = AccountSaolei.objects.get(pk=101)
        self.assertEqual((account.parent, account.name, account.auto_sync), (self.user, '扫雷网用户', True))
        self.assertTrue(AccountLinkQueue.objects.filter(platform=Platform.SAOLEI, identifier='101', userprofile=self.user, verified=True).exists())

    def test_sync_false_is_stored(self):
        self.client.force_login(self.user)
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            response = self.client.post(f'{BIND_BASE}/confirm', {'token': TOKEN, 'sync': False}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AccountSaolei.objects.get(pk=101).auto_sync)

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

    def test_pending_when_not_linked(self):
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            response = self.client.get(f'{BIND_BASE}/status', {'token': TOKEN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'profile': None, 'status': 'pending'})

    def test_confirmed_with_profile_when_linked(self):
        AccountSaolei.objects.create(pk=101, parent=self.user)
        AccountLinkQueue.objects.create(platform=Platform.SAOLEI, identifier='101', userprofile=self.user, verified=True)
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=remote_payload()):
            response = self.client.get(f'{BIND_BASE}/status', {'token': TOKEN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'profile': self.user.pk, 'status': 'confirmed'})

    def test_unknown_token_is_404(self):
        with patch('accountlink.saolei.bind.fetch_remote_bind_request', return_value=None):
            response = self.client.get(f'{BIND_BASE}/status', {'token': TOKEN})
        self.assertEqual(response.status_code, 404)
