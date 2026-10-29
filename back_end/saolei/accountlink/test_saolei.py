from unittest.mock import patch

from django.tasks import TaskResultStatus
from django.test import override_settings, SimpleTestCase, TestCase
from django.urls import resolve, Resolver404
from django_tasks_db.models import DBTaskResult

from msuser.models import UserMS
from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from .models import AccountLinkQueue, AccountSaolei, Platform
from .tasks import task_saolei_profile, task_saolei_video_import, task_saolei_video_import_bulk


class SaoleiCrawlingDisabledTests(SimpleTestCase):
    def test_old_crawling_urls_are_removed_with_or_without_trailing_slashes(self):
        for path in ['/accountlink/saolei_import_video', '/accountlink/saolei_import_videos']:
            for suffix in ['', '/']:
                with self.subTest(path=path + suffix), self.assertRaises(Resolver404):
                    resolve(path + suffix)

    @patch('requests.sessions.Session.request', side_effect=AssertionError('Unexpected external request'))
    def test_queued_legacy_tasks_fail_without_network_or_database_access(self, remote):
        for task, args in [
            (task_saolei_profile, [1]),
            (task_saolei_video_import, [1]),
            (task_saolei_video_import_bulk, [1, 'all']),
        ]:
            with self.subTest(task=task.func.__name__), self.assertRaises(ExceptionToResponse) as caught:
                task.call(*args)
            self.assertEqual(caught.exception.status_code, 410)
            self.assertEqual(caught.exception.category, 'crawling_disabled')
        remote.assert_not_called()


@override_settings(RATELIMIT_ENABLE=False)
@patch('requests.sessions.Session.request', side_effect=AssertionError('Unexpected external request'))
class SaoleiBusinessTests(TestCase):
    def setUp(self):
        self.user = UserProfile.objects.create_user(username='saolei_business', email='saolei_business@example.com', userms=UserMS.objects.create())
        self.staff = UserProfile.objects.create_user(username='saolei_staff', email='saolei_staff@example.com', is_staff=True)

    def test_account_creation_verification_and_public_details_remain_available(self, remote):
        self.client.force_login(self.user)
        response = self.client.post('/api/accountlink/create/', {'platform': Platform.SAOLEI, 'identifier': '101'})
        self.assertEqual(response.status_code, 200, response.content)
        self.client.force_login(self.staff)
        with patch('accountlink.api.update_account') as update:
            response = self.client.post('/api/accountlink/verify/', {'id': self.user.pk, 'platform': Platform.SAOLEI, 'identifier': '101'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(AccountLinkQueue.objects.get(userprofile=self.user).verified)
        self.assertEqual(AccountSaolei.objects.get(pk=101).parent_id, self.user.pk)
        update.assert_not_called()
        self.client.logout()
        self.assertEqual(self.client.get(f'/api/accountlink/{self.user.pk}').json()['c']['id'], 101)
        remote.assert_not_called()

    def test_profile_refresh_is_rejected_without_changing_saved_data(self, remote):
        account = AccountSaolei.objects.create(pk=101, parent=self.user, name='Saved name')
        self.client.force_login(self.user)
        response = self.client.post('/accountlink/update/', {'platform': Platform.SAOLEI})
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.json()['category'], 'crawling_disabled')
        account.refresh_from_db()
        self.assertEqual(account.name, 'Saved name')
        remote.assert_not_called()

    def test_legacy_crawling_tasks_cannot_be_restarted(self, remote):
        self.client.force_login(self.staff)
        for task in [task_saolei_profile, task_saolei_video_import, task_saolei_video_import_bulk]:
            old_task = DBTaskResult.objects.create(
                task_path=task.module_path, status=TaskResultStatus.FAILED,
                args_kwargs={'args': [1], 'kwargs': {}}, queue_name='default', backend_name='default',
            )
            count = DBTaskResult.objects.count()
            response = self.client.post('/api/common/tasks/restart', {'task_id': str(old_task.pk)})
            self.assertEqual(response.status_code, 410, response.content)
            self.assertEqual(response.json()['category'], 'crawling_disabled')
            self.assertEqual(DBTaskResult.objects.count(), count)
        remote.assert_not_called()
