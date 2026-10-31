import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import SESSION_KEY
from django.core.cache import caches
from django.db import connections
from django.test import Client, override_settings, SimpleTestCase, skipUnlessDBFeature, TestCase, TransactionTestCase
import requests

from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from .cache import BROWSER_SESSION_KEY, consume_discord_flow, save_discord_flow
from .client import discord_authorization_url, DiscordProfile, fetch_discord_profile, get_discord_config, TOKEN_URL, USER_URL
from ..models import AccountDiscord, AccountLinkQueue, AccountQQ, Platform
from ..services import save_verified_account_link

CONFIG = {
    'discord_oauth_client_secret': 'offline-test-secret',
}
CLIENT_ID = '123456789012345678'
REDIRECT_URI = 'https://site.example.test/api/accountlink/discord/callback'
PROFILE = {
    'id': '803511102246789123', 'username': 'discord_user', 'global_name': 'Discord Player',
    'avatar': 'a_' + 'a' * 32, 'banner': 'b' * 32, 'accent_color': 0x5865F2, 'public_flags': 64,
}
TOKEN = {'access_token': 'offline-access-token', 'token_type': 'Bearer', 'scope': 'identify', 'expires_in': 3600}
TEST_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'discord-oauth-tests'},
    'saolei_website': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'discord-session-tests'},
}


def http_response(payload, status=200):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(payload).encode()
    response.headers['Content-Type'] = 'application/json'
    return response


@override_settings(CACHES=TEST_CACHES, DISCORD_OAUTH_CLIENT_ID=CLIENT_ID, DISCORD_OAUTH_REDIRECT_URI=REDIRECT_URI)
class DiscordTransportTests(SimpleTestCase):
    def setUp(self):
        self.config_patch = patch('accountlink.discord.client.read_secrets', return_value=CONFIG.copy())
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        caches['default'].clear()

    def test_authorization_uses_identify_and_pkce_without_exposing_secret(self):
        url, state = discord_authorization_url(get_discord_config(), 'v' * 64)
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query['scope'], ['identify'])
        self.assertEqual(query['state'], [state])
        self.assertEqual(query['response_type'], ['code'])
        self.assertEqual(query['client_id'], [CLIENT_ID])
        self.assertEqual(query['redirect_uri'], [REDIRECT_URI])
        self.assertEqual(query['code_challenge_method'], ['S256'])
        expected = base64.urlsafe_b64encode(hashlib.sha256(('v' * 64).encode()).digest()).rstrip(b'=').decode()
        self.assertEqual(query['code_challenge'], [expected])
        self.assertNotIn(CONFIG['discord_oauth_client_secret'], url)

    @patch('requests.sessions.Session.send')
    def test_real_authlib_transport_exchanges_form_code_and_fetches_identity(self, send):
        send.side_effect = [http_response(TOKEN), http_response(PROFILE)]
        profile = fetch_discord_profile(get_discord_config(), 'offline-code', 'v' * 64)
        self.assertEqual(profile.id, PROFILE['id'])
        token_request = send.call_args_list[0].args[0]
        self.assertEqual(token_request.url, TOKEN_URL)
        self.assertEqual(token_request.method, 'POST')
        body = parse_qs(token_request.body)
        self.assertEqual(body['code'], ['offline-code'])
        self.assertEqual(body['code_verifier'], ['v' * 64])
        self.assertEqual(body['redirect_uri'], [REDIRECT_URI])
        self.assertEqual(body['grant_type'], ['authorization_code'])
        self.assertEqual(token_request.headers['Content-Type'], 'application/x-www-form-urlencoded;charset=UTF-8')
        self.assertTrue(token_request.headers['Authorization'].startswith('Basic '))
        user_request = send.call_args_list[1].args[0]
        self.assertEqual(user_request.url, USER_URL)
        self.assertEqual(user_request.headers['Authorization'], 'Bearer offline-access-token')
        for call in send.call_args_list:
            self.assertEqual(call.kwargs['timeout'], 5)
            self.assertFalse(call.kwargs['allow_redirects'])

    @patch('requests.sessions.Session.send')
    def test_upstream_failures_are_sanitized(self, send):
        cases = [
            ([requests.Timeout('private detail')], 'timeout'),
            ([http_response(TOKEN), requests.ConnectionError('private detail')], 'upstream_error'),
            ([http_response({'error': 'invalid_grant', 'error_description': 'private detail'}, 400)], 'authorization_failed'),
            ([http_response(TOKEN), http_response({'message': 'private detail'}, 403)], 'upstream_error'),
            ([http_response(TOKEN), http_response({**PROFILE, 'id': 123})], 'upstream_error'),
        ]
        for responses, category in cases:
            with self.subTest(category=category):
                send.side_effect = responses
                with self.assertRaises(ExceptionToResponse) as raised:
                    fetch_discord_profile(get_discord_config(), 'code', 'v' * 64)
                self.assertEqual(raised.exception.category, category)
                self.assertNotIn('private detail', str(raised.exception))

    @patch('requests.sessions.Session.send')
    def test_invalid_tokens_never_trigger_profile_requests(self, send):
        for payload in ([], {}, {**TOKEN, 'token_type': None}, {**TOKEN, 'scope': 'email'}, {**TOKEN, 'access_token': 123}):
            with self.subTest(payload=payload):
                send.reset_mock()
                send.side_effect = [http_response(payload)]
                with self.assertRaises(ExceptionToResponse):
                    fetch_discord_profile(get_discord_config(), 'code', 'v' * 64)
                self.assertEqual(send.call_count, 1)

    @patch('requests.sessions.Session.send')
    def test_optional_profile_fields_validate_without_expanding_scope(self, send):
        for fields in ({}, {'avatar': None, 'banner': None, 'accent_color': None, 'public_flags': None}):
            with self.subTest(fields=fields):
                send.side_effect = [http_response(TOKEN), http_response({'id': PROFILE['id'], 'username': 'player', **fields})]
                profile = fetch_discord_profile(get_discord_config(), 'code', 'v' * 64)
                self.assertEqual(profile.account_fields(), {
                    'username': 'player', 'global_name': '', 'avatar': '', 'banner': '', 'accent_color': None, 'public_flags': None,
                })
        for fields in ({'avatar': '../image'}, {'banner': 'https://evil.example/image'}, {'accent_color': -1}, {'accent_color': 0x1000000}, {'public_flags': -1}):
            with self.subTest(fields=fields):
                send.side_effect = [http_response(TOKEN), http_response({**PROFILE, **fields})]
                with self.assertRaises(ExceptionToResponse):
                    fetch_discord_profile(get_discord_config(), 'code', 'v' * 64)

    def test_configuration_requires_trusted_absolute_urls(self):
        for value in ('', '//evil.example/callback', 'http://site.example/callback', 'https://site.example/#/callback', None):
            with self.subTest(value=value), override_settings(DISCORD_OAUTH_REDIRECT_URI=value):
                with self.assertRaises(ExceptionToResponse):
                    get_discord_config()
        with patch('accountlink.discord.client.read_secrets', return_value={**CONFIG, 'discord_oauth_frontend_url': 'http://127.0.0.1:8080'}):
            self.assertEqual(get_discord_config().frontend_url, 'http://127.0.0.1:8080')

    def test_redirect_setting_is_used_even_if_secrets_contains_an_old_uri(self):
        with patch('accountlink.discord.client.read_secrets', return_value={**CONFIG, 'discord_oauth_redirect_uri': 'https://ignored.example/callback'}):
            self.assertEqual(get_discord_config().redirect_uri, REDIRECT_URI)

    def test_client_id_setting_is_used_and_missing_id_does_not_fall_back_to_secrets(self):
        with patch('accountlink.discord.client.read_secrets', return_value={**CONFIG, 'discord_oauth_client_id': '999'}):
            self.assertEqual(get_discord_config().client_id, CLIENT_ID)
            with override_settings(DISCORD_OAUTH_CLIENT_ID=''):
                with self.assertRaises(ExceptionToResponse):
                    get_discord_config()

    def test_wrong_browser_does_not_consume_state_and_replay_is_rejected(self):
        save_discord_flow('state', {'browser_nonce': 'correct-browser'})
        with self.assertRaises(ExceptionToResponse):
            consume_discord_flow('state', 'wrong-browser')
        self.assertEqual(consume_discord_flow('state', 'correct-browser')['browser_nonce'], 'correct-browser')
        with self.assertRaises(ExceptionToResponse):
            consume_discord_flow('state', 'correct-browser')

    def test_simultaneous_callbacks_consume_state_once(self):
        save_discord_flow('state', {'browser_nonce': 'browser'})

        def consume(_):
            try:
                consume_discord_flow('state', 'browser')
                return True
            except ExceptionToResponse:
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(consume, range(2))), 1)


@override_settings(CACHES=TEST_CACHES, DISCORD_OAUTH_CLIENT_ID=CLIENT_ID, DISCORD_OAUTH_REDIRECT_URI=REDIRECT_URI, RATELIMIT_ENABLE=False, SESSION_COOKIE_SECURE=False, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DiscordApiTests(TestCase):
    def setUp(self):
        for cache in caches.all():
            cache.clear()
        self.user = UserProfile.objects.create_user(username='discord_site_user', email='discord_site@test.com', password='password')
        self.other = UserProfile.objects.create_user(username='discord_other', email='discord_other@test.com', password='password')
        self.config_patch = patch('accountlink.discord.client.read_secrets', return_value=CONFIG.copy())
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        self.send_patch = patch('requests.sessions.Session.send', side_effect=AssertionError('Unexpected live HTTP request'))
        self.send_patch.start()
        self.addCleanup(self.send_patch.stop)
        self.profile_patch = patch('accountlink.discord.api.fetch_discord_profile', return_value=DiscordProfile.model_validate(PROFILE))
        self.profile = self.profile_patch.start()
        self.addCleanup(self.profile_patch.stop)

    def start(self, mode='link', expiry=0):
        response = self.client.post('/api/accountlink/discord/start', {'mode': mode, 'set_expiry': expiry})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertNotIn(CONFIG['discord_oauth_client_secret'], response.content.decode())
        return parse_qs(urlsplit(response.json()['authorization_url']).query)['state'][0]

    def callback(self, state, **kwargs):
        return self.client.get('/api/accountlink/discord/callback', {'state': state, 'code': 'offline-code', **kwargs})

    def assert_result(self, response, **expected):
        self.assertEqual(response.status_code, 302, response.content)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')
        self.assertTrue(response['Location'].startswith('https://site.example.test/#/discord?'))
        self.assertNotIn('offline-code', response['Location'])
        self.assertEqual(parse_qs(response['Location'].split('?', 1)[1]), {key: [str(value)] for key, value in expected.items()})

    def test_availability_does_not_expose_credentials_and_missing_config_disables_feature(self):
        response = self.client.get('/api/accountlink/discord/config')
        self.assertEqual(response.json(), {'enabled': True})
        with patch('accountlink.discord.client.read_secrets', side_effect=FileNotFoundError):
            self.assertEqual(self.client.get('/api/accountlink/discord/config').json(), {'enabled': False})
            self.assertEqual(self.client.post('/api/accountlink/discord/start', {'mode': 'login'}).status_code, 503)

    def test_successful_binding_is_private_verified_and_repeat_authorization_updates_profile(self):
        self.client.force_login(self.user)
        self.assert_result(self.callback(self.start()), status='linked', user_id=self.user.pk)
        account = AccountDiscord.objects.get(pk=PROFILE['id'])
        self.assertEqual(account.parent_id, self.user.pk)
        self.assertEqual(account.username, PROFILE['username'])
        details = self.client.get(f'/api/accountlink/{self.user.pk}').json()['d']
        self.assertEqual(details['id'], PROFILE['id'])
        for field in ('avatar', 'banner', 'accent_color', 'public_flags'):
            self.assertEqual(getattr(account, field), PROFILE[field])
            self.assertEqual(details[field], PROFILE[field])
        self.profile.return_value = DiscordProfile(id=PROFILE['id'], username='renamed', global_name=None)
        self.assert_result(self.callback(self.start()), status='linked', user_id=self.user.pk)
        account.refresh_from_db()
        self.assertEqual((account.username, account.global_name), ('renamed', ''))
        self.assertEqual((account.avatar, account.banner, account.accent_color, account.public_flags), ('', '', None, None))
        self.assertEqual(AccountLinkQueue.objects.filter(platform='d', userprofile=self.user, verified=True).count(), 1)
        public = Client().get(f'/api/accountlink/{self.user.pk}').json()
        self.assertIsNone(public['d'])
        self.assertEqual(public['summary'], [])

    def test_discord_and_qq_details_are_visible_only_to_owner_and_staff(self):
        save_verified_account_link(self.user, Platform.DISCORD, PROFILE['id'], DiscordProfile.model_validate(PROFILE).account_fields())
        AccountQQ.objects.create(id=12345, parent=self.user)
        AccountLinkQueue.objects.create(platform=Platform.QQ, userprofile=self.user, identifier='12345', verified=True)

        self.client.force_login(self.user)
        response = self.client.get(f'/api/accountlink/{self.user.pk}')
        self.assertIn('no-store', response['Cache-Control'])
        own = response.json()
        self.assertEqual({link['platform'] for link in own['summary']}, {'d', 'q'})
        self.assertEqual(own['d']['avatar'], PROFILE['avatar'])
        self.assertEqual(own['q']['id'], 12345)

        for client in (Client(), self.client):
            if client is self.client:
                client.force_login(self.other)
            public = client.get(f'/api/accountlink/{self.user.pk}').json()
            self.assertIsNone(public['d'])
            self.assertIsNone(public['q'])
            self.assertEqual(public['summary'], [])

        self.other.is_staff = True
        self.other.save(update_fields=['is_staff'])
        self.client.force_login(self.other)
        staff = self.client.get(f'/api/accountlink/{self.user.pk}').json()
        self.assertEqual(staff['d']['id'], PROFILE['id'])
        self.assertEqual(staff['q']['id'], 12345)
        self.assertEqual({link['platform'] for link in staff['summary']}, {'d', 'q'})

    def test_private_ids_are_not_searchable_in_the_public_user_directory(self):
        for platform in ('d', 'q'):
            with self.subTest(platform=platform):
                response = self.client.get('/api/userprofile/query', {'platform': platform, 'id': PROFILE['id']})
                self.assertEqual(response.status_code, 422)

    def test_binding_requires_login_and_manual_paths_reject_discord(self):
        self.assertEqual(self.client.post('/api/accountlink/discord/start', {'mode': 'link'}).status_code, 403)
        self.assertEqual(self.client.post('/api/accountlink/discord/unlink').status_code, 403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post('/api/accountlink/create/', {'platform': 'd', 'identifier': PROFILE['id']}).status_code, 400)
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.assertEqual(self.client.post('/api/accountlink/verify/', {'id': self.other.pk, 'platform': 'd', 'identifier': PROFILE['id']}).status_code, 400)

    def test_cross_browser_and_expired_states_never_contact_discord(self):
        self.client.force_login(self.user)
        state = self.start()
        other = Client()
        other.force_login(self.user)
        self.assert_result(other.get('/api/accountlink/discord/callback', {'state': state, 'code': 'code'}), error='invalid_state')
        caches['default'].clear()
        self.assert_result(self.callback(state), error='invalid_state')
        self.profile.assert_not_called()

    def test_replayed_and_duplicate_callbacks_are_rejected(self):
        self.client.force_login(self.user)
        state = self.start()
        duplicate = self.client.get(f'/api/accountlink/discord/callback?state={state}&state=another&code=code')
        self.assert_result(duplicate, error='invalid_state')
        self.assert_result(self.callback(state), status='linked', user_id=self.user.pk)
        self.assert_result(self.callback(state), error='invalid_state')
        self.profile.assert_called_once()

    def test_session_user_change_cannot_bind_another_user(self):
        self.client.force_login(self.user)
        state = self.start()
        nonce = self.client.session[BROWSER_SESSION_KEY]
        self.client.force_login(self.other)
        self.assert_result(self.callback(state), error='invalid_state')
        # User ownership is checked even if a session backend preserves the nonce.
        session = self.client.session
        session[BROWSER_SESSION_KEY] = nonce
        session.save()  # noqa: DJM100 - This is a SessionStore, not a model.
        self.assert_result(self.callback(state), error='session_changed')
        self.profile.assert_not_called()
        self.assertFalse(AccountDiscord.objects.exists())

    def test_denied_authorization_and_wrong_issuer_do_not_fetch_identity(self):
        self.client.force_login(self.user)
        self.assert_result(self.callback(self.start(), error='access_denied', error_description='private detail'), error='access_denied')
        self.assert_result(self.callback(self.start(), iss='https://evil.example'), error='invalid_state')
        self.profile.assert_not_called()

    def test_conflicts_never_reassign_accounts(self):
        save_verified_account_link(self.other, Platform.DISCORD, PROFILE['id'])
        self.client.force_login(self.user)
        self.assert_result(self.callback(self.start()), error='identifier_conflict')
        self.assertEqual(AccountDiscord.objects.get(pk=PROFILE['id']).parent_id, self.other.pk)
        self.assertFalse(AccountLinkQueue.objects.filter(platform='d', userprofile=self.user).exists())
        save_verified_account_link(self.user, Platform.DISCORD, '999999999999999999')
        self.assert_result(self.callback(self.start()), error='identifier_conflict')
        self.assertEqual(AccountDiscord.objects.get(parent=self.user).pk, '999999999999999999')

    def test_login_requires_preexisting_verified_link_and_never_registers(self):
        self.assert_result(self.callback(self.start('login')), error='not_linked')
        self.assertNotIn(SESSION_KEY, self.client.session)
        AccountDiscord.objects.create(id=PROFILE['id'], parent=self.user, username='old')
        self.assert_result(self.callback(self.start('login')), error='not_linked')
        self.assertEqual(UserProfile.objects.count(), 2)

    def test_linked_user_can_login_with_selected_expiry(self):
        save_verified_account_link(self.user, Platform.DISCORD, PROFILE['id'])
        for days in (0, 1, 7, 30, 90):
            with self.subTest(days=days):
                self.client.logout()
                state = self.start('login', days)
                self.assert_result(self.callback(state), status='logged_in', user_id=self.user.pk)
                self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))
                self.assertEqual(self.client.session.get_expire_at_browser_close(), days == 0)
                if days:
                    self.assertAlmostEqual(self.client.session.get_expiry_age(), days * 86400, delta=2)
        self.assertEqual(AccountDiscord.objects.get(parent=self.user).username, PROFILE['username'])
        account = AccountDiscord.objects.get(parent=self.user)
        for field in ('avatar', 'banner', 'accent_color', 'public_flags'):
            self.assertEqual(getattr(account, field), PROFILE[field])

    def test_inactive_and_memorial_accounts_cannot_login(self):
        save_verified_account_link(self.user, Platform.DISCORD, PROFILE['id'])
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assert_result(self.callback(self.start('login')), error='account_disabled')
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.user.is_memorial = True
        self.user.email = 'discord@accounts.invalid'
        self.user.set_unusable_password()
        self.user.save(update_fields=['is_memorial', 'email', 'password'])
        self.assert_result(self.callback(self.start('login')), error='account_disabled')

    def test_logged_in_browser_cannot_start_discord_login(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post('/api/accountlink/discord/start', {'mode': 'login'}).status_code, 409)

    def test_unlink_removes_login_identity_but_preserves_site_password(self):
        save_verified_account_link(self.user, Platform.DISCORD, PROFILE['id'])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post('/api/accountlink/discord/unlink').status_code, 404)
        self.assertTrue(AccountDiscord.objects.exists())
        self.client.force_login(self.user)
        self.assertEqual(self.client.post('/api/accountlink/discord/unlink').status_code, 200)
        self.assertFalse(AccountDiscord.objects.exists())
        self.assertFalse(AccountLinkQueue.objects.filter(platform='d').exists())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('password'))
        self.client.logout()
        self.assert_result(self.callback(self.start('login')), error='not_linked')

    def test_upstream_failure_preserves_existing_binding(self):
        save_verified_account_link(self.user, Platform.DISCORD, PROFILE['id'])
        self.client.force_login(self.user)
        self.profile.side_effect = ExceptionToResponse('discord', 'timeout', status_code=504)
        self.assert_result(self.callback(self.start()), error='timeout')
        self.assertEqual(AccountDiscord.objects.get(pk=PROFILE['id']).parent_id, self.user.pk)

    def test_configuration_change_and_invalid_expiry_are_rejected(self):
        self.assertEqual(self.client.post('/api/accountlink/discord/start', {'mode': 'login', 'set_expiry': 365}).status_code, 422)
        self.client.force_login(self.user)
        state = self.start()
        with override_settings(DISCORD_OAUTH_CLIENT_ID='999'):
            self.assert_result(self.callback(state), error='not_configured')
        self.profile.assert_not_called()

    def test_callback_through_real_authlib_transport(self):
        self.profile_patch.stop()
        self.client.force_login(self.user)
        with patch('requests.sessions.Session.send', side_effect=[http_response(TOKEN), http_response(PROFILE)]) as send:
            self.assert_result(self.callback(self.start()), status='linked', user_id=self.user.pk)
        self.assertEqual(send.call_count, 2)
        self.assertTrue(AccountDiscord.objects.filter(id=PROFILE['id'], parent=self.user).exists())


@override_settings(CACHES=TEST_CACHES, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class VerifiedBindingConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.users = [UserProfile.objects.create_user(username=f'discord_race_{i}', email=f'race_{i}@example.test') for i in range(2)]

    @staticmethod
    def bind(item):
        user, identifier = item
        try:
            save_verified_account_link(user, Platform.DISCORD, identifier)
            return True
        except ExceptionToResponse as exc:
            if exc.category != 'collision':
                raise
            return False
        finally:
            connections.close_all()

    @skipUnlessDBFeature('has_select_for_update')
    def test_two_users_cannot_claim_same_discord_identity(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(self.bind, [(user, PROFILE['id']) for user in self.users]))
        self.assertEqual(sum(result), 1)
        self.assertEqual(AccountDiscord.objects.count(), 1)
        self.assertEqual(AccountLinkQueue.objects.filter(platform='d', verified=True).count(), 1)

    @skipUnlessDBFeature('has_select_for_update')
    def test_same_user_cannot_bind_two_discord_identities(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(self.bind, [(self.users[0], identifier) for identifier in (PROFILE['id'], '999999999999999999')]))
        self.assertEqual(sum(result), 1)
        self.assertEqual(AccountDiscord.objects.count(), 1)
        self.assertEqual(AccountLinkQueue.objects.filter(platform='d', verified=True).count(), 1)
