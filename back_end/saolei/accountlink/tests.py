import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import SkipTest
from unittest.mock import patch

from django.core.cache import caches
from django.db import connection
from django.test import override_settings, SimpleTestCase, TestCase
from django.utils import timezone
import requests

from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from .api import MineracerAccountLinkSessionOut
from .mineracer.client import poll_mineracer_account_link, request_mineracer_account_link
from .mineracer.dtos import MINERACER_ERROR_ACCOUNT_NOT_FOUND, MINERACER_ERROR_INVALID_DEVICE_CODE, MINERACER_ERROR_LINK_SUPERSEDED, MINERACER_STATUS_CONFIRMED, MINERACER_STATUS_EXPIRED, MINERACER_STATUS_FAILED, MINERACER_STATUS_PENDING, MineracerAccountLinkPollResponse, MineracerAccountLinkSession, MineracerAccountLinkStartResponse
from .mineracer.sessions import _get_mineracer_session, _save_mineracer_session, _save_user_pending_mineracer_session
from .models import AccountBilibili, AccountLinkQueue, AccountMineracer, AccountMinesweeperGames, AccountSaolei, Platform
from .services import update_saolei_account_info
from .utils import isPrivate, private_platforms, update_bilibili_account


@override_settings(RATELIMIT_ENABLE=False)
class NamePrivacyBindingTests(TestCase):
    def setUp(self):
        self.staff = UserProfile.objects.create_user(username='binding_staff', email='binding_staff@test.com', is_staff=True)
        self.user = UserProfile.objects.create_user(username='binding_user', email='binding_user@test.com', realname='真实姓名')
        self.link = AccountLinkQueue.objects.create(userprofile=self.user, platform=Platform.MSGAMES, identifier='1234')
        self.client.force_login(self.staff)

    def verify(self, user=None):
        return self.client.post('/api/accountlink/verify/', {'id': (user or self.user).pk, 'platform': Platform.MSGAMES, 'identifier': self.link.identifier})

    @patch('accountlink.msgames.client.msgames_client', side_effect=AssertionError('Unexpected external MSGames request'))
    def test_verification_saves_msgames_names_before_returning(self, remote):
        self.link.identifier = '2147483000'
        self.link.save(update_fields=['identifier'])
        with TemporaryDirectory() as root, override_settings(E2E_TEST=True, DEBUG=True, PRODUCTION_MARK=Path(root) / '.production'):
            response = self.verify()
        self.assertEqual(response.status_code, 200, response.content)
        account = AccountMinesweeperGames.objects.get(parent=self.user)
        self.assertEqual((account.name, account.local_name), ('MSGames Fixture', '关联姓名'))
        remote.assert_not_called()

    @patch('accountlink.services.fetch_msgames_profile', return_value={'name': 'Linked Name', 'local_name': '关联姓名'})
    def test_binding_grants_once_and_unlink_keeps_privacy(self, sync):
        self.assertFalse(self.user.can_hide_realname)
        self.assertEqual(self.verify().status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.can_hide_realname)
        self.assertFalse(self.user.hide_realname)
        self.assertEqual(AccountMinesweeperGames.objects.get(pk=1234).parent_id, self.user.pk)
        self.user.hide_realname = True
        self.user.save(update_fields=['hide_realname'])
        self.client.force_login(self.user)
        self.assertEqual(self.client.post('/accountlink/delete/', {'platform': Platform.MSGAMES}).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.can_hide_realname)
        self.assertTrue(self.user.hide_realname)
        self.assertFalse(AccountMinesweeperGames.objects.filter(pk=1234).exists())

    @patch('accountlink.services.fetch_msgames_profile', return_value={'name': 'Linked Name', 'local_name': '关联姓名'})
    def test_retry_does_not_override_admin_revocation(self, sync):
        self.verify()
        UserProfile.objects.filter(pk=self.user.pk).update(can_hide_realname=False)
        self.assertEqual(self.verify().status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.can_hide_realname)
        sync.assert_called_once()

    @patch('accountlink.services.fetch_msgames_profile', side_effect=ExceptionToResponse('import', 'timeout', status_code=503))
    def test_remote_failure_returns_success_and_keeps_binding_and_grant(self, sync):
        with self.assertLogs('accountlink', level='ERROR'):
            response = self.verify()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'')
        self.user.refresh_from_db()
        self.link.refresh_from_db()
        self.assertTrue(self.user.can_hide_realname)
        self.assertTrue(self.link.verified)
        self.assertTrue(AccountMinesweeperGames.objects.filter(parent=self.user).exists())

    @patch('accountlink.services.fetch_msgames_profile')
    def test_other_users_queue_cannot_be_verified_and_legacy_url_removed(self, sync):
        other = UserProfile.objects.create_user(username='binding_other', email='binding_other@test.com')
        self.assertEqual(self.verify(other).status_code, 404)
        self.assertFalse(AccountMinesweeperGames.objects.filter(pk=1234).exists())
        self.assertEqual(self.client.post('/accountlink/verify/').status_code, 404)
        sync.assert_not_called()

    @patch('accountlink.services.fetch_msgames_profile')
    def test_account_names_remain_public_and_existing_binding_does_not_grant(self, sync):
        account = AccountMinesweeperGames.objects.create(pk=1234, parent=self.user, name='Linked Name', local_name='关联姓名')
        self.link.verified = True
        self.link.save(update_fields=['verified'])
        self.assertEqual(self.verify().status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.can_hide_realname)
        self.user.can_hide_realname = True
        self.user.hide_realname = True
        self.user.save(update_fields=['can_hide_realname', 'hide_realname'])
        self.client.logout()
        response = self.client.get(f'/api/accountlink/{self.user.pk}')
        self.assertEqual(response.json()['a']['name'], account.name)
        self.assertEqual(response.json()['a']['local_name'], account.local_name)

    @patch('accountlink.msgames.client.Client')
    def test_empty_remote_name_keeps_successful_binding_available_for_sync_retry(self, factory):
        for name in ('', '   '):
            with self.subTest(name=name):
                factory.return_value.__enter__.return_value.get_profile.return_value = SimpleNamespace(player_id=1234, name=name)
                with self.assertLogs('accountlink', level='ERROR'):
                    self.assertEqual(self.verify().status_code, 200)
                self.user.refresh_from_db()
                self.link.refresh_from_db()
                self.assertTrue(self.link.verified)
                self.assertTrue(self.user.can_hide_realname)
                self.assertEqual(AccountMinesweeperGames.objects.get(parent=self.user).name, '')

    @patch('accountlink.services.fetch_msgames_profile', side_effect=[ExceptionToResponse('import', 'timeout', status_code=503), {'name': 'Recovered Name', 'local_name': '关联姓名'}])
    def test_retry_after_sync_failure_repairs_profile_without_regranting(self, sync):
        with self.assertLogs('accountlink', level='ERROR'):
            self.assertEqual(self.verify().status_code, 200)
        UserProfile.objects.filter(pk=self.user.pk).update(can_hide_realname=False)
        self.assertEqual(self.verify().status_code, 200)
        self.assertEqual(AccountMinesweeperGames.objects.get(parent=self.user).name, 'Recovered Name')
        self.user.refresh_from_db()
        self.assertFalse(self.user.can_hide_realname)
        self.assertEqual(sync.call_count, 2)

    @patch('accountlink.api.update_account', side_effect=RuntimeError('third-party client failed'))
    def test_unexpected_sync_failure_on_another_platform_keeps_successful_binding(self, sync):
        self.link.platform = Platform.BILIBILI
        self.link.save(update_fields=['platform'])
        with self.assertLogs('accountlink', level='ERROR'):
            response = self.client.post('/api/accountlink/verify/', {'id': self.user.pk, 'platform': Platform.BILIBILI, 'identifier': self.link.identifier})
        self.assertEqual(response.status_code, 200)
        self.link.refresh_from_db()
        self.assertTrue(self.link.verified)
        self.assertTrue(AccountBilibili.objects.filter(parent=self.user).exists())

    @patch('accountlink.services.fetch_msgames_profile', return_value={'name': 'Recovered Name', 'local_name': '关联姓名'})
    def test_retry_repairs_legacy_empty_profile_without_regranting(self, sync):
        AccountMinesweeperGames.objects.create(pk=1234, parent=self.user)
        self.link.verified = True
        self.link.save(update_fields=['verified'])
        self.assertEqual(self.verify().status_code, 200)
        self.assertEqual(AccountMinesweeperGames.objects.get(parent=self.user).name, 'Recovered Name')
        self.user.refresh_from_db()
        self.assertFalse(self.user.can_hide_realname)
        sync.assert_called_once_with(1234)

    def unverify(self, identifier='1234'):
        return self.client.post('/api/accountlink/unverify/', {'id': self.user.pk, 'platform': Platform.MSGAMES, 'identifier': identifier})

    @patch('accountlink.services.fetch_msgames_profile', return_value={'name': 'Linked Name', 'local_name': '关联姓名'})
    def test_unverify_removes_queue_and_allows_corrected_id_without_revoking_privacy(self, sync):
        self.assertEqual(self.verify().status_code, 200)
        UserProfile.objects.filter(pk=self.user.pk).update(hide_realname=True)
        self.assertEqual(self.unverify('9999').status_code, 404)
        self.assertTrue(AccountMinesweeperGames.objects.filter(parent=self.user).exists())
        self.assertEqual(self.unverify().status_code, 200)
        self.assertFalse(AccountLinkQueue.objects.filter(pk=self.link.pk).exists())
        self.assertFalse(AccountMinesweeperGames.objects.filter(parent=self.user).exists())
        self.user.refresh_from_db()
        self.assertTrue(self.user.can_hide_realname)
        self.assertTrue(self.user.hide_realname)
        self.client.force_login(self.user)
        response = self.client.post('/api/accountlink/create/', {'platform': Platform.MSGAMES, 'identifier': '5678'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['identifier'], '5678')

    def test_unverify_pending_link_requires_staff_and_removes_application(self):
        self.client.force_login(self.user)
        self.assertEqual(self.unverify().status_code, 403)
        self.client.logout()
        self.assertEqual(self.unverify().status_code, 403)
        self.assertTrue(AccountLinkQueue.objects.filter(pk=self.link.pk).exists())
        self.client.force_login(self.staff)
        self.assertEqual(self.unverify().status_code, 200)
        self.assertFalse(AccountLinkQueue.objects.filter(pk=self.link.pk).exists())
        self.assertEqual(self.client.post('/accountlink/unverify/').status_code, 404)

    @patch('accountlink.models.AccountLinkQueue.delete', side_effect=RuntimeError('queue deletion failed'))
    def test_unverify_rolls_back_account_deletion_when_queue_deletion_fails(self, delete):
        AccountMinesweeperGames.objects.create(pk=1234, parent=self.user, name='Linked Name')
        self.link.verified = True
        self.link.save(update_fields=['verified'])
        with self.assertRaises(RuntimeError):
            self.unverify()
        self.assertTrue(AccountMinesweeperGames.objects.filter(parent=self.user).exists())
        self.link.refresh_from_db()
        self.assertTrue(self.link.verified)


class AccountLinkTestCase(TestCase):
    def setUp(self):
        user = UserProfile.objects.create(
            username='setUp', email='setUp@test.com')
        AccountSaolei.objects.create(id=1, parent=user)
        AccountBilibili.objects.create(id=208259, parent=user)

    def test_update_saolei(self):
        account = AccountSaolei.objects.filter(id=1).first()
        update_saolei_account_info(account, {
            'name': '张砷镓', 'total_views': 100,
            'timems': {'b': 980, 'i': 10310, 'e': 37820, 's': 49110},
            'bvs_cent': {'b': 729, 'i': 530, 'e': 423, 's': 1681},
            'count': {'b': 12, 'i': 33, 'e': 50},
        })
        account = AccountSaolei.objects.filter(id=1).first()
        self.assertEqual(account.id, 1)
        self.assertEqual(account.name, '张砷镓')
        self.assertEqual(account.beg_count, 12)
        self.assertEqual(account.int_count, 33)
        self.assertEqual(account.exp_count, 50)
        self.assertEqual(account.b_t_ms, 980)
        self.assertEqual(account.i_t_ms, 10310)
        self.assertEqual(account.e_t_ms, 37820)
        self.assertEqual(account.s_t_ms, 49110)
        self.assertEqual(account.b_b_cent, 729)
        self.assertEqual(account.i_b_cent, 530)
        self.assertEqual(account.e_b_cent, 423)
        self.assertEqual(account.s_b_cent, 1681)

    def test_update_bilibili(self):
        account = AccountBilibili.objects.filter(id=208259).first()
        update_bilibili_account(account)
        account = AccountBilibili.objects.filter(id=208259).first()

        self.assertEqual(account.id, 208259)
        self.assertEqual(account.name, '陈睿')
        self.assertEqual(account.level, 6)
        self.assertIn('bilibili', account.official_title)
        self.assertTrue(account.face.startswith(('http://', 'https://')))
        self.assertTrue(account.sign)

        self.assertGreater(account.following, 100)
        self.assertLess(account.following, 5000)
        self.assertGreater(account.follower, 1000000)
        self.assertLess(account.follower, 5000000)
        self.assertGreaterEqual(account.video_count, 10)
        self.assertLess(account.video_count, 100)
        self.assertGreaterEqual(account.article_count, 0)
        self.assertLess(account.article_count, 100)
        self.assertGreaterEqual(account.opus_count, 100)
        self.assertLess(account.opus_count, 1000)

    def test_private_platforms(self):
        self.assertIn(Platform.QQ, private_platforms)
        self.assertTrue(isPrivate(Platform.QQ))
        self.assertFalse(isPrivate(Platform.BILIBILI))
        self.assertFalse(isPrivate(Platform.SAOLEI))


class MineracerFakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self.data = data

    def json(self):
        if self.data is None:
            raise ValueError
        return self.data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError()


class MineracerApiResponseTestCase(SimpleTestCase):
    def test_session_schema_serializes_dataclass_fields(self):
        now = timezone.now()
        session = MineracerAccountLinkSession(
            session_id='session-1',
            user_id=1,
            device_code='device-code-1',
            user_code='ABCD-EFGH',
            verification_uri='https://mineracer.example.test/link',
            verification_uri_complete='https://mineracer.example.test/link?code=ABCD-EFGH',
            expires_at=now + datetime.timedelta(minutes=10),
            next_poll_at=now + datetime.timedelta(seconds=2),
            remote_userid='abcDEF123',
            error_category=MINERACER_ERROR_ACCOUNT_NOT_FOUND,
        )

        response = MineracerAccountLinkSessionOut.model_validate(session).model_dump()

        self.assertEqual(response['session_id'], 'session-1')
        self.assertEqual(response['remote_userid'], 'abcDEF123')
        self.assertEqual(response['error_category'], MINERACER_ERROR_ACCOUNT_NOT_FOUND)


class MineracerLegacyViewTestCase(TestCase):
    def setUp(self):
        self.user = UserProfile.objects.create_user(
            username='mineracer_legacy_user',
            email='mineracer_legacy_user@test.com',
            password='password',
            is_staff=True,
        )
        self.client.force_login(self.user)

    def test_delete_link_rejects_mineracer(self):
        AccountLinkQueue.objects.create(platform=Platform.MINERACER, identifier='mineracer-userid', userprofile=self.user, verified=True)

        response = self.client.post('/accountlink/delete/', {'platform': Platform.MINERACER})

        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['category'], 'unlink_not_supported')
        self.assertTrue(AccountLinkQueue.objects.filter(platform=Platform.MINERACER, userprofile=self.user, verified=True).exists())

    def test_verify_link_rejects_manual_mineracer_link(self):
        AccountLinkQueue.objects.create(platform=Platform.MINERACER, identifier='mineracer-userid', userprofile=self.user, verified=False)

        response = self.client.post('/api/accountlink/verify/', {
            'id': self.user.id,
            'platform': Platform.MINERACER,
            'identifier': 'mineracer-userid',
        })

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()['category'], 'manual_link_not_supported')
        self.assertFalse(AccountLinkQueue.objects.get(platform=Platform.MINERACER, userprofile=self.user).verified)

    def test_unverify_link_rejects_mineracer(self):
        AccountLinkQueue.objects.create(platform=Platform.MINERACER, identifier='mineracer-userid', userprofile=self.user, verified=True)

        response = self.client.post('/api/accountlink/unverify/', {
            'id': self.user.id,
            'platform': Platform.MINERACER,
            'identifier': 'mineracer-userid',
        })

        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['category'], 'unlink_not_supported')
        self.assertTrue(AccountLinkQueue.objects.get(platform=Platform.MINERACER, userprofile=self.user).verified)

    def test_update_link_rejects_mineracer(self):
        response = self.client.post('/accountlink/update/', {'platform': Platform.MINERACER})

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()['category'], 'update_not_supported')


MINERACER_TEST_CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'mineracer-default-cache',
    },
    'saolei_website': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'mineracer-session-cache',
    },
}

MINERACER_TEST_SETTINGS = {
    'MINERACER_START_URL': 'https://mineracer.example.test/api/partner/link/start',
    'MINERACER_POLL_URL': 'https://mineracer.example.test/api/partner/link/poll',
    'MINERACER_TIMEOUT': 5,
    'MINERACER_POLL_INTERVAL_MS': 2500,
    'MINERACER_SESSION_GRACE_SECONDS': 60,
    'CACHES': MINERACER_TEST_CACHES,
}


@override_settings(**MINERACER_TEST_SETTINGS)
class MineracerHttpClientTestCase(SimpleTestCase):
    def setUp(self):
        self.read_secret = self.enterContext(patch('accountlink.mineracer.client.read_secret', return_value='test-partner-key'))

    @patch('accountlink.mineracer.client.requests.post')
    def test_requests_read_current_partner_key(self, requests_post):
        requests_post.return_value = MineracerFakeResponse(data={
            'deviceCode': 'device-code-1',
            'userCode': 'ABCD-EFGH',
            'verificationUri': 'https://mineracer.example.test/link',
            'verificationUriComplete': 'https://mineracer.example.test/link?code=ABCD-EFGH',
            'intervalMs': 2500,
            'expiresAt': 1780000000000,
        })
        request_mineracer_account_link()
        self.read_secret.assert_called_once_with('mineracer_account_link_partner_key')
        self.assertEqual(requests_post.call_args.kwargs['headers']['Authorization'], 'Bearer test-partner-key')

        self.read_secret.return_value = 'rotated-partner-key'
        requests_post.return_value = MineracerFakeResponse(status_code=202, data={'status': 'pending', 'intervalMs': 2500})
        poll_mineracer_account_link('device-code-1')
        self.assertEqual(self.read_secret.call_count, 2)
        self.assertEqual(requests_post.call_args.kwargs['headers']['Authorization'], 'Bearer rotated-partner-key')

    @patch('accountlink.mineracer.client.requests.post')
    def test_missing_partner_key_raises_before_http_request(self, requests_post):
        for error in (FileNotFoundError('secrets.json'), KeyError('mineracer_account_link_partner_key')):
            for request, args in ((request_mineracer_account_link, ()), (poll_mineracer_account_link, ('device-code-1',))):
                with self.subTest(error=type(error).__name__, request=request.__name__):
                    self.read_secret.side_effect = error
                    with self.assertRaises(type(error)):
                        request(*args)
        requests_post.assert_not_called()

    @patch('accountlink.mineracer.client.requests.post')
    def test_empty_partner_key_raises_before_http_request(self, requests_post):
        self.read_secret.return_value = '   '
        for request, args in ((request_mineracer_account_link, ()), (poll_mineracer_account_link, ('device-code-1',))):
            with self.subTest(request=request.__name__):
                with self.assertRaises(ExceptionToResponse) as context:
                    request(*args)
                self.assertEqual(context.exception.category, 'not_configured')
                self.assertEqual(context.exception.status_code, 503)
        requests_post.assert_not_called()

    @patch('accountlink.mineracer.client.requests.post')
    def test_request_mineracer_account_link_uses_bearer_and_no_body(self, requests_post):
        requests_post.return_value = MineracerFakeResponse(data={
            'deviceCode': 'device-code-1',
            'userCode': 'ABCD-EFGH',
            'verificationUri': 'https://mineracer.example.test/link',
            'verificationUriComplete': 'https://mineracer.example.test/link?code=ABCD-EFGH',
            'intervalMs': 2500,
            'expiresAt': 1780000000000,
        })

        response = request_mineracer_account_link()

        requests_post.assert_called_once()
        _, kwargs = requests_post.call_args
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer test-partner-key')
        self.assertNotIn('json', kwargs)
        self.assertEqual(response.device_code, 'device-code-1')
        self.assertEqual(response.user_code, 'ABCD-EFGH')
        self.assertEqual(response.verification_uri_complete, 'https://mineracer.example.test/link?code=ABCD-EFGH')
        self.assertEqual(response.poll_interval_ms, 2500)

    @patch('accountlink.mineracer.client.requests.post')
    def test_poll_mineracer_account_link_returns_pending_on_202(self, requests_post):
        requests_post.return_value = MineracerFakeResponse(status_code=202, data={'status': 'pending', 'intervalMs': 3000})

        response = poll_mineracer_account_link('device-code-1')

        _, kwargs = requests_post.call_args
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer test-partner-key')
        self.assertEqual(kwargs['json'], {'deviceCode': 'device-code-1'})
        self.assertEqual(response.status, MINERACER_STATUS_PENDING)
        self.assertEqual(response.retry_after_ms, 3000)

    @patch('accountlink.mineracer.client.requests.post')
    def test_poll_mineracer_rejects_nonpositive_or_noninteger_interval(self, requests_post):
        for interval in (0, -1, '3000', 3000.0, True):
            with self.subTest(interval=interval):
                requests_post.return_value = MineracerFakeResponse(status_code=202, data={'status': 'pending', 'intervalMs': interval})
                with self.assertRaises(ExceptionToResponse) as context:
                    poll_mineracer_account_link('device-code-1')
                self.assertEqual(context.exception.category, 'response')

    @patch('accountlink.mineracer.client.requests.post')
    def test_poll_mineracer_account_link_returns_linked_userid_on_200(self, requests_post):
        requests_post.return_value = MineracerFakeResponse(data={
            'status': 'linked',
            'userId': '12345678901234567',
        })

        response = poll_mineracer_account_link('device-code-1')

        self.assertEqual(response.status, MINERACER_STATUS_CONFIRMED)
        self.assertEqual(response.userid, '12345678901234567')

    @patch('accountlink.mineracer.client.requests.post')
    def test_poll_mineracer_account_link_maps_remote_errors(self, requests_post):
        cases = [
            (400, {'error': 'invalid-device-code'}, MINERACER_STATUS_FAILED, MINERACER_ERROR_INVALID_DEVICE_CODE),
            (404, {'error': 'invalid-device-code'}, MINERACER_STATUS_FAILED, MINERACER_ERROR_INVALID_DEVICE_CODE),
            (404, {'error': 'account-not-found'}, MINERACER_STATUS_FAILED, MINERACER_ERROR_ACCOUNT_NOT_FOUND),
            (409, {'error': 'link-superseded'}, MINERACER_STATUS_FAILED, MINERACER_ERROR_LINK_SUPERSEDED),
            (410, {'error': 'code-expired'}, MINERACER_STATUS_EXPIRED, ''),
        ]

        for status_code, data, expected_status, expected_category in cases:
            with self.subTest(status_code=status_code, data=data):
                requests_post.return_value = MineracerFakeResponse(status_code=status_code, data=data)

                response = poll_mineracer_account_link('device-code-1')

                self.assertEqual(response.status, expected_status)
                self.assertEqual(response.error_category, expected_category)


@override_settings(**MINERACER_TEST_SETTINGS)
class MineracerAccountLinkTestCase(TestCase):
    def setUp(self):
        if AccountMineracer._meta.db_table not in connection.introspection.table_names():
            raise SkipTest('AccountMineracer migration has not been generated yet.')
        caches['default'].clear()
        self.user = UserProfile.objects.create_user(
            username='mineracer_user',
            email='mineracer_user@test.com',
            password='password',
        )
        self.client.force_login(self.user)

    @patch('accountlink.mineracer.sessions.request_mineracer_account_link')
    def test_start_mineracer_session_creates_pending_session(self, request_mineracer_account_link):
        expires_at = timezone.now() + datetime.timedelta(minutes=10)
        request_mineracer_account_link.return_value = MineracerAccountLinkStartResponse(
            device_code='device-code-1',
            user_code='ABCD-EFGH',
            verification_uri='https://mineracer.example.test/link',
            verification_uri_complete='https://mineracer.example.test/link?code=ABCD-EFGH',
            expires_at=expires_at,
            poll_interval_ms=2500,
        )

        response = self.client.post('/api/accountlink/mineracer/start/')

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        session = _get_mineracer_session(data['session_id'])
        self.assertIsNotNone(session)
        self.assertEqual(data['status'], MINERACER_STATUS_PENDING)
        self.assertEqual(data['verification_uri_complete'], 'https://mineracer.example.test/link?code=ABCD-EFGH')
        self.assertEqual(session.device_code, 'device-code-1')
        self.assertEqual(session.user_code, 'ABCD-EFGH')
        self.assertEqual(session.user_id, self.user.id)

    @patch('accountlink.mineracer.sessions.poll_mineracer_account_link')
    def test_status_uses_local_pending_state_before_next_poll_time(self, poll_mineracer_account_link):
        session = self.create_session(next_poll_at=timezone.now() + datetime.timedelta(seconds=30))

        response = self.client.get(f'/api/accountlink/mineracer/status/{session.session_id}')

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['status'], MINERACER_STATUS_PENDING)
        self.assertIsNotNone(response.json()['next_poll_at'])
        poll_mineracer_account_link.assert_not_called()

    @patch('accountlink.mineracer.sessions.poll_mineracer_account_link')
    def test_status_confirms_session_and_links_string_userid(self, poll_mineracer_account_link):
        session = self.create_session(next_poll_at=timezone.now() - datetime.timedelta(seconds=1))
        poll_mineracer_account_link.return_value = MineracerAccountLinkPollResponse(
            status=MINERACER_STATUS_CONFIRMED,
            userid='abcDEF123',
        )

        response = self.client.get(f'/api/accountlink/mineracer/status/{session.session_id}')

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['status'], MINERACER_STATUS_CONFIRMED)
        self.assertEqual(response.json()['remote_userid'], 'abcDEF123')
        self.assertTrue(AccountMineracer.objects.filter(id='abcDEF123', parent=self.user).exists())
        self.assertTrue(AccountLinkQueue.objects.filter(
            platform=Platform.MINERACER,
            identifier='abcDEF123',
            userprofile=self.user,
            verified=True,
        ).exists())

    @patch('accountlink.mineracer.sessions.poll_mineracer_account_link')
    def test_status_conflict_does_not_reassign_existing_mineracer_userid(self, poll_mineracer_account_link):
        other_user = UserProfile.objects.create_user(
            username='other_mineracer_user',
            email='other_mineracer_user@test.com',
            password='password',
        )
        AccountMineracer.objects.create(id='12345678901234567', parent=other_user)
        AccountLinkQueue.objects.create(
            platform=Platform.MINERACER,
            identifier='12345678901234567',
            userprofile=other_user,
            verified=True,
        )
        session = self.create_session(next_poll_at=timezone.now() - datetime.timedelta(seconds=1))
        poll_mineracer_account_link.return_value = MineracerAccountLinkPollResponse(
            status=MINERACER_STATUS_CONFIRMED,
            userid='12345678901234567',
        )

        response = self.client.get(f'/api/accountlink/mineracer/status/{session.session_id}')

        self.assertEqual(response.status_code, 409, response.content)
        session = _get_mineracer_session(session.session_id)
        self.assertEqual(session.status, MINERACER_STATUS_FAILED)
        self.assertEqual(session.error_category, 'identifier_conflict')
        self.assertEqual(AccountMineracer.objects.get(id='12345678901234567').parent, other_user)
        self.assertFalse(AccountLinkQueue.objects.filter(platform=Platform.MINERACER, userprofile=self.user).exists())

    def test_generic_create_rejects_mineracer(self):
        response = self.client.post('/api/accountlink/create/', {
            'platform': Platform.MINERACER,
            'identifier': '123456789',
        })

        self.assertEqual(response.status_code, 400)
        self.assertFalse(AccountLinkQueue.objects.filter(platform=Platform.MINERACER, userprofile=self.user).exists())

    def create_session(self, next_poll_at):
        session = MineracerAccountLinkSession(
            session_id='session-1',
            user_id=self.user.id,
            device_code='device-code-1',
            user_code='ABCD-EFGH',
            verification_uri='https://mineracer.example.test/link',
            verification_uri_complete='https://mineracer.example.test/link?code=ABCD-EFGH',
            expires_at=timezone.now() + datetime.timedelta(minutes=10),
            next_poll_at=next_poll_at,
        )
        _save_mineracer_session(session)
        _save_user_pending_mineracer_session(session)
        return session
