from unittest.mock import Mock, patch

from django.test import override_settings, TestCase
from requests.exceptions import Timeout

from msuser.models import UserMS
from .models import EmailVerifyRecord, UserProfile
from .services import register_user


@override_settings(RATELIMIT_ENABLE=False, BAIDU_VERIFY_SKIP=False, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class UserRegistrationTests(TestCase):
    def setUp(self):
        self.code = EmailVerifyRecord.objects.create(email='register@example.com', code='123456', hashkey='registration-email-key')
        self.payload = {
            'username': 'approved_user', 'password': 'safe-password', 'email': self.code.email,
            'email_key': self.code.hashkey, 'email_captcha': self.code.code,
        }

    def submit(self):
        return self.client.post('/api/userprofile/register', self.payload, REMOTE_ADDR='203.0.113.7')

    def assert_rejected(self, response, obj, category):
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {'type': 'error', 'object': obj, 'category': category})
        self.assertFalse(UserProfile.objects.filter(email=self.code.email).exists())
        self.assertFalse(UserMS.objects.exists())
        self.assertTrue(EmailVerifyRecord.objects.filter(pk=self.code.pk).exists())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_approved_cleaned_username_is_checked_before_creating_and_logging_in(self):
        self.payload['username'] = ' approved_user '

        def approve(username, user_id, user_ip):
            self.assertEqual((username, user_id, user_ip), ('approved_user', 0, '203.0.113.7'))
            self.assertFalse(UserProfile.objects.exists())
            self.assertFalse(UserMS.objects.exists())
            return True

        with patch('userprofile.services.verify_text', side_effect=approve) as verify:
            response = self.submit()
        verify.assert_called_once()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['type'], 'success')
        user = UserProfile.objects.get(username='approved_user')
        self.assertTrue(user.check_password(self.payload['password']))
        self.assertTrue(user.is_active)
        self.assertIsNotNone(user.userms_id)
        self.assertEqual(UserMS.objects.count(), 1)
        self.assertEqual(response.json()['user']['id'], user.pk)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.assertFalse(EmailVerifyRecord.objects.filter(pk=self.code.pk).exists())

    def test_rejected_username_does_not_create_an_account_or_consume_the_email_code(self):
        with patch('userprofile.services.verify_text', return_value=False) as verify:
            response = self.submit()
        verify.assert_called_once_with('approved_user', 0, '203.0.113.7')
        self.assert_rejected(response, 'censorship', 'illegal')

    def test_moderation_uses_the_username_after_model_normalization(self):
        self.payload['username'] = 'Ａ'
        with patch('userprofile.services.verify_text', return_value=False) as verify:
            response = self.submit()
        verify.assert_called_once_with('A', 0, '203.0.113.7')
        self.assert_rejected(response, 'censorship', 'illegal')

    def test_moderation_failure_allows_a_retry_with_the_same_email_code(self):
        with patch('userprofile.services.verify_text', side_effect=Timeout('moderation timed out')):
            response = self.submit()
        self.assert_rejected(response, 'censorship', 'unknown')
        with patch('userprofile.services.verify_text', return_value=True):
            response = self.submit()
        self.assertEqual(response.json()['type'], 'success')
        self.assertEqual(UserProfile.objects.count(), 1)

    def test_single_character_username_is_sent_to_baidu(self):
        self.payload['username'] = '雷'
        result = Mock()
        result.json.return_value = {'conclusion': '不合规'}
        with patch('utils.get_ACCESS_TOKEN', return_value='test-token'), patch('utils.requests.request', return_value=result) as request:
            response = self.submit()
        self.assert_rejected(response, 'censorship', 'illegal')
        request.assert_called_once()
        self.assertEqual(request.call_args.kwargs['data'], {'text': '雷', 'userId': '0', 'userIp': '203.0.113.7'})
        self.assertEqual(request.call_args.kwargs['timeout'], 5)

    def test_invalid_form_does_not_call_moderation(self):
        for username in ('', 'ㅤ'):
            with self.subTest(username=username), patch('userprofile.services.verify_text') as verify:
                self.payload['username'] = username
                self.assert_rejected(self.submit(), 'register', 'validation')
                verify.assert_not_called()

    def test_duplicate_username_does_not_call_moderation(self):
        UserProfile.objects.create_user(username=self.payload['username'], email='existing@example.com', password='password')
        with patch('userprofile.services.verify_text') as verify:
            self.assert_rejected(self.submit(), 'register', 'validation')
        verify.assert_not_called()

    def test_invalid_email_code_does_not_call_moderation(self):
        self.payload['email_captcha'] = 'wrong'
        with patch('userprofile.services.verify_text') as verify:
            self.assert_rejected(self.submit(), 'emailcode', 'invalid')
        verify.assert_not_called()

    def test_username_collision_check_does_not_call_moderation(self):
        with patch('userprofile.services.verify_text') as verify:
            response = self.client.get('/userprofile/checkcollision/', {'username': self.payload['username']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'False')
        verify.assert_not_called()

    def test_failed_account_write_rolls_back_userms_and_preserves_email_code(self):
        with patch('userprofile.services.verify_text', return_value=True), patch.object(UserProfile, 'save', side_effect=RuntimeError('write failed')):
            with self.assertRaisesMessage(RuntimeError, 'write failed'):
                register_user(self.payload, '203.0.113.7')
        self.assertFalse(UserProfile.objects.exists())
        self.assertFalse(UserMS.objects.exists())
        self.assertTrue(EmailVerifyRecord.objects.filter(pk=self.code.pk).exists())

    def test_legacy_registration_url_is_removed(self):
        self.assertEqual(self.client.post('/userprofile/register/', self.payload).status_code, 404)

    def test_registration_requires_post_and_a_complete_form(self):
        with patch('userprofile.services.verify_text') as verify:
            self.assertEqual(self.client.get('/api/userprofile/register').status_code, 405)
            self.assertEqual(self.client.post('/api/userprofile/register', {}).status_code, 422)
        verify.assert_not_called()
