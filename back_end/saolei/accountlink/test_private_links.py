from unittest.mock import patch

from django.test import Client, override_settings, TestCase

from userprofile.models import UserProfile
from .models import AccountDiscord, AccountLinkQueue, AccountQQ, Platform

TEST_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'private-links'},
    'saolei_website': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'private-links-sessions'},
}


@override_settings(CACHES=TEST_CACHES, RATELIMIT_ENABLE=False, SESSION_COOKIE_SECURE=False, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PrivateAccountLinkTests(TestCase):
    discord_id = '18446744073709551615'
    platforms = [(Platform.DISCORD, discord_id, AccountDiscord), (Platform.QQ, '12345678', AccountQQ)]

    def setUp(self):
        self.user = UserProfile.objects.create_user(username='private-owner', email='owner@example.test')
        self.other = UserProfile.objects.create_user(username='private-other', email='other@example.test')
        self.staff = UserProfile.objects.create_user(username='private-staff', email='staff@example.test', is_staff=True)
        self.client = Client(enforce_csrf_checks=True)
        network = patch('requests.sessions.Session.send', side_effect=AssertionError('Unexpected external HTTP request'))
        network.start()
        self.addCleanup(network.stop)

    def create(self, platform, identifier):
        return self.client.post('/api/accountlink/create/', {'platform': platform, 'identifier': identifier})

    def moderate(self, platform, identifier, action='verify', user=None):
        self.client.force_login(self.staff)
        token = self.client.get('/api/userprofile/admin/csrf').json()['csrf_token']
        return self.client.post(
            f'/api/accountlink/{action}/', {'id': (user or self.user).pk, 'platform': platform, 'identifier': identifier},
            HTTP_X_CSRFTOKEN=token,
        )

    def test_qq_and_discord_share_manual_request_and_staff_verification(self):
        for platform, identifier, model in self.platforms:
            with self.subTest(platform=platform):
                self.client.force_login(self.user)
                response = self.create(platform, identifier)
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()['identifier'], identifier)
                self.assertFalse(response.json()['verified'])
                self.assertFalse(model.objects.exists())
                pending = self.client.get(f'/api/accountlink/{self.user.pk}').json()
                self.assertIsNone(pending[platform])
                self.assertIn(identifier, [link['identifier'] for link in pending['summary']])
                self.assertEqual(self.create(platform, identifier).status_code, 409)
                self.assertEqual(self.moderate(platform, identifier).status_code, 200)
                self.assertEqual(model.objects.get(pk=identifier).parent_id, self.user.pk)
                self.assertTrue(AccountLinkQueue.objects.get(platform=platform, userprofile=self.user).verified)
                self.assertEqual(self.moderate(platform, identifier).status_code, 200)
                self.user.refresh_from_db()
                self.assertFalse(self.user.can_hide_realname)

    def test_discord_rejects_invalid_ids_before_creating_or_moderating(self):
        for identifier in ('0', '01', '-1', '1.5', '1e18', 'player', '１２３', '123 ', ' 123', '1' * 21):
            with self.subTest(identifier=identifier):
                self.client.force_login(self.user)
                self.assertEqual(self.create(Platform.DISCORD, identifier).status_code, 422)
                self.assertEqual(self.moderate(Platform.DISCORD, identifier).status_code, 422)
        self.assertFalse(AccountLinkQueue.objects.exists())
        self.assertFalse(AccountDiscord.objects.exists())

    def test_anonymous_creation_and_nonstaff_verification_are_rejected(self):
        self.assertIn(self.create(Platform.DISCORD, self.discord_id).status_code, (401, 403))
        self.client.force_login(self.user)
        self.assertEqual(self.create(Platform.DISCORD, self.discord_id).status_code, 200)
        self.assertEqual(self.client.post('/api/accountlink/verify/', {'id': self.user.pk, 'platform': 'd', 'identifier': self.discord_id}).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post('/api/accountlink/verify/', {'id': self.user.pk, 'platform': 'd', 'identifier': self.discord_id}).status_code, 403)
        self.assertFalse(AccountDiscord.objects.exists())

    def test_private_details_are_visible_only_to_owner_and_staff(self):
        for platform, identifier, _model in self.platforms:
            self.client.force_login(self.user)
            self.create(platform, identifier)
            self.moderate(platform, identifier)
        for viewer in (self.user, self.staff):
            with self.subTest(viewer=viewer.username):
                self.client.force_login(viewer)
                response = self.client.get(f'/api/accountlink/{self.user.pk}')
                self.assertIn('no-store', response['Cache-Control'])
                data = response.json()
                self.assertEqual({link['platform'] for link in data['summary']}, {'d', 'q'})
                self.assertEqual(data['d'], {'id': self.discord_id, 'parent': self.user.pk})
                self.assertEqual(data['q'], {'id': 12345678, 'parent': self.user.pk})
        for viewer in (self.other, None):
            if viewer:
                self.client.force_login(viewer)
            else:
                self.client.logout()
            response = self.client.get(f'/api/accountlink/{self.user.pk}')
            self.assertIn('no-store', response['Cache-Control'])
            self.assertEqual(response.json()['summary'], [])
            self.assertIsNone(response.json()['d'])
            self.assertIsNone(response.json()['q'])
        for platform in ('d', 'q'):
            self.assertEqual(self.client.get('/api/userprofile/query', {'platform': platform, 'id': self.discord_id}).status_code, 422)

    def test_conflicting_claim_never_reassigns_verified_identity(self):
        for platform, identifier, model in self.platforms:
            with self.subTest(platform=platform):
                self.client.force_login(self.user)
                self.create(platform, identifier)
                self.assertEqual(self.moderate(platform, identifier).status_code, 200)
                self.client.force_login(self.other)
                self.assertEqual(self.create(platform, identifier).status_code, 200)
                self.assertEqual(self.moderate(platform, identifier, user=self.other).status_code, 409)
                self.assertEqual(model.objects.get(pk=identifier).parent_id, self.user.pk)
                self.assertFalse(AccountLinkQueue.objects.get(platform=platform, userprofile=self.other).verified)

    def test_moderator_can_remove_pending_or_verified_links_and_allow_correction(self):
        for platform, identifier, model in self.platforms:
            with self.subTest(platform=platform):
                self.client.force_login(self.user)
                self.create(platform, identifier)
                self.assertEqual(self.moderate(platform, identifier, action='unverify').status_code, 200)
                self.assertFalse(AccountLinkQueue.objects.filter(platform=platform).exists())
                self.client.force_login(self.user)
                self.create(platform, identifier)
                self.assertEqual(self.moderate(platform, identifier).status_code, 200)
                self.assertEqual(self.moderate(platform, identifier, action='unverify').status_code, 200)
                self.assertFalse(model.objects.exists())
                self.client.force_login(self.user)
                self.assertEqual(self.create(platform, '999999999999999999').status_code, 200)

    def test_oauth_routes_are_removed_and_mineracer_still_rejects_manual_linking(self):
        for route in ('config', 'callback'):
            self.assertEqual(self.client.get(f'/api/accountlink/discord/{route}').status_code, 404)
        for route in ('start', 'unlink'):
            self.assertEqual(self.client.post(f'/api/accountlink/discord/{route}').status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.create(Platform.MINERACER, '123').status_code, 400)
