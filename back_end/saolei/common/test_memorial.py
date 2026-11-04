from datetime import timedelta
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlencode
import uuid

from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import Client, override_settings, TestCase
from django.utils import timezone

from accountlink.models import AccountLinkQueue, AccountMinesweeperGames, AccountSaolei, AccountWorldOfMinesweeper, Platform
from config.text_choices import MS_TextChoices
from identifier.models import Identifier
from msuser.models import UserMS
from userprofile.forms import EmailForm, UserRetrieveForm
from userprofile.models import UserProfile
from utils.parser import MSVideoParser
from videomanager.cache import cache, newest_cache
from videomanager.models import VideoModel


BASE = '/api/common/admin/memorial'


class MemorialFixtures:
    def setUp(self):
        super().setUp()
        self.enterContext(patch('medal.signals.enqueue_player_refresh'))
        self.enterContext(override_settings(RATELIMIT_ENABLE=False))
        self.actor = UserProfile.objects.create_user(pk=1000, username='site-owner', email='owner@example.com', is_superuser=True, userms=UserMS.objects.create(pk=2000))
        self.client.force_login(self.actor)

    def create(self, user_id=42, userms_id=70, username='legend'):
        call_command('create_memorial_account', str(user_id), str(userms_id), username, realname='传奇玩家', stdout=StringIO())
        return UserProfile.objects.get(pk=user_id)


class MemorialCommandTests(MemorialFixtures, TestCase):
    def test_creates_independent_ids_and_public_identity_without_login(self):
        user = self.create()
        self.assertEqual((user.pk, user.userms_id), (42, 70))
        self.assertTrue(user.is_memorial)
        self.assertFalse(user.is_active or user.is_staff or user.is_superuser or user.has_usable_password())
        self.assertEqual(user.userms.video_num_total, 0)
        self.assertIsNone(authenticate(username=user.username, password='password123'))
        self.assertEqual(self.client.get('/api/userprofile/info/42').json()['is_memorial'], True)
        self.assertEqual(self.client.get('/api/userprofile/query', {'id': '42'}).json()['users'][0]['is_memorial'], True)
        with self.assertRaises(CommandError):
            self.create()
        self.assertEqual(UserMS.objects.count(), 2)

    def test_only_vacant_holes_below_each_tables_own_maximum_are_allowed(self):
        for user_id, userms_id in [(0, 70), (-1, 70), (1000, 70), (1001, 70), (42, 0), (42, 2000), (42, 2001), (42, 3000)]:
            with self.subTest(user_id=user_id, userms_id=userms_id), self.assertRaises(CommandError):
                self.create(user_id, userms_id)
        UserMS.objects.create(pk=70)
        with self.assertRaises(CommandError):
            self.create()
        self.assertFalse(UserProfile.objects.filter(pk=42).exists())

    def test_equal_and_cross_table_numeric_matches_are_allowed(self):
        self.create(44, 44, 'same-ids')
        other = UserProfile.objects.create_user(pk=70, username='other', email='other@example.com', userms=UserMS.objects.create(pk=42))
        self.create()
        other.refresh_from_db()
        self.assertEqual((other.pk, other.userms_id), (70, 42))

    def test_invalid_profile_rolls_back_new_userms_and_empty_tables_reject_creation(self):
        with self.assertRaises(CommandError):
            self.create(username=self.actor.username)
        self.assertFalse(UserMS.objects.filter(pk=70).exists())
        UserProfile.objects.all().delete()
        self.assertFalse(UserMS.objects.exists())
        with self.assertRaises(CommandError):
            self.create()

    def test_authentication_guards_and_existing_staff_permissions_remain(self):
        user = self.create()
        self.assertFalse(UserRetrieveForm({'email': user.email, 'password': 'password123'}).is_valid())
        self.assertFalse(EmailForm({'email': user.email, 'captcha': 'test', 'hashkey': 'hash'}).is_valid())
        user.is_active = True
        with self.assertRaises(ValidationError):
            user.save(update_fields=['is_active'])
        with self.assertRaises(IntegrityError), transaction.atomic():
            UserProfile.objects.filter(pk=42).update(is_staff=True)
        self.assertEqual(self.client.post('/api/userprofile/admin/staff', {'user_id': 42, 'is_staff': True}, content_type='application/json').status_code, 409)
        staff = UserProfile.objects.create_user(username='editor', email='editor@example.com', is_staff=True)
        self.client.force_login(staff)
        response = self.client.patch('/api/userprofile/admin/update/42', urlencode({'signature': '通用管理'}), content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 200, response.content)
        user.refresh_from_db()
        self.assertEqual(user.signature, '通用管理')


class MemorialUploadTests(MemorialFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.enterContext(patch('identifier.utils.verify_text', return_value=True))
        self.create()
        directory = self.enterContext(TemporaryDirectory())
        self.enterContext(override_settings(MEDIA_ROOT=directory))
        key = f'memorial-tests:{uuid.uuid4().hex}'
        self.enterContext(patch.object(newest_cache, 'key', key))
        self.addCleanup(cache.delete, key)
        self.when = timezone.now() - timedelta(days=3650)

    def replay(self, name='standard_gsc.evf'):
        path = Path(__file__).parent / 'test_fixtures/video_upload_ranking' / name
        return SimpleUploadedFile(name, path.read_bytes())

    def upload(self, when=None, name='standard_gsc.evf', identifiers=()):
        return self.client.post(f'{BASE}/users/42/videos', {'upload_time': (when or self.when).isoformat(), 'identifiers': json.dumps(identifiers), 'file': self.replay(name)})

    def test_only_superusers_can_upload_including_root_without_staff(self):
        self.assertFalse(self.actor.is_staff)
        response = self.client.get(f'{BASE}/users/42/videos')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['user']['userms_id'], 70)
        staff = UserProfile.objects.create_user(username='staff', email='staff@example.com', is_staff=True)
        ordinary = UserProfile.objects.create_user(username='ordinary', email='ordinary@example.com')
        for viewer in (staff, ordinary, None):
            with self.subTest(viewer=viewer):
                if viewer is None:
                    self.client.logout()
                else:
                    self.client.force_login(viewer)
                self.assertEqual(self.client.get(f'{BASE}/users/42/videos').status_code, 401)
                self.assertEqual(self.upload(identifiers=['must-not-bind']).status_code, 401)
        self.assertFalse(Identifier.objects.exists())
        self.assertFalse(VideoModel.objects.exists())

    def test_invalid_targets_are_rejected_before_import_services(self):
        user = UserProfile.objects.get(pk=42)
        user.userms = None
        user.save(update_fields=['userms'])
        for user_id, status_code in ((1000, 409), (999, 404), (42, 409)):
            with self.subTest(user_id=user_id), patch('common.memorial.api.register_memorial_identifiers') as bind, patch('common.memorial.api.upload_memorial_video') as upload:
                self.assertEqual(self.client.get(f'{BASE}/users/{user_id}/videos').status_code, status_code)
                response = self.client.post(f'{BASE}/users/{user_id}/videos', {
                    'upload_time': self.when.isoformat(), 'identifiers': '["must-not-bind"]', 'file': self.replay(),
                })
                self.assertEqual(response.status_code, status_code)
                bind.assert_not_called()
                upload.assert_not_called()

    def test_csrf_is_required_for_upload(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        data = {'upload_time': self.when.isoformat(), 'identifiers': '[]', 'file': self.replay()}
        self.assertEqual(client.post(f'{BASE}/users/42/videos', data).status_code, 403)
        self.assertFalse(VideoModel.objects.exists())
        token = client.get(f'{BASE}/users/42/videos').json()['csrf_token']
        data['file'] = self.replay()
        response = client.post(f'{BASE}/users/42/videos', data, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200, response.content)

    def test_binding_upload_dates_counts_and_deduplication_reuse_gsc_rules(self):
        identifier = MSVideoParser(self.replay()).identifier
        response = self.upload(identifiers=[identifier, 'another-selected', identifier])
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([item['bound'] for item in response.json()['bindings']], [True, True])
        self.assertEqual(Identifier.objects.filter(userms_id=70).count(), 2)
        video = VideoModel.objects.get()
        self.assertEqual((video.player_id, video.state, video.upload_time), (42, MS_TextChoices.State.OFFICIAL, self.when))
        userms = UserMS.objects.get(pk=70)
        self.assertEqual((userms.video_num_total, userms.video_size_total), (1, video.stored_file_size))
        with patch('common.services.MSVideoParser') as parse:
            self.assertEqual(self.upload(self.when + timedelta(days=1)).status_code, 200)
            self.assertEqual(self.upload(self.when - timedelta(days=1)).status_code, 200)
        parse.assert_not_called()
        video.refresh_from_db()
        self.assertEqual(video.upload_time, self.when - timedelta(days=1))
        self.assertEqual(VideoModel.objects.count(), 1)
        self.assertEqual(self.upload(self.when.replace(tzinfo=None)).status_code, 422)

    def test_all_binding_failures_still_upload_and_do_not_transfer_another_owners_file(self):
        identifier = MSVideoParser(self.replay()).identifier
        Identifier.objects.create(identifier=identifier, safe=True, userms=self.actor.userms)
        Identifier.objects.create(identifier='unsafe', safe=False)
        response = self.upload(identifiers=[identifier, 'unsafe'])
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([item['bound'] for item in response.json()['bindings']], [False, False])
        video = VideoModel.objects.get()
        self.assertEqual(video.state, MS_TextChoices.State.IDENTIFIER)
        video.player = self.actor
        video.save(update_fields=['player'])
        old_time = video.upload_time
        response = self.upload(self.when - timedelta(days=1))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['bindings'], [])
        video.refresh_from_db()
        self.assertEqual((video.player_id, video.upload_time), (self.actor.pk, old_time))

    def test_unexpected_binding_errors_do_not_abort_upload(self):
        with patch('common.memorial.services.bind_import_identifier', side_effect=RuntimeError('binding failed')):
            response = self.upload(identifiers=['first', 'second'])
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.json()['bindings']), 2)
        self.assertTrue(VideoModel.objects.exists())

    def test_upload_failure_preserves_bindings_and_returns_their_results(self):
        identifier = MSVideoParser(self.replay()).identifier
        response = self.upload(name='incomplete.evf', identifiers=[identifier])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['bindings'][0]['bound'], True)
        self.assertEqual(Identifier.objects.get(identifier=identifier).userms_id, 70)
        self.assertFalse(VideoModel.objects.exists())
        self.assertEqual(self.upload().status_code, 200)
        self.assertEqual(VideoModel.objects.get().state, MS_TextChoices.State.OFFICIAL)


class MemorialAccountLinkTests(MemorialFixtures, TestCase):
    LINKS = f'{BASE}/users/42/account-links'

    def setUp(self):
        super().setUp()
        self.create()

    def post(self, platform, identifier):
        return self.client.post(self.LINKS, {'platform': platform, 'identifier': str(identifier)})

    def test_superuser_assigns_and_lists_saolei_msgames_and_wom_links(self):
        for platform, identifier, model in (
            (Platform.SAOLEI, 901, AccountSaolei),
            (Platform.MSGAMES, 902, AccountMinesweeperGames),
            (Platform.WOM, 903, AccountWorldOfMinesweeper),
        ):
            with self.subTest(platform=platform):
                response = self.post(platform.value, identifier)
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()['identifier'], str(identifier))
                self.assertTrue(model.objects.filter(pk=identifier, parent_id=42).exists())
                self.assertTrue(AccountLinkQueue.objects.filter(platform=platform, identifier=str(identifier), userprofile_id=42, verified=True).exists())
        listed = self.client.get(self.LINKS)
        self.assertEqual(listed.status_code, 200, listed.content)
        self.assertEqual({item['platform'] for item in listed.json()['links']}, {'c', 'a', 'w'})
        self.assertIn('csrf_token', listed.json())

    def test_only_assignable_platforms_are_accepted(self):
        for platform in (Platform.DISCORD, Platform.BILIBILI, Platform.QQ, Platform.MINERACER, Platform.CLASSIC, 'z', ''):
            with self.subTest(platform=platform):
                value = platform.value if hasattr(platform, 'value') else platform
                self.assertEqual(self.post(value, 904).status_code, 400)
        self.assertFalse(AccountLinkQueue.objects.exists())

    def test_target_must_be_a_memorial_account(self):
        for user_id in (1000, 999):
            for method, path in (('post', f'{BASE}/users/{user_id}/account-links'), ('get', f'{BASE}/users/{user_id}/account-links')):
                with self.subTest(user_id=user_id, method=method):
                    response = getattr(self.client, method)(path, {'platform': 'c', 'identifier': '905'} if method == 'post' else None)
                    self.assertEqual(response.status_code, 409 if user_id == 1000 else 404)
        self.assertFalse(AccountLinkQueue.objects.exists())

    def test_staff_and_ordinary_users_cannot_assign_links(self):
        staff = UserProfile.objects.create_user(username='staff-link', email='staff-link@example.com', is_staff=True)
        ordinary = UserProfile.objects.create_user(username='ordinary-link', email='ordinary-link@example.com')
        for viewer in (staff, ordinary):
            with self.subTest(viewer=viewer.username):
                self.client.force_login(viewer)
                self.assertEqual(self.post('c', 906).status_code, 401)
                self.assertEqual(self.client.get(self.LINKS).status_code, 401)
        self.assertFalse(AccountLinkQueue.objects.exists())

    def test_reassign_replaces_identifier_and_rejects_another_owners_account(self):
        self.assertEqual(self.post('c', 907).status_code, 200)
        self.assertEqual(self.post('c', 908).status_code, 200)
        self.assertEqual(list(AccountLinkQueue.objects.filter(platform='c', userprofile_id=42).values_list('identifier', flat=True)), ['908'])
        self.assertFalse(AccountSaolei.objects.filter(pk=907).exists())
        owner = UserProfile.objects.create_user(username='saolei-owner', email='saolei-owner@example.com')
        AccountSaolei.objects.create(pk=909, parent=owner)
        self.assertEqual(self.post('c', 909).status_code, 409)
        self.assertEqual(AccountSaolei.objects.get(pk=909).parent_id, owner.pk)

    def test_pending_application_of_another_user_is_replaced_not_verified(self):
        other = UserProfile.objects.create_user(username='pending-owner', email='pending-owner@example.com')
        AccountLinkQueue.objects.create(platform=Platform.SAOLEI, identifier='910', userprofile=other)
        self.assertEqual(self.post('c', 910).status_code, 200)
        self.assertFalse(AccountLinkQueue.objects.filter(userprofile=other, identifier='910').exists())
        self.assertTrue(AccountLinkQueue.objects.filter(userprofile_id=42, identifier='910', verified=True).exists())

    def test_unlink_removes_only_the_requested_platform(self):
        self.assertEqual(self.post('c', 911).status_code, 200)
        self.assertEqual(self.post('a', 912).status_code, 200)
        response = self.client.delete(f'{self.LINKS}?platform=c')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['removed'])
        self.assertFalse(AccountSaolei.objects.filter(pk=911).exists())
        self.assertFalse(AccountLinkQueue.objects.filter(platform='c').exists())
        self.assertTrue(AccountMinesweeperGames.objects.filter(pk=912, parent_id=42).exists())
        self.assertEqual(self.client.delete(f'{self.LINKS}?platform=c').status_code, 404)

    def test_assigning_links_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        self.assertEqual(client.post(self.LINKS, {'platform': 'c', 'identifier': '913'}).status_code, 403)
        token = client.get(self.LINKS).json()['csrf_token']
        response = client.post(self.LINKS, {'platform': 'c', 'identifier': '913'}, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(AccountLinkQueue.objects.filter(identifier='913', verified=True).exists())
