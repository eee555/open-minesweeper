from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlencode

from django.core.files.base import ContentFile
from django.test import override_settings, TestCase
from django.utils import timezone

from msuser.models import UserMS
from userprofile.models import UserProfile
from videomanager.models import ExpandVideoModel, VideoModel
from videomanager.view_utils import generate_file_stream


@override_settings(RATELIMIT_ENABLE=False)
class UserProfileAdminApiTests(TestCase):
    def setUp(self):
        self.staff = UserProfile.objects.create_user(
            username='profile_staff',
            email='profile_staff@example.com',
            password='password',
            is_staff=True,
            userms=UserMS.objects.create(),
        )
        self.userms = UserMS.objects.create(
            identifiers=['alpha', 'beta'],
            video_num_limit=100,
        )
        self.user = UserProfile.objects.create_user(
            username='profile_user',
            email='profile_user@example.com',
            password='password',
            realname='旧名',
            firstname='Old',
            lastname='Name',
            userms=self.userms,
        )
        self.client.force_login(self.staff)

    def patch_update(self, user_id, payload):
        return self.client.patch(
            f'/api/userprofile/admin/update/{user_id}',
            urlencode(payload),
            content_type='application/x-www-form-urlencoded',
        )

    def test_admin_get_user_profile(self):
        response = self.client.get(f'/api/userprofile/admin/detail/{self.user.id}')

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data['id'], self.user.id)
        self.assertEqual(data['username'], 'profile_user')
        self.assertEqual(data['firstname'], 'Old')
        self.assertEqual(data['lastname'], 'Name')
        self.assertEqual(data['userms_id'], self.userms.id)
        self.assertEqual(data['userms_identifiers'], ['alpha', 'beta'])
        self.assertEqual(data['userms_video_num_limit'], 100)

    def test_admin_update_user_profile(self):
        old_updated = timezone.now() - timedelta(days=1)
        UserProfile.objects.filter(id=self.user.id).update(date_updated=old_updated)

        response = self.patch_update(self.user.id, {
            'username': 'profile_user_new',
            'email': 'profile_user_new@example.com',
            'firstname': 'New',
            'lastname': 'Player',
            'realname': '新名',
            'signature': 'updated signature',
            'country': 'CN',
            'is_banned': True,
            'left_realname_n': 2,
            'left_avatar_n': 3,
            'left_signature_n': 4,
        })

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data['username'], 'profile_user_new')
        self.assertEqual(data['firstname'], 'New')
        self.assertEqual(data['lastname'], 'Player')
        self.assertTrue(data['is_banned'])

        self.user.refresh_from_db()
        self.userms.refresh_from_db()
        self.assertEqual(self.user.email, 'profile_user_new@example.com')
        self.assertEqual(self.user.signature, 'updated signature')
        self.assertEqual(self.user.country, 'CN')
        self.assertEqual(self.user.left_realname_n, 2)
        self.assertEqual(self.user.left_avatar_n, 3)
        self.assertEqual(self.user.left_signature_n, 4)
        self.assertGreater(self.user.date_updated, old_updated)
        self.assertEqual(self.userms.video_num_limit, 100)

    def test_admin_update_writes_equal_value(self):
        old_updated = timezone.now() - timedelta(days=1)
        UserProfile.objects.filter(id=self.user.id).update(date_updated=old_updated)

        response = self.patch_update(self.user.id, {
            'realname': self.user.realname,
        })

        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertGreater(self.user.date_updated, old_updated)

    def test_staff_cannot_update_another_staff_user(self):
        other_staff = UserProfile.objects.create_user(
            username='profile_other_staff',
            email='profile_other_staff@example.com',
            password='password',
            is_staff=True,
            userms=UserMS.objects.create(),
        )

        response = self.patch_update(other_staff.id, {
            'realname': 'blocked',
        })

        self.assertEqual(response.status_code, 403)
        other_staff.refresh_from_db()
        self.assertNotEqual(other_staff.realname, 'blocked')

    def test_non_staff_cannot_use_admin_api(self):
        self.client.force_login(self.user)

        get_response = self.client.get(f'/api/userprofile/admin/detail/{self.user.id}')
        patch_response = self.patch_update(self.user.id, {
            'realname': 'blocked',
        })

        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(patch_response.status_code, 403)

    def test_legacy_staff_userprofile_urls_are_removed(self):
        get_response = self.client.get('/userprofile/get/', {'id': self.user.id})
        post_response = self.client.post('/userprofile/set/', {
            'id': self.user.id,
            'field': 'realname',
            'value': 'blocked',
        })

        self.assertEqual(get_response.status_code, 404)
        self.assertEqual(post_response.status_code, 404)


@override_settings(RATELIMIT_ENABLE=False)
class UserProfileUpdateApiTests(TestCase):
    def setUp(self):
        self.user = UserProfile.objects.create_user(
            username='self_user',
            email='self_user@example.com',
            password='password',
            userms=UserMS.objects.create(),
        )
        self.client.force_login(self.user)

    def test_update_profile_keeps_error_when_name_censorship_fails(self):
        for result, category in [(False, 'illegal'), (RuntimeError('verification unavailable'), 'unknown')]:
            with self.subTest(category=category), patch('userprofile.services.verify_text') as verify:
                if isinstance(result, Exception):
                    verify.side_effect = result
                else:
                    verify.return_value = result
                response = self.client.post('/api/userprofile/update_profile', {'realname': 'Jason Weng'})
                verify.assert_called_once()
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(response.json()['realname'], {'type': 'error', 'object': 'censorship', 'category': category})
            self.user.refresh_from_db()
            self.assertEqual(self.user.realname, '匿名')
            self.assertFalse(self.user.has_realname())


@override_settings(RATELIMIT_ENABLE=False)
class RealnamePrivacyTests(TestCase):
    patch_update = UserProfileAdminApiTests.patch_update

    def setUp(self):
        UserProfileAdminApiTests.setUp(self)
        self.user.can_hide_realname = True
        self.user.hide_realname = True
        self.user.save(update_fields=['can_hide_realname', 'hide_realname'])

    def privacy(self, hide):
        return self.client.post('/api/userprofile/update_profile', {'hide_realname': hide})

    def test_public_and_private_names_have_distinct_contracts(self):
        for viewer in (None, self.user, self.staff):
            with self.subTest(viewer=viewer):
                self.client.logout()
                if viewer:
                    self.client.force_login(viewer)
                for url in (f'/api/userprofile/info/{self.user.pk}', f'/api/userprofile/infobulk?ids={self.user.pk}'):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200, response.content)
                    data = response.json()
                    if isinstance(data, list):
                        data = data[0]
                    for field in ('realname', 'firstname', 'lastname'):
                        self.assertEqual(data[field], 'hidden')
                        self.assertNotIn('_' + field, data)
                    self.assertNotIn('has_realname', data)
                    self.assertNotIn('hide_realname', data)
        self.client.force_login(self.user)
        response = self.client.get('/api/userprofile/info/0')
        self.assertEqual(response.json()['realname'], '旧名')
        self.assertTrue(response.json()['hide_realname'])
        with patch('common.api.TopRankingCache.get_anchors', return_value={}):
            response = self.client.get('/api/common/loginauto')
        self.assertEqual(response.json()['user']['realname'], '旧名')
        self.assertTrue(response.json()['user']['hide_realname'])
        self.client.force_login(self.staff)
        response = self.client.get(f'/api/userprofile/admin/detail/{self.user.pk}')
        self.assertEqual(response.json()['realname'], '旧名')

    def test_getters_and_realname_gate_use_original_values(self):
        self.assertEqual(self.user.realname, 'hidden')
        self.assertTrue(self.user.has_realname())
        self.assertEqual(self.user._realname, '旧名')
        for missing in ('', '   ', '匿名'):
            with self.subTest(missing=missing):
                self.user.realname = missing
                self.assertFalse(self.user.has_realname())
                self.assertFalse(self.user.is_name_hidden)
                self.assertEqual(self.user.realname, missing)

    def test_private_switch_revoke_and_name_clear(self):
        self.client.force_login(self.user)
        self.assertEqual(self.privacy(False).json()['hide_realname']['type'], 'success')
        self.user.refresh_from_db()
        self.assertFalse(self.user.hide_realname)
        self.assertEqual(self.privacy(True).json()['hide_realname']['type'], 'success')
        self.user.refresh_from_db()
        self.assertTrue(self.user.hide_realname)
        self.client.force_login(self.staff)
        response = self.patch_update(self.user.pk, {'can_hide_realname': False})
        self.assertFalse(response.json()['hide_realname'])
        self.client.force_login(self.user)
        self.assertEqual(self.privacy(True).json()['hide_realname'], {'type': 'error', 'object': 'privacy', 'category': 'not_authorized'})
        self.assertEqual(self.privacy(False).json()['hide_realname']['type'], 'success')
        self.client.force_login(self.staff)
        self.patch_update(self.user.pk, {'can_hide_realname': True})
        self.client.force_login(self.user)
        self.privacy(True)
        self.client.force_login(self.staff)
        response = self.patch_update(self.user.pk, {'realname': ''})
        self.assertTrue(response.json()['can_hide_realname'])
        self.assertFalse(response.json()['hide_realname'])
        self.client.force_login(self.user)
        self.assertEqual(self.privacy(True).json()['hide_realname'], {'type': 'error', 'object': 'privacy', 'category': 'realname_required'})

    def test_saving_name_and_hiding_is_atomic(self):
        self.user._realname = '匿名'
        self.user._firstname = ''
        self.user.hide_realname = False
        self.user.save(update_fields=['_realname', '_firstname', 'hide_realname'])
        self.client.force_login(self.user)
        with patch('userprofile.services.verify_text', return_value=True):
            response = self.client.post('/api/userprofile/update_profile', {'realname': '首次实名', 'hide_realname': True})
        self.assertEqual(response.json()['hide_realname']['type'], 'success')
        self.user.refresh_from_db()
        self.assertEqual(self.user._realname, '首次实名')
        self.assertEqual(self.user.realname, 'hidden')
        # An empty English name remains writable while all public names are masked.
        with patch('userprofile.services.verify_text', return_value=True):
            response = self.client.post('/api/userprofile/update_profile', {'firstname': 'Given'})
        self.assertEqual(response.json()['firstname']['type'], 'success')
        self.user.refresh_from_db()
        self.assertEqual(self.user._firstname, 'Given')
        self.assertTrue(self.user.hide_realname)

    def test_failed_privacy_or_name_validation_rolls_back_names(self):
        self.user._realname = '匿名'
        self.user.can_hide_realname = False
        self.user.hide_realname = False
        self.user.save(update_fields=['_realname', 'can_hide_realname', 'hide_realname'])
        self.client.force_login(self.user)
        with patch('userprofile.services.verify_text', return_value=True):
            response = self.client.post('/api/userprofile/update_profile', {'realname': '首次实名', 'hide_realname': True, 'can_hide_realname': True})
        self.assertEqual(response.json()['realname']['type'], 'error')
        self.user.refresh_from_db()
        self.assertEqual(self.user._realname, '匿名')
        self.assertFalse(self.user.can_hide_realname)
        for field in ('realname', 'firstname', 'lastname'):
            with self.subTest(field=field):
                response = self.client.post('/api/userprofile/update_profile', {field: ' hidden ', 'realname': 'hidden' if field == 'realname' else '首次实名'})
                self.assertEqual(response.json()['realname']['type'], 'error')
                self.client.force_login(self.staff)
                self.assertEqual(self.patch_update(self.user.pk, {field: 'hidden'}).status_code, 400)
                self.client.force_login(self.user)
                self.user.refresh_from_db()
                self.assertEqual(self.user._realname, '匿名')

    def test_video_queries_and_export_do_not_bypass_name_getters(self):
        with TemporaryDirectory() as root, override_settings(MEDIA_ROOT=root):
            video = VideoModel(player=self.user, video=ExpandVideoModel.objects.create(identifier='privacy'), software='e', level='e', bv=100, timems=100000)
            video.file.save('privacy.evf', ContentFile(b'original replay'))  # noqa: DJM100
            other = VideoModel.objects.create(player=self.staff, video=ExpandVideoModel.objects.create(), software='e', level='e', bv=100, timems=90000)
            response = self.client.get('/api/video/query', {'level': 'e', 'mode': '00'})
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual([row['id'] for row in response.json()['videos']], [other.pk, video.pk])
            row = next(row for row in response.json()['videos'] if row['id'] == video.pk)
            self.assertEqual(row['player__realname'], 'hidden')
            for sort_field in ('player__realname', 'player___realname'):
                for reverse in (False, True):
                    with self.subTest(sort_field=sort_field, reverse=reverse):
                        response = self.client.get('/api/video/query', {'level': 'e', 'mode': '00', 'o': sort_field, 'r': reverse})
                        self.assertEqual(response.status_code, 400, response.content)
            response = self.client.get(f'/api/video/admin/detail/{video.pk}')
            self.assertEqual(response.json()['player__realname'], self.user._realname)
            self.assertEqual(self.client.get('/video/get/', {'id': video.pk}).status_code, 404)
            stream = iter(generate_file_stream(VideoModel.objects.filter(pk=video.pk)))
            next(stream)
            self.assertEqual(next(stream).decode(), f'{self.user.pk}_hidden/privacy.evf')
