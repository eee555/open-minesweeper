from contextlib import contextmanager
from email import policy
from email.parser import BytesParser
from unittest.mock import patch

from django.core import mail
from django.db import transaction
from django.test import override_settings, TestCase
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from accountlink.models import AccountLinkQueue, Platform
from config.text_choices import MS_TextChoices
from identifier.models import Identifier
from identifier.utils import verify_identifier
from media.models import Media
from media.utils import MediaFormat, MediaStatus
from msuser.models import UserMS
from userprofile.models import EmailSentQuota, UserProfile
from userprofile.utils import EmailNotificationType
from videomanager.models import ExpandVideoModel, VideoModel
from .email_notifications.mail import MultilingualNotificationEmail
from .email_notifications.tasks import enqueue_notification, task_send_staff_notification

TASK = 'common.email_notifications.tasks.task_send_staff_notification'


@contextmanager
def mock_enqueue(**kwargs):
    # Task instances are frozen dataclasses; replace the module binding.
    with patch(TASK) as mocked:
        mocked.enqueue.configure_mock(**kwargs)
        yield mocked.enqueue


@override_settings(
    EMAIL_SKIP=False, E2E_TEST=False, RATELIMIT_ENABLE=False,
    EMAIL_DAILY_LIMIT=2000, EMAIL_QUOTA_TIME_ZONE='UTC', EMAIL_WEBSITE_URL='https://example.com',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', DEFAULT_FROM_EMAIL='mail@example.com',
)
class StaffEmailNotificationTests(TestCase):
    def setUp(self):
        self.owner = self.user('mail-owner')
        self.staff = self.user('mail-staff', is_staff=True, email_notification_mask=31)
        for target in ('speedranking.services._sync_video', 'effranking.services._sync_video', 'videomanager.cache.cache'):
            replacement = patch(target)
            replacement.start()
            self.addCleanup(replacement.stop)

    @staticmethod
    def user(username, **kwargs):
        return UserProfile.objects.create_user(username=username, email=f'{username}@example.com', userms=UserMS.objects.create(), **kwargs)

    def video(self, state):
        return VideoModel.objects.create(
            player=self.owner, video=ExpandVideoModel.objects.create(identifier='mail-video'),
            file='notifications/test.evf', state=state, software='e', level='b', bv=4, timems=1000,
        )

    def media(self):
        return Media.objects.create(user=self.owner, format=MediaFormat.B_V, suffix='mail-work', created_at=timezone.now())

    def test_request_enqueues_without_rendering_reserving_or_sending(self):
        self.client.force_login(self.owner)
        with patch('common.email_notifications.tasks.MultilingualNotificationEmail') as message, patch('common.email_notifications.tasks.send_budgeted_email') as send:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post('/api/accountlink/create/', {'platform': Platform.QQ, 'identifier': '123456789'})
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(DBTaskResult.objects.filter(task_path=TASK).count(), 1)
            message.assert_not_called()
            send.assert_not_called()
            self.assertFalse(EmailSentQuota.objects.exists())

    def test_enqueue_failure_does_not_turn_committed_request_into_error(self):
        self.client.force_login(self.owner)
        with mock_enqueue(side_effect=RuntimeError('queue unavailable')), self.assertLogs('django.test', level='ERROR'):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post('/api/accountlink/create/', {'platform': Platform.QQ, 'identifier': '123456789'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(AccountLinkQueue.objects.filter(userprofile=self.owner).exists())

    def test_rollback_discards_notification(self):
        with mock_enqueue() as queued, self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(ValueError), transaction.atomic():
                Identifier.objects.create(identifier='mail-rollback', safe=False)
                raise ValueError('business rollback')
        queued.assert_not_called()
        self.assertFalse(Identifier.objects.filter(identifier='mail-rollback').exists())

    def test_media_and_unsafe_identifier_creation_only(self):
        with mock_enqueue() as queued, self.captureOnCommitCallbacks(execute=True):
            media = self.media()
            identifier = Identifier.objects.create(identifier='mail-unsafe', safe=False)
            identifier.save(update_fields=['safe'])
            media.save(update_fields=['title'])
        self.assertEqual(queued.call_count, 2)
        queued.assert_any_call('staff_media_review', [media.pk])
        queued.assert_any_call('staff_identifier_unsafe', [identifier.pk])

    def test_both_automatic_identifier_entry_points_notify_once(self):
        with mock_enqueue() as queued, patch('identifier.utils.verify_text', return_value=False), patch('identifier.models.verify_text', return_value=False):
            with self.captureOnCommitCallbacks(execute=True):
                self.assertFalse(verify_identifier('mail-first-entry'))
                self.assertFalse(verify_identifier('mail-first-entry'))
                self.assertFalse(Identifier.verify('mail-second-entry', self.owner.userms))
        self.assertEqual(queued.call_count, 2)

    def test_video_creation_and_real_transitions_only(self):
        with mock_enqueue() as queued, self.captureOnCommitCallbacks(execute=True):
            video = self.video(MS_TextChoices.State.PLAIN)
            video.save(update_fields=['version'])
            video.state = MS_TextChoices.State.FROZEN
            video.save(update_fields=['state'])
            video.save(update_fields=['state'])
        self.assertEqual(queued.call_count, 2)
        queued.assert_any_call('staff_video_plain', [video.pk])
        queued.assert_any_call('staff_video_frozen', [video.pk])

    def test_automatic_verified_link_is_not_mailed(self):
        with mock_enqueue() as queued, self.captureOnCommitCallbacks(execute=True):
            AccountLinkQueue.objects.create(userprofile=self.owner, platform=Platform.GITHUB, identifier='123', verified=True)
        queued.assert_not_called()
        with self.captureOnCommitCallbacks(execute=False):
            link = AccountLinkQueue.objects.create(userprofile=self.owner, platform=Platform.QQ, identifier='123')
        link.verified = True
        link.save(update_fields=['verified'])
        with patch('common.email_notifications.tasks.send_budgeted_email') as send:
            self.assertEqual(task_send_staff_notification.call('staff_account_link_review', [link.pk]), 0)
        send.assert_not_called()

    def test_each_of_the_five_types_sends_multilingual_mail(self):
        with self.captureOnCommitCallbacks(execute=False):
            media = self.media()
            frozen = self.video(MS_TextChoices.State.FROZEN)
            plain = self.video(MS_TextChoices.State.PLAIN)
            link = AccountLinkQueue.objects.create(userprofile=self.owner, platform=Platform.QQ, identifier='123')
            identifier = Identifier.objects.create(identifier='mail-unsafe', safe=False)
        for kind, source in zip(EmailNotificationType, (media, frozen, plain, link, identifier), strict=True):
            with self.subTest(kind=kind):
                self.assertEqual(task_send_staff_notification.call(kind.value, [source.pk]), 1)
        self.assertEqual(len(mail.outbox), 5)
        self.assertEqual(EmailSentQuota.objects.get().count, 5)
        self.assertTrue(all(message.to == [self.staff.email] for message in mail.outbox))

    def test_send_time_state_role_and_subscription_are_respected(self):
        with self.captureOnCommitCallbacks(execute=False):
            media = self.media()
        for updates in ({'email_notification_mask': 0}, {'is_staff': False}, {'is_active': False}):
            with self.subTest(updates=updates):
                UserProfile.objects.filter(pk=self.staff.pk).update(**updates)
                self.assertEqual(task_send_staff_notification.call('staff_media_review', [media.pk]), 0)
                UserProfile.objects.filter(pk=self.staff.pk).update(email_notification_mask=31, is_staff=True, is_active=True)
        Media.objects.filter(pk=media.pk).update(status=MediaStatus.VERIFIED)
        self.assertEqual(task_send_staff_notification.call('staff_media_review', [media.pk]), 0)
        self.assertFalse(EmailSentQuota.objects.exists())

    def test_nonstaff_subscription_saved_by_api_does_not_receive_staff_mail(self):
        self.client.force_login(self.owner)
        response = self.client.patch('/api/userprofile/email-notifications', {
            'changes': [{'type': 'staff_media_review', 'enabled': True}],
        }, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['email_notification_mask'], 1)
        with self.captureOnCommitCallbacks(execute=False):
            media = self.media()
        self.assertEqual(task_send_staff_notification.call('staff_media_review', [media.pk]), 1)
        self.assertEqual([message.to for message in mail.outbox], [[self.staff.email]])

    def test_one_recipient_failure_does_not_block_the_next(self):
        second = self.user('mail-second-staff', is_staff=True, email_notification_mask=31)
        with self.captureOnCommitCallbacks(execute=False):
            media = self.media()
        with patch('common.email_notifications.tasks.send_budgeted_email', side_effect=[TimeoutError, 1]) as send, self.assertLogs('common.email_notifications.tasks', level='ERROR'):
            self.assertEqual(task_send_staff_notification.call('staff_media_review', [media.pk]), 1)
        self.assertEqual(send.call_count, 2)
        self.assertEqual(send.call_args.args[0].to, [second.email])

    def test_email_skip_does_not_enqueue_or_send(self):
        with override_settings(EMAIL_SKIP=True), mock_enqueue() as queued:
            enqueue_notification(EmailNotificationType.STAFF_MEDIA_REVIEW, 1)
            self.assertEqual(task_send_staff_notification.call('staff_media_review', [1]), 0)
        queued.assert_not_called()

    def test_mime_structure_and_language_headers_survive_serialization(self):
        message = MultilingualNotificationEmail(EmailNotificationType.STAFF_MEDIA_REVIEW, [42], '/staff/media', self.staff)
        parsed = BytesParser(policy=policy.default).parsebytes(message.message(policy=policy.SMTP).as_bytes())
        self.assertEqual(parsed.get_content_type(), 'multipart/multilingual')
        parts = list(parsed.iter_parts())
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0].get_content_type(), 'text/plain')
        self.assertIsNone(parts[0]['Content-Language'])
        self.assertIn('中文', parts[0].get_content())
        self.assertIn('español', parts[0].get_content().lower())
        for part, language in zip(parts[1:], ('zh-CN', 'en', 'es'), strict=True):
            self.assertEqual(part.get_content_type(), 'message/rfc822')
            self.assertEqual(part['Content-Language'], language)
            content = part.get_payload(0)
            self.assertEqual(content['From'], parsed['From'])
            self.assertTrue(content['Subject'])
            self.assertEqual(content.get_content_type(), 'multipart/alternative')
            self.assertEqual([body.get_content_type() for body in content.iter_parts()], ['text/plain', 'text/html'])
            self.assertIn(f'/#/player/{self.staff.pk}/settings', content.get_body(preferencelist=('html',)).get_content())
