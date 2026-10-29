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
        self.assertEqual((userms.video_num_total, userms.video_size_total), (1, video.file_size))
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
