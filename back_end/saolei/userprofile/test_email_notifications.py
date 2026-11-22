from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as dt_timezone
from threading import Barrier
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.db import close_old_connections, connection, IntegrityError, transaction
from django.test import override_settings, TestCase, TransactionTestCase
from django.utils import timezone

from msuser.models import UserMS
from .mail import reserve_email_quota, send_budgeted_email
from .models import EmailSentQuota, UserProfile
from .services import send_email, user_metadata

URL = '/api/userprofile/email-notifications'
MAIL_SETTINGS = {
    'EMAIL_SKIP': False, 'E2E_TEST': False, 'EMAIL_DAILY_LIMIT': 2000, 'EMAIL_QUOTA_TIME_ZONE': 'UTC',
    'EMAIL_BACKEND': 'django.core.mail.backends.locmem.EmailBackend', 'DEFAULT_FROM_EMAIL': 'mail@example.com',
}


@override_settings(RATELIMIT_ENABLE=False)
class EmailNotificationSettingsTests(TestCase):
    def setUp(self):
        self.user = UserProfile.objects.create_user(
            username='mail-settings', email='mail-settings@example.com', is_staff=True, userms=UserMS.objects.create(),
        )
        self.client.force_login(self.user)

    def update(self, changes):
        return self.client.patch(URL, {'changes': changes}, content_type='application/json')

    def test_merges_changes_preserving_high_bit_and_returns_number(self):
        UserProfile.objects.filter(pk=self.user.pk).update(email_notification_mask=(1 << 31) | 2)
        response = self.update([{'type': 'staff_video_plain', 'enabled': True}])
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {'email_notification_mask': (1 << 31) | 6})
        self.user.refresh_from_db()
        self.assertEqual(self.user.email_notification_mask, (1 << 31) | 6)

    def test_uint32_round_trip_and_validation(self):
        for mask in (0, 1 << 31, (1 << 32) - 1):
            self.user.email_notification_mask = mask
            self.user.save(update_fields=['email_notification_mask'])
            self.user.refresh_from_db()
            self.assertEqual(self.user.email_notification_mask, mask)
        self.user.email_notification_mask = 1 << 32
        with self.assertRaises(ValidationError):
            self.user.full_clean()

    def test_login_and_self_responses_contain_private_preference(self):
        self.user.email_notification_mask = 31
        self.user.save(update_fields=['email_notification_mask'])
        self.assertEqual(user_metadata(self.user, self.user)['email_notification_mask'], 31)
        with patch('common.api.TopRankingCache') as rankings:
            rankings.return_value.get_anchors.return_value = {}
            response = self.client.get('/api/common/loginauto')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['user']['email_notification_mask'], 31)
        self.assertEqual(self.client.get('/api/userprofile/info/0').json()['email_notification_mask'], 31)
        self.assertNotIn('email_notification_mask', self.client.get(f'/api/userprofile/info/{self.user.pk}').json())
        self.assertNotIn('email_notification_mask', user_metadata(self.user, object()))

    def test_password_login_includes_preference(self):
        self.user.set_password('password123')
        self.user.email_notification_mask = 7
        self.user.save(update_fields=['password', 'email_notification_mask'])
        self.client.logout()
        with patch('userprofile.views.judge_captcha', return_value=True):
            response = self.client.post('/userprofile/login/', {
                'username': self.user.username, 'password': 'password123', 'captcha': 'test',
                'hashkey': 'mail-settings-captcha', 'set_expiry': 7,
            })
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['user']['email_notification_mask'], 7)

    def test_no_separate_get_endpoint_and_anonymous_cannot_save(self):
        self.assertEqual(self.client.get(URL).status_code, 405)
        self.client.logout()
        self.assertEqual(self.update([{'type': 'staff_video_plain', 'enabled': True}]).status_code, 403)

    def test_rejects_unknown_duplicate_and_non_boolean_changes(self):
        for changes in (
            [{'type': 'unknown', 'enabled': True}],
            [{'type': 'staff_video_plain', 'enabled': 1}],
            [{'type': 'staff_video_plain', 'enabled': True}] * 2,
        ):
            with self.subTest(changes=changes):
                self.assertEqual(self.update(changes).status_code, 422)

    def test_nonstaff_can_store_and_clear_staff_preferences(self):
        self.user.is_staff = False
        self.user.email_notification_mask = 0
        self.user.save(update_fields=['is_staff', 'email_notification_mask'])
        response = self.update([{'type': 'staff_video_plain', 'enabled': True}])
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['email_notification_mask'], 4)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email_notification_mask, 4)
        self.assertEqual(self.update([{'type': 'staff_video_plain', 'enabled': False}]).json()['email_notification_mask'], 0)

    def test_placeholder_address_cannot_subscribe(self):
        self.user.email = 'mail-settings@accounts.invalid'
        self.user.save(update_fields=['email'])
        self.assertEqual(self.update([{'type': 'staff_video_plain', 'enabled': True}]).status_code, 409)


@override_settings(**MAIL_SETTINGS)
class EmailQuotaTests(TestCase):
    def test_limit_and_day_rollover_reuse_one_row(self):
        yesterday = timezone.now().date() - timedelta(days=1)
        EmailSentQuota.objects.create(pk=1, quota_date=yesterday, count=2000)
        self.assertTrue(reserve_email_quota())
        quota = EmailSentQuota.objects.get()
        self.assertEqual(quota.quota_date, timezone.now().date())
        self.assertEqual(quota.count, 1)
        quota.count = 2000
        quota.save(update_fields=['count'])
        self.assertFalse(reserve_email_quota())
        self.assertEqual(EmailSentQuota.objects.count(), 1)

    @override_settings(EMAIL_QUOTA_TIME_ZONE='Asia/Shanghai')
    def test_provider_date_and_clock_rollback(self):
        now = datetime(2026, 11, 22, 17, tzinfo=dt_timezone.utc)
        with patch('userprofile.mail.timezone.now', return_value=now):
            self.assertTrue(reserve_email_quota())
        quota = EmailSentQuota.objects.get()
        self.assertEqual(str(quota.quota_date), '2026-11-23')
        with patch('userprofile.mail.timezone.now', return_value=now - timedelta(days=1)):
            self.assertFalse(reserve_email_quota())
        quota.refresh_from_db()
        self.assertEqual(quota.count, 1)

    def test_failure_keeps_reservation(self):
        message = EmailMessage('test', 'body', to=['recipient@example.com'])
        with patch.object(message, 'send', side_effect=TimeoutError), self.assertRaises(TimeoutError):
            send_budgeted_email(message)
        self.assertEqual(EmailSentQuota.objects.get().count, 1)

    @override_settings(EMAIL_QUOTA_TIME_ZONE='Asia/Shanghai')
    def test_utc_plus_eight_resets_at_1600_utc(self):
        before = datetime(2026, 11, 22, 15, 59, 59, tzinfo=dt_timezone.utc)
        with patch('userprofile.mail.timezone.now', return_value=before):
            self.assertTrue(reserve_email_quota())
        with patch('userprofile.mail.timezone.now', return_value=before + timedelta(seconds=1)):
            self.assertTrue(reserve_email_quota())
        quota = EmailSentQuota.objects.get()
        self.assertEqual(str(quota.quota_date), '2026-11-23')
        self.assertEqual(quota.count, 1)
        self.assertEqual(EmailSentQuota.objects.count(), 1)

    def test_refuses_reservation_inside_business_atomic(self):
        with transaction.atomic(), self.assertRaises(RuntimeError):
            reserve_email_quota()

    def test_quota_is_a_singleton(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            EmailSentQuota.objects.create(pk=2, quota_date=timezone.now().date())

    def test_all_verification_mail_shares_counter(self):
        self.assertIsNotNone(send_email('register@example.com', 'register'))
        self.assertIsNotNone(send_email('retrieve@example.com', 'retrieve'))
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(EmailSentQuota.objects.get().count, 2)

    def test_skip_modes_and_placeholder_do_not_consume_quota(self):
        for overrides in ({'EMAIL_SKIP': True}, {'E2E_TEST': True}):
            with self.subTest(overrides=overrides), override_settings(**overrides):
                self.assertEqual(send_budgeted_email(EmailMessage('test', 'body', to=['mail@example.com'])), 0)
        self.assertEqual(send_budgeted_email(EmailMessage('test', 'body', to=['mail@accounts.invalid'])), 0)
        self.assertFalse(EmailSentQuota.objects.exists())


@override_settings(**MAIL_SETTINGS)
class EmailQuotaConcurrencyTests(TransactionTestCase):
    def concurrently_reserve(self, workers):
        barrier = Barrier(workers)

        def reserve():
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                return reserve_email_quota()
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(lambda _: reserve(), range(workers)))

    def test_competing_senders_cannot_exceed_daily_limit(self):
        EmailSentQuota.objects.create(pk=1, quota_date=timezone.now().date(), count=1999)
        self.assertEqual(sum(self.concurrently_reserve(4)), 1)
        self.assertEqual(EmailSentQuota.objects.get().count, 2000)

    def test_concurrent_initialization_still_has_one_record(self):
        self.assertEqual(sum(self.concurrently_reserve(4)), 4)
        self.assertEqual(EmailSentQuota.objects.count(), 1)
        self.assertEqual(EmailSentQuota.objects.get().count, 4)

    def test_concurrent_rollover_only_resets_once(self):
        EmailSentQuota.objects.create(pk=1, quota_date=timezone.now().date() - timedelta(days=1), count=2000)
        self.assertEqual(sum(self.concurrently_reserve(4)), 4)
        quota = EmailSentQuota.objects.get()
        self.assertEqual(quota.count, 4)
        self.assertEqual(quota.quota_date, timezone.now().date())
