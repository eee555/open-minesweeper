from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.core.files.base import ContentFile
from django.test import Client, override_settings, TestCase

from config.text_choices import MS_TextChoices
from msuser.models import UserMS
from userprofile.models import UserProfile
from utils.ranking_lock import RankingRefreshBusy
from .models import ExpandVideoModel, VideoModel
from .services import freeze_video_by_id


class VideoFreezeTests(TestCase):
    url = '/api/video/admin/freeze'

    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        configuration = override_settings(MEDIA_ROOT=media.name)
        configuration.enable()
        self.addCleanup(configuration.disable)
        self.mocks = {}
        for target in ['speedranking.services._sync_video', 'effranking.services._sync_video', 'videomanager.cache.cache']:
            replacement = patch(target)
            self.mocks[target] = replacement.start()
            self.addCleanup(replacement.stop)
        self.owner = UserProfile.objects.create_user(username='freeze-owner', email='freeze-owner@example.com', userms=UserMS.objects.create())
        self.staff = UserProfile.objects.create_user(username='freeze-staff', email='freeze-staff@example.com', is_staff=True)
        self.video = VideoModel.objects.create(
            player=self.owner, video=ExpandVideoModel.objects.create(identifier='freeze'),
            file=ContentFile(b'fixture', name='freeze.evf'), file_size=7,
            state=MS_TextChoices.State.OFFICIAL, software='e', level='b', mode='00', bv=4, timems=1000,
        )

    def freeze(self, reason='测试冻结原因'):
        return self.client.post(self.url, {'id': self.video.pk, 'freeze_reason': reason}, content_type='application/json')

    def assert_unchanged(self):
        self.video.refresh_from_db()
        self.video.video.refresh_from_db()
        self.assertEqual(self.video.state, MS_TextChoices.State.OFFICIAL)
        self.assertEqual(self.video.video.freeze_reason, '')

    def test_requires_staff_for_access_and_freezing(self):
        for user in (None, self.owner):
            with self.subTest(user=user):
                if user is not None:
                    self.client.force_login(user)
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertEqual(self.freeze().status_code, 403)
                self.assert_unchanged()
        self.client.force_login(self.staff)
        access = self.client.get(self.url)
        self.assertEqual(access.status_code, 200, access.content)
        self.assertIn('csrf_token', access.json())
        self.assert_unchanged()

    def test_freezes_with_long_multiline_reason_and_preserves_file_and_upload_time(self):
        self.client.force_login(self.staff)
        upload_time = self.video.upload_time
        path = Path(self.video.file.path)
        reason = '  第一行\n' + '详细冻结原因' * 3000 + '\n最后一行  '
        with self.captureOnCommitCallbacks(execute=True):
            response = self.freeze(reason)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {'id': self.video.pk, 'state': MS_TextChoices.State.FROZEN, 'freeze_reason': reason.strip()})
        self.video.refresh_from_db()
        self.video.video.refresh_from_db()
        self.assertEqual(self.video.state, MS_TextChoices.State.FROZEN)
        self.assertEqual(self.video.video.freeze_reason, reason.strip())
        self.assertEqual(self.video.upload_time, upload_time)
        self.assertEqual(path.read_bytes(), b'fixture')
        self.mocks['videomanager.cache.cache'].hdel.assert_called_with('newest_queue', self.video.pk)
        self.mocks['speedranking.services._sync_video'].assert_called_once_with(self.video.pk, self.owner.pk)
        self.mocks['effranking.services._sync_video'].assert_called_once()
        details = self.client.get(f'/api/video/admin/detail/{self.video.pk}')
        self.assertEqual(details.status_code, 200, details.content)
        self.assertEqual(details.json()['id'], self.video.pk)
        self.assertEqual(details.json()['video__freeze_reason'], reason.strip())

    def test_can_update_reason_of_already_frozen_video(self):
        self.client.force_login(self.staff)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.freeze().status_code, 200)
        for mocked in self.mocks.values():
            mocked.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.freeze('修正后的原因')
        self.assertEqual(response.status_code, 200, response.content)
        self.video.video.refresh_from_db()
        self.assertEqual(self.video.video.freeze_reason, '修正后的原因')
        self.mocks['speedranking.services._sync_video'].assert_not_called()
        self.mocks['effranking.services._sync_video'].assert_not_called()

    def test_rejects_invalid_ids_and_empty_or_nontext_reasons(self):
        self.client.force_login(self.staff)
        payloads = [
            {}, {'id': self.video.pk}, {'id': self.video.pk, 'freeze_reason': ''},
            {'id': self.video.pk, 'freeze_reason': ' \t\n '}, {'id': self.video.pk, 'freeze_reason': None},
            {'id': self.video.pk, 'freeze_reason': 123},
            *({'id': value, 'freeze_reason': '原因'} for value in (0, -1, True, 1.5, str(self.video.pk), 2**63)),
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                response = self.client.post(self.url, payload, content_type='application/json')
                self.assertEqual(response.status_code, 422, response.content)
                self.assert_unchanged()

    def test_missing_video_returns_404(self):
        self.client.force_login(self.staff)
        response = self.client.post(self.url, {'id': self.video.pk + 1000, 'freeze_reason': '原因'}, content_type='application/json')
        self.assertEqual(response.status_code, 404, response.content)
        self.assert_unchanged()

    def test_state_and_reason_roll_back_together(self):
        self.client.force_login(self.staff)
        with patch.object(VideoModel, 'save', side_effect=RuntimeError('state save failed')):
            with self.assertRaisesMessage(RuntimeError, 'state save failed'):
                self.freeze()
        self.assert_unchanged()
        self.assertTrue(Path(self.video.file.path).exists())

    def test_ranking_rebuild_rejects_before_changing_state_or_reason(self):
        self.client.force_login(self.staff)
        with patch('utils.ranking_lock.ranking_access', side_effect=RankingRefreshBusy):
            response = self.freeze()
        self.assertEqual(response.status_code, 503, response.content)
        self.assertEqual(response['Retry-After'], '1')
        self.assert_unchanged()

    def test_requires_csrf_and_access_initializes_cookie(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        payload = {'id': self.video.pk, 'freeze_reason': '原因'}
        response = client.post(self.url, payload, content_type='application/json')
        self.assertEqual(response.status_code, 403, response.content)
        self.assert_unchanged()
        access = client.get(self.url)
        self.assertEqual(access.status_code, 200, access.content)
        self.assertIn(settings.CSRF_COOKIE_NAME, access.cookies)
        self.assertIn('no-store', access['Cache-Control'])
        response = client.post(self.url, payload, content_type='application/json', HTTP_X_CSRFTOKEN=access.json()['csrf_token'])
        self.assertEqual(response.status_code, 200, response.content)

    def test_service_rejects_blank_reason(self):
        with self.assertRaisesMessage(ValueError, 'Freeze reason is required.'):
            freeze_video_by_id(self.video.pk, ' \n ', actor_id=self.staff.pk)
        self.assert_unchanged()
