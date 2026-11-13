"""玩家认证有向图、独占维护会话与统一准入的后端回归测试。

所有图写入均为请求内的同步事务；测试直接断言请求完成后的数据库状态。
"""

from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings, TestCase
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from msuser.models import UserMS
from .models import UserProfile, UserVerifyEdge
from .utils import has_identity_access
from .verification.cache import read_maintenance
from .verification.utils import MAINTENANCE_KEY

TEST_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'verification-default'},
    'saolei_website': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'verification-sessions'},
}

STATUS_URL = '/api/userprofile/verification/status'
VERIFY_URL = '/api/userprofile/verification/verify'
SET_VERIFIED_URL = '/api/userprofile/admin/verification/set-verified'
GRAPH_URL = '/api/userprofile/admin/verification/graph'
MAINTENANCE_URL = '/api/userprofile/admin/verification/maintenance'
GRAPH_UPDATE_URL = '/api/userprofile/admin/verification/graph-update'


@override_settings(RATELIMIT_ENABLE=False, CACHES=TEST_CACHES)
class VerificationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
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

    def get_json(self, path, expected=200):
        response = self.client.get(path)
        self.assertEqual(response.status_code, expected, response.content)
        return response.json() if response.content else None

    def post_json(self, path, data=None, expected=200):
        response = self.client.post(path, data or {}, content_type='application/json')
        self.assertEqual(response.status_code, expected, response.content)
        return response.json() if response.content else None

    def set_verified(self, user, value):
        UserProfile.objects.filter(pk=user.pk).update(verified=value, date_updated=timezone.now())

    def verified(self, *users):
        return [UserProfile.objects.get(pk=user.pk).verified for user in users]

    def status(self, user=None):
        if user is not None:
            self.login(user)
        return self.get_json(STATUS_URL)

    def verify(self, actor, target, expected=200):
        self.login(actor)
        return self.post_json(VERIFY_URL, {'user_id': target.pk}, expected=expected)

    def start_maintenance(self, user=None, seconds=60, expected=200):
        self.login(user or self.superuser)
        return self.post_json(MAINTENANCE_URL, {'duration_seconds': seconds}, expected=expected)

    def edge(self, from_user, to_user):
        return {'from_user_id': from_user.pk, 'to_user_id': to_user.pk}

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
        self.assertEqual(self.status(self.alice), {
            'verified': False, 'can_submit_replays': False, 'can_verify': False, 'maintenance_active': False,
        })
        self.assertFalse(UserProfile.objects.get(pk=self.staff.pk).verified)
        self.assertFalse(UserProfile.objects.get(pk=self.superuser.pk).verified)
        self.assertFalse(UserVerifyEdge.objects.exists())

    def test_unverified_user_cannot_verify_and_self_verification_is_rejected(self):
        body = self.verify(self.alice, self.bob, expected=403)
        self.assertEqual(body['category'], 'not_verified')
        self.set_verified(self.alice, True)
        body = self.verify(self.alice, self.alice, expected=400)
        self.assertEqual(body['category'], 'self_verify')
        self.assertFalse(UserVerifyEdge.objects.exists())

    def test_verification_needs_no_request_and_only_touches_current_edge_and_target(self):
        self.set_verified(self.alice, True)
        UserVerifyEdge.objects.create(from_user=self.alice, to_user=self.bob)
        UserVerifyEdge.objects.create(from_user=self.bob, to_user=self.cara)
        self.set_verified(self.bob, True)
        self.set_verified(self.cara, True)
        result = self.verify(self.alice, self.dave)
        self.assertTrue(result['edge_created'])
        self.assertTrue(result['verified'])
        self.assertEqual(result['target_id'], self.dave.pk)
        self.assertEqual(UserVerifyEdge.objects.count(), 3)
        self.assertEqual(self.verified(self.bob, self.cara, self.dave), [True, True, True])
        self.assertEqual(DBTaskResult.objects.filter(task_path__contains='verification').count(), 0)

    def test_multiple_in_edges_reverse_edges_and_cycles_are_allowed(self):
        for user in (self.alice, self.bob, self.cara):
            self.set_verified(user, True)
        self.verify(self.alice, self.bob)
        self.verify(self.alice, self.cara)
        self.verify(self.bob, self.alice)
        self.verify(self.bob, self.cara)
        self.verify(self.cara, self.alice)
        self.assertEqual(UserVerifyEdge.objects.count(), 5)
        self.assertEqual(UserVerifyEdge.objects.filter(to_user=self.cara).count(), 2)
        self.assertTrue(UserVerifyEdge.objects.filter(from_user=self.alice, to_user=self.bob).exists())
        self.assertTrue(UserVerifyEdge.objects.filter(from_user=self.bob, to_user=self.alice).exists())

    def test_duplicate_verification_is_idempotent_and_keeps_the_original_edge_time(self):
        self.set_verified(self.alice, True)
        self.assertTrue(self.verify(self.alice, self.bob)['edge_created'])
        created_at = UserVerifyEdge.objects.get().created_at
        self.assertFalse(self.verify(self.alice, self.bob)['edge_created'])
        self.assertEqual(UserVerifyEdge.objects.count(), 1)
        self.assertEqual(UserVerifyEdge.objects.get().created_at, created_at)

    def test_old_request_detach_and_task_endpoints_are_gone(self):
        self.login(self.alice)
        for path in (
            '/api/userprofile/verification/requests',
            '/api/userprofile/verification/detach',
            '/api/userprofile/verification/requests/1/approve',
            '/api/userprofile/verification/requests/1/reject',
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path, {}, content_type='application/json').status_code, 404)
        self.assertEqual(self.client.get('/api/userprofile/verification/tasks/1').status_code, 404)

    def test_admin_sets_verified_both_ways_without_touching_edges_or_other_nodes(self):
        self.login(self.staff)
        result = self.post_json(SET_VERIFIED_URL, {'user_id': self.staff.pk, 'verified': True})
        self.assertTrue(result['verified'])
        self.assertEqual(self.verified(self.staff), [True])
        result = self.post_json(SET_VERIFIED_URL, {'user_id': self.bob.pk, 'verified': True})
        self.assertEqual(result['nodes_updated'], 1)
        UserVerifyEdge.objects.create(from_user=self.staff, to_user=self.bob)
        self.post_json(SET_VERIFIED_URL, {'user_id': self.bob.pk, 'verified': False})
        self.assertEqual(self.verified(self.staff, self.bob, self.cara), [True, False, False])
        self.assertEqual(UserVerifyEdge.objects.count(), 1)

    def test_ordinary_user_cannot_use_admin_endpoints(self):
        self.login(self.alice)
        self.assertEqual(self.client.post(SET_VERIFIED_URL, {'user_id': self.alice.pk, 'verified': True}, content_type='application/json').status_code, 403)
        self.assertIn(self.client.get(GRAPH_URL).status_code, (401, 403))
        for path in (MAINTENANCE_URL, GRAPH_UPDATE_URL):
            with self.subTest(path=path):
                self.assertIn(self.client.post(path, {}, content_type='application/json').status_code, (401, 403))

    def test_maintenance_blocks_two_writes_while_reads_and_batch_remain_available(self):
        self.set_verified(self.alice, True)
        state = self.start_maintenance()
        self.assertTrue(state['active'])
        self.assertEqual(state['owner_id'], self.superuser.pk)
        self.assertTrue(state['owned_by_requester'])
        self.assertIsNotNone(state['expires_at'])

        self.assertEqual(self.verify(self.alice, self.bob, expected=409)['category'], 'maintenance_active')
        self.assertTrue(self.status(self.alice)['maintenance_active'])
        self.login(self.staff)
        body = self.post_json(SET_VERIFIED_URL, {'user_id': self.bob.pk, 'verified': True}, expected=409)
        self.assertEqual(body['category'], 'maintenance_active')

        self.login(self.superuser)
        graph = self.get_json(GRAPH_URL)
        self.assertTrue(graph['maintenance']['active'])
        result = self.post_json(GRAPH_UPDATE_URL, {
            'add_edges': [self.edge(self.alice, self.bob)],
            'set_verified': [{'user_id': self.bob.pk, 'verified': True}],
        })
        self.assertEqual(result, {'added_edges': 1, 'removed_edges': 0, 'updated_nodes': 1})
        self.assertFalse(self.get_json(GRAPH_URL)['maintenance']['active'])
        self.assertEqual(self.verified(self.bob), [True])
        self.assertTrue(UserVerifyEdge.objects.filter(from_user=self.alice, to_user=self.bob).exists())

    def test_maintenance_duration_and_ownership(self):
        self.login(self.superuser)
        self.post_json(MAINTENANCE_URL, {'duration_seconds': 0}, expected=422)
        self.post_json(MAINTENANCE_URL, {'duration_seconds': 3601}, expected=422)
        self.start_maintenance()
        self.assertEqual(self.start_maintenance(expected=409)['category'], 'maintenance_active')
        other = self.create_user('root2', is_superuser=True)
        self.login(other)
        self.assertFalse(self.get_json(GRAPH_URL)['maintenance']['owned_by_requester'])
        self.assertEqual(self.post_json(GRAPH_UPDATE_URL, {}, expected=403)['category'], 'maintenance_owner')
        response = self.client.delete(MAINTENANCE_URL, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.login(self.superuser)
        self.assertEqual(self.client.delete(MAINTENANCE_URL, content_type='application/json').status_code, 204)
        self.assertFalse(self.get_json(GRAPH_URL)['maintenance']['active'])

    def test_expired_maintenance_restores_service(self):
        self.start_maintenance(seconds=1)
        cache.set(MAINTENANCE_KEY, {
            'owner_id': self.superuser.pk,
            'expires_at': (timezone.now() - timedelta(seconds=1)).isoformat(),
        }, timeout=60)
        self.set_verified(self.alice, True)
        self.verify(self.alice, self.bob)
        self.assertTrue(UserVerifyEdge.objects.filter(from_user=self.alice, to_user=self.bob).exists())
        self.login(self.superuser)
        self.assertEqual(self.post_json(GRAPH_UPDATE_URL, {}, expected=409)['category'], 'maintenance_required')

    def test_expired_read_never_deletes_a_newer_maintenance_session(self):
        expired = {
            'owner_id': self.superuser.pk,
            'expires_at': (timezone.now() - timedelta(seconds=1)).isoformat(),
        }
        fresh = {
            'owner_id': self.superuser.pk,
            'expires_at': (timezone.now() + timedelta(minutes=1)).isoformat(),
        }
        cache.set(MAINTENANCE_KEY, expired, timeout=60)
        original_get = cache.get

        def get_after_new_session(key, *args, **kwargs):
            if key == MAINTENANCE_KEY:
                # 模拟 GET 读到旧值之后、清理之前，站长已开启新会话。
                cache.set(MAINTENANCE_KEY, fresh, timeout=60)
                return expired
            return original_get(key, *args, **kwargs)

        with patch('userprofile.verification.cache.cache.get', side_effect=get_after_new_session):
            self.assertIsNone(read_maintenance())
        self.assertEqual(cache.get(MAINTENANCE_KEY), fresh)
        self.assertEqual(read_maintenance()['owner_id'], self.superuser.pk)

    def test_batch_requires_a_session_and_releases_it_after_success(self):
        self.login(self.superuser)
        self.assertEqual(self.post_json(GRAPH_UPDATE_URL, {}, expected=409)['category'], 'maintenance_required')
        self.start_maintenance()
        self.post_json(GRAPH_UPDATE_URL, {'set_verified': [{'user_id': self.alice.pk, 'verified': True}]})
        self.assertEqual(self.post_json(GRAPH_UPDATE_URL, {}, expected=409)['category'], 'maintenance_required')

    def test_batch_validation_rejects_only_invalid_commands(self):
        self.start_maintenance()
        cases = [
            ({'add_edges': [self.edge(self.alice, self.alice)]}, 400, 'self_edge'),
            ({'add_edges': [self.edge(self.alice, self.bob)], 'remove_edges': [self.edge(self.alice, self.bob)]}, 400, 'conflicting_edge'),
            ({'add_edges': [self.edge(self.alice, self.bob), self.edge(self.alice, self.bob)]}, 400, 'duplicate_input'),
            ({'set_verified': [{'user_id': self.alice.pk, 'verified': True}, {'user_id': self.alice.pk, 'verified': True}]}, 400, 'duplicate_input'),
            ({'set_verified': [{'user_id': self.alice.pk, 'verified': True}, {'user_id': self.alice.pk, 'verified': False}]}, 400, 'conflicting_node'),
            ({'set_verified': [{'user_id': 999999, 'verified': True}]}, 404, 'not_found'),
        ]
        for payload, expected, category in cases:
            with self.subTest(category=category):
                self.assertEqual(self.post_json(GRAPH_UPDATE_URL, payload, expected=expected)['category'], category)
        self.assertFalse(UserVerifyEdge.objects.exists())
        self.assertEqual(self.verified(self.alice), [False])
        self.assertTrue(self.get_json(GRAPH_URL)['maintenance']['active'])

    def test_batch_failure_rolls_back_every_write_and_allows_retry(self):
        self.start_maintenance()
        payload = {
            'add_edges': [self.edge(self.alice, self.bob)],
            'set_verified': [{'user_id': self.bob.pk, 'verified': True}],
        }
        original_bulk_create = UserVerifyEdge.objects.bulk_create

        def failing_bulk_create(objs, *args, **kwargs):
            original_bulk_create(objs, *args, **kwargs)
            raise RuntimeError('simulated write failure after edge insert')

        with patch.object(UserVerifyEdge.objects, 'bulk_create', side_effect=failing_bulk_create):
            with self.assertRaises(RuntimeError):
                self.client.post(GRAPH_UPDATE_URL, payload, content_type='application/json')
        self.assertFalse(UserVerifyEdge.objects.exists())
        self.assertEqual(self.verified(self.bob), [False])
        self.assertTrue(self.get_json(GRAPH_URL)['maintenance']['active'])
        self.assertEqual(self.post_json(GRAPH_UPDATE_URL, payload), {
            'added_edges': 1, 'removed_edges': 0, 'updated_nodes': 1,
        })
        self.assertEqual(UserVerifyEdge.objects.count(), 1)

    def test_batch_applies_only_explicit_commands_and_does_not_restore_downstream(self):
        self.set_verified(self.alice, True)
        UserVerifyEdge.objects.create(from_user=self.alice, to_user=self.bob)
        UserVerifyEdge.objects.create(from_user=self.bob, to_user=self.cara)
        self.set_verified(self.bob, True)
        self.set_verified(self.cara, True)
        self.start_maintenance()
        result = self.post_json(GRAPH_UPDATE_URL, {
            'remove_edges': [self.edge(self.alice, self.bob)],
            'set_verified': [
                {'user_id': self.bob.pk, 'verified': False},
                {'user_id': self.cara.pk, 'verified': False},
            ],
        })
        self.assertEqual(result, {'added_edges': 0, 'removed_edges': 1, 'updated_nodes': 2})
        self.assertTrue(UserVerifyEdge.objects.filter(from_user=self.bob, to_user=self.cara).exists())
        self.verify(self.alice, self.bob)
        self.assertEqual(self.verified(self.alice, self.bob, self.cara), [True, True, False])
        self.login(self.superuser)
        node = self.get_json(f'{GRAPH_URL}/{self.bob.pk}')
        self.assertTrue(node['verified'])
        self.assertEqual(node['in_edges'], [self.alice.pk])
        self.assertEqual(node['out_edges'], [self.cara.pk])

    def test_batch_supports_cycles_and_multiple_in_edges(self):
        self.start_maintenance()
        result = self.post_json(GRAPH_UPDATE_URL, {
            'add_edges': [self.edge(self.alice, self.bob), self.edge(self.bob, self.alice), self.edge(self.cara, self.bob)],
            'set_verified': [{'user_id': self.bob.pk, 'verified': True}],
        })
        self.assertEqual(result['added_edges'], 3)
        self.assertEqual(UserVerifyEdge.objects.count(), 3)
        self.assertEqual(len(self.get_json(GRAPH_URL)['edges']), 3)
        self.assertEqual(self.get_json(GRAPH_URL)['verified_user_ids'], [self.bob.pk])

    def test_batch_does_not_duplicate_existing_edges(self):
        UserVerifyEdge.objects.create(from_user=self.alice, to_user=self.bob)
        self.start_maintenance()
        result = self.post_json(GRAPH_UPDATE_URL, {
            'add_edges': [self.edge(self.alice, self.bob), self.edge(self.bob, self.cara)],
        })
        self.assertEqual(result, {'added_edges': 1, 'removed_edges': 0, 'updated_nodes': 0})
        self.assertEqual(UserVerifyEdge.objects.count(), 2)

    def test_account_deletion_cascades_edges_without_repairing_other_nodes(self):
        self.set_verified(self.alice, True)
        self.set_verified(self.bob, True)
        UserVerifyEdge.objects.create(from_user=self.alice, to_user=self.bob)
        self.alice.delete()
        self.assertFalse(UserVerifyEdge.objects.exists())
        self.assertEqual(self.verified(self.bob), [True])

    def test_identity_access_errors_and_player_verification_allows_registration(self):
        self.login(self.alice)
        response = self.client.post('/api/tournament/gsc/participant', {'order': 999})
        self.assertEqual(response.json(), {'type': 'error', 'object': 'userprofile', 'category': 'identity_access_required'})
        self.set_verified(self.alice, True)
        response = self.client.post('/api/tournament/gsc/participant', {'order': 999})
        self.assertEqual(response.status_code, 404)
