"""玩家认证与统一准入的后端回归测试。

后台任务在测试中直接以任务参数执行业务入口，模拟 worker 完成一次完整提交；
并发行锁行为另需 MySQL TransactionTestCase 验证。
"""

from datetime import timedelta
from types import SimpleNamespace

from django.tasks import TaskResultStatus
from django.test import override_settings, TestCase
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from msuser.models import UserMS
from .models import UserProfile, UserVerifyTree
from .tasks import task_apply_verification
from .utils import has_identity_access
from .verification.utils import VERIFICATION_TASK_PATH


@override_settings(RATELIMIT_ENABLE=False)
class VerificationTests(TestCase):
    def setUp(self):
        self.alice = self.create_user('alice')
        self.bob = self.create_user('bob')
        self.cara = self.create_user('cara')
        self.dave = self.create_user('dave')
        self.staff = self.create_user('staff', is_staff=True)
        self.superuser = self.create_user('root', is_superuser=True)

    @staticmethod
    def create_user(username, **extra):
        return UserProfile.objects.create_user(
            username=username, email=f'{username}@example.com', password='password',
            userms=UserMS.objects.create(), **extra,
        )

    def login(self, user):
        self.client.force_login(user)

    def status(self, user=None):
        if user is not None:
            self.login(user)
        response = self.client.get('/api/userprofile/verification/request')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def post(self, path, data=None, expected=202):
        response = self.client.post(path, data or {})
        self.assertEqual(response.status_code, expected, response.content)
        return response.json() if response.content else None

    def submit_task(self, path, data=None):
        body = self.post(path, data)
        self.assertIn('task_id', body)
        self.assertEqual(DBTaskResult.objects.filter(pk=body['task_id'], task_path=VERIFICATION_TASK_PATH).count(), 1)
        return body['task_id']

    def run_task(self, task_id):
        row = DBTaskResult.objects.get(pk=task_id)
        kwargs = dict(row.args_kwargs['kwargs'])
        context = SimpleNamespace(task_result=SimpleNamespace(id=str(row.id)))
        result = task_apply_verification.func(context, **kwargs)
        row.status = TaskResultStatus.SUCCESSFUL
        row.return_value = result
        row.save(update_fields=['status', 'return_value'])
        return result

    def age_request(self, user, hours):
        UserVerifyTree.objects.filter(user_id=user.pk).update(created_at=timezone.now() - timedelta(hours=hours))

    def grant(self, actor, target):
        self.login(actor)
        return self.run_task(self.submit_task('/api/userprofile/admin/verification/grant', {'user_id': target.pk}))

    def request_from(self, applicant, parent):
        self.login(applicant)
        return self.post('/api/userprofile/verification/requests', {'user_id': parent.pk}, expected=200)

    def approve(self, actor, applicant):
        self.login(actor)
        return self.run_task(self.submit_task(f'/api/userprofile/verification/requests/{applicant.pk}/approve'))

    def verified(self, *users):
        return [UserProfile.objects.get(pk=user.pk).verified for user in users]

    def test_identity_access_predicate(self):
        self.assertFalse(has_identity_access(self.alice))
        self.alice.verified = True
        self.assertTrue(has_identity_access(self.alice))
        self.alice.verified = False
        self.alice.realname = 'Alice'
        self.assertTrue(has_identity_access(self.alice))
        self.alice.can_hide_realname = True
        self.alice.hide_realname = True
        self.assertTrue(has_identity_access(self.alice))
        self.assertFalse(has_identity_access(self.staff))
        self.assertFalse(has_identity_access(self.superuser))

    def test_defaults_and_management_roles_do_not_grant_verification(self):
        state = self.status(self.alice)
        self.assertFalse(state['verified'])
        self.assertFalse(state['can_submit_replays'])
        self.assertEqual(state['request_state'], 'none')
        self.assertTrue(state['can_request'])
        self.assertFalse(UserProfile.objects.get(pk=self.staff.pk).verified)
        self.assertFalse(UserProfile.objects.get(pk=self.superuser.pk).verified)

    def test_self_request_and_cycle_are_rejected(self):
        self.login(self.alice)
        response = self.client.post('/api/userprofile/verification/requests', {'user_id': self.alice.pk})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['category'], 'self_request')

    def test_request_cooldown_reject_and_lazy_expiry_replacement(self):
        state = self.request_from(self.alice, self.bob)
        self.assertEqual(state['request_state'], 'pending')
        self.assertEqual(state['request_parent_id'], self.bob.pk)
        self.assertFalse(state['can_request'])
        self.login(self.alice)
        response = self.client.post('/api/userprofile/verification/requests', {'user_id': self.cara.pk})
        self.assertEqual(response.json()['category'], 'cooldown')

        self.login(self.bob)
        self.post(f'/api/userprofile/verification/requests/{self.alice.pk}/reject', expected=204)
        state = self.status(self.alice)
        self.assertEqual(state['request_state'], 'rejected')
        self.assertFalse(state['request_parent_id'])
        self.assertFalse(state['can_request'])
        self.assertIsNotNone(state['cooldown_until'])

        self.login(self.bob)
        self.assertEqual(self.client.post(f'/api/userprofile/verification/requests/{self.alice.pk}/approve').json()['category'], 'not_found')

        self.age_request(self.alice, 169)
        state = self.request_from(self.alice, self.cara)
        self.assertEqual(state['request_parent_id'], self.cara.pk)
        self.assertEqual(UserVerifyTree.objects.filter(user_id=self.alice.pk).count(), 1)
        self.assertFalse(UserVerifyTree.objects.get(user_id=self.alice.pk).verified)

    def test_exact_expiry_rejects_approval(self):
        self.request_from(self.alice, self.bob)
        self.age_request(self.alice, 168)
        self.login(self.bob)
        response = self.client.post(f'/api/userprofile/verification/requests/{self.alice.pk}/approve')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['category'], 'expired')

    def test_approval_only_by_named_recipient_and_not_applied_before_task(self):
        self.request_from(self.alice, self.bob)
        self.login(self.cara)
        self.assertEqual(self.client.post(f'/api/userprofile/verification/requests/{self.alice.pk}/approve').json()['category'], 'not_found')
        self.login(self.bob)
        task_id = self.submit_task(f'/api/userprofile/verification/requests/{self.alice.pk}/approve')
        self.assertFalse(UserVerifyTree.objects.get(user_id=self.alice.pk).verified)
        self.assertEqual(self.verified(self.alice), [False])
        result = self.run_task(task_id)
        self.assertEqual(result['status'], 'applied')
        self.assertTrue(UserVerifyTree.objects.get(user_id=self.alice.pk).verified)
        # 未认证的收件人批准后，关系成立但申请人仍未认证。
        self.assertEqual(self.verified(self.alice, self.bob), [False, False])

    def test_unverified_approver_propagates_when_later_verified(self):
        self.request_from(self.bob, self.dave)
        self.login(self.dave)
        self.run_task(self.submit_task(f'/api/userprofile/verification/requests/{self.bob.pk}/approve'))
        self.assertTrue(UserVerifyTree.objects.get(user_id=self.bob.pk).verified)
        self.assertEqual(self.verified(self.bob, self.dave), [False, False])
        self.grant(self.staff, self.dave)
        self.assertEqual(self.verified(self.bob, self.dave), [True, True])

    def test_grant_makes_root_and_revoke_cascades_only_effective_descendants(self):
        self.grant(self.staff, self.alice)
        self.request_from(self.bob, self.alice)
        self.approve(self.alice, self.bob)
        self.request_from(self.cara, self.bob)
        self.approve(self.bob, self.cara)
        self.assertEqual(self.verified(self.alice, self.bob, self.cara), [True, True, True])

        self.login(self.superuser)
        self.run_task(self.submit_task('/api/userprofile/admin/verification/revoke', {'user_id': self.alice.pk}))
        self.assertEqual(self.verified(self.alice, self.bob, self.cara), [False, False, False])
        # 后代内部已批准的边保留。
        self.assertTrue(UserVerifyTree.objects.get(user_id=self.cara.pk).verified)
        self.assertEqual(UserVerifyTree.objects.get(user_id=self.cara.pk).parent_id, self.bob.pk)

        self.grant(self.staff, self.bob)
        self.assertEqual(self.verified(self.alice, self.bob, self.cara), [False, True, True])
        self.assertIsNone(UserVerifyTree.objects.get(user_id=self.bob.pk).parent_id)

    def test_detach_keeps_descendant_edges_and_cascades(self):
        self.grant(self.staff, self.alice)
        self.request_from(self.bob, self.alice)
        self.approve(self.alice, self.bob)
        self.request_from(self.cara, self.bob)
        self.approve(self.bob, self.cara)
        self.login(self.bob)
        self.run_task(self.submit_task('/api/userprofile/verification/detach'))
        self.assertEqual(self.verified(self.alice, self.bob, self.cara), [True, False, False])
        self.assertTrue(UserVerifyTree.objects.get(user_id=self.cara.pk).verified)
        self.assertIsNone(UserVerifyTree.objects.get(user_id=self.bob.pk).parent_id)

    def test_pending_request_cannot_be_detached_and_cycle_is_blocked(self):
        self.request_from(self.alice, self.bob)
        self.login(self.alice)
        self.assertEqual(self.client.post('/api/userprofile/verification/detach').json()['category'], 'no_relation')

    def test_revoke_requires_superuser_and_grant_allows_both_roles(self):
        self.login(self.staff)
        self.assertIn(self.client.post('/api/userprofile/admin/verification/revoke', {'user_id': self.alice.pk}).status_code, (401, 403))
        self.login(self.alice)
        self.assertIn(self.client.post('/api/userprofile/admin/verification/revoke', {'user_id': self.alice.pk}).status_code, (401, 403))
        self.assertEqual(self.client.post('/api/userprofile/admin/verification/grant', {'user_id': self.alice.pk}).status_code, 403)
        self.grant(self.staff, self.staff)
        self.grant(self.superuser, self.superuser)
        self.assertEqual(self.verified(self.staff, self.superuser), [True, True])

    def test_task_result_only_visible_to_submitter(self):
        self.request_from(self.alice, self.bob)
        self.login(self.bob)
        task_id = self.submit_task(f'/api/userprofile/verification/requests/{self.alice.pk}/approve')
        response = self.client.get(f'/api/userprofile/verification/tasks/{task_id}')
        self.assertEqual(response.json()['status'], 'READY')
        self.assertIsNone(response.json()['result'])
        self.login(self.alice)
        self.assertEqual(self.client.get(f'/api/userprofile/verification/tasks/{task_id}').status_code, 404)

    def test_duplicate_submission_returns_existing_task_and_conflicting_op_is_processing(self):
        self.request_from(self.alice, self.bob)
        self.login(self.bob)
        first = self.post(f'/api/userprofile/verification/requests/{self.alice.pk}/approve')
        second = self.post(f'/api/userprofile/verification/requests/{self.alice.pk}/approve')
        self.assertEqual(first['task_id'], second['task_id'])
        self.assertTrue(second['existing'])
        self.login(self.superuser)
        response = self.client.post('/api/userprofile/admin/verification/revoke', {'user_id': self.alice.pk})
        self.assertEqual(response.json()['category'], 'processing')

    def test_identity_access_errors_and_player_verification_allows_registration(self):
        self.login(self.alice)
        response = self.client.post('/api/tournament/gsc/participant', {'order': 999})
        # 赛事不存在时仍先按统一准入拒绝。
        self.assertEqual(response.json(), {'type': 'error', 'object': 'userprofile', 'category': 'identity_access_required'})
        self.alice.verified = True
        self.alice.save(update_fields=['verified', 'date_updated'])
        response = self.client.post('/api/tournament/gsc/participant', {'order': 999})
        self.assertEqual(response.status_code, 404)
