import json
from unittest.mock import patch

from django.db import transaction
from django.test import override_settings, TestCase
from django.utils import timezone

from config.text_choices import Medal_TextChoices
from userprofile.models import UserProfile
from .models import MedalDefinition, MedalGrant
from .services import ensure_basic_definitions, evaluate_player
from .utils import NOVICE_REALNAME


@override_settings(
    RATELIMIT_ENABLE=False,
    SESSION_ENGINE='django.contrib.sessions.backends.db',
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'medal-staff-api-tests'}},
)
class MedalStaffApiTests(TestCase):
    def setUp(self):
        self.user = UserProfile.objects.create_user(username='medal_staff_target', email='medal-staff-target@example.com')
        self.staff = UserProfile.objects.create_user(username='medal_operator', email='medal-operator@example.com', is_staff=True)
        self.definition = MedalDefinition.objects.create(
            code='ability.staff.time.b', series='能力', kind=Medal_TextChoices.Kind.PB, metric='timems',
            direction=Medal_TextChoices.Direction.DESC, level='b', thresholds=[60000, 50000], active=True,
        )
        self.manual = MedalDefinition.objects.create(
            code='manual.staff', series='纪念', kind=Medal_TextChoices.Kind.MANUAL, metric='manual',
            direction=Medal_TextChoices.Direction.ASC, thresholds=[1, 2], active=True,
        )
        self.client.force_login(self.staff)

    def post_json(self, path, payload):
        return self.client.post(f'/api/medal/{path}', data=json.dumps(payload), content_type='application/json')

    def override(self, **changes):
        payload = {'user_id': self.user.id, 'code': self.definition.code, 'mode': 'grant', 'reason': '人工核验', 'stage': 50000, 'granted_on': '2020-01-02'}
        payload.update(changes)
        return self.post_json('staff/overrides', payload)

    def staff_summary(self):
        response = self.client.get(f'/api/medal/staff/players/{self.user.id}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_new_staff_endpoints_reject_anonymous_and_nonstaff(self):
        for user in [None, self.user]:
            with self.subTest(user=user):
                self.client.logout()
                if user is not None:
                    self.client.force_login(user)
                for path in ['staff/catalog', f'staff/players/{self.user.id}']:
                    self.assertEqual(self.client.get(f'/api/medal/{path}').status_code, 403)
                for mode in ['grant', 'revoke', 'auto']:
                    self.assertEqual(self.override(mode=mode).status_code, 403)
        self.assertFalse(MedalGrant.objects.exists())

    def test_staff_catalog_includes_hidden_and_inactive_definitions(self):
        hidden = MedalDefinition.objects.create(
            code='manual.staff.hidden', series='隐藏', kind=Medal_TextChoices.Kind.MANUAL, metric='manual',
            direction=Medal_TextChoices.Direction.ASC, thresholds=[1], active=True, hidden=True,
        )
        inactive = MedalDefinition.objects.create(
            code='manual.staff.disabled', series='纪念', kind=Medal_TextChoices.Kind.MANUAL, metric='manual',
            direction=Medal_TextChoices.Direction.ASC, thresholds=[1], active=False,
        )
        response = self.client.get('/api/medal/staff/catalog')
        self.assertEqual(response.status_code, 200, response.content)
        rows = {row['code']: row for row in response.json()}
        self.assertTrue(rows[hidden.code]['hidden'])
        self.assertFalse(rows[inactive.code]['active'])
        self.assertTrue({'code', 'series', 'subseries', 'kind', 'metric', 'direction', 'level', 'style', 'thresholds', 'active', 'hidden'} <= rows[hidden.code].keys())
        self.client.logout()
        public = self.client.get('/api/medal/catalog')
        self.assertEqual(public.status_code, 200, public.content)
        public_codes = {row['code'] for row in public.json()}
        self.assertNotIn(hidden.code, public_codes)
        self.assertNotIn(inactive.code, public_codes)

    def test_invalid_override_payloads_do_not_write(self):
        invalid = [
            {'mode': 'invalid'}, {'stage': 12345}, {'stage': -1}, {'stage': None},
            {'scope_key': 'x' * 129}, {'reason': ''}, {'reason': '   '},
            {'reason': 'x' * 256}, {'granted_on': 'not-a-date'}, {'granted_on': '2026-02-30'},
        ]
        for changes in invalid:
            with self.subTest(changes=changes):
                response = self.override(**changes)
                self.assertIn(response.status_code, (400, 422), response.content)
        missing_reason = self.post_json('staff/overrides', {'user_id': self.user.id, 'code': self.definition.code, 'mode': 'revoke'})
        self.assertEqual(missing_reason.status_code, 422, missing_reason.content)
        summary = self.staff_summary()
        self.assertEqual(summary['grants'], [])
        self.assertEqual(summary['overrides'], [])
        self.assertEqual(summary['history'], [])

    def test_inactive_definition_cannot_be_granted(self):
        self.definition.active = False
        self.definition.save(update_fields=['active'])
        response = self.override()
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(MedalGrant.objects.filter(user=self.user).exists())
        self.assertEqual(self.staff_summary()['overrides'], [])

    def test_grant_requires_an_explicit_date(self):
        response = self.override(granted_on=None)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(MedalGrant.objects.filter(user=self.user).exists())
        self.assertEqual(self.staff_summary()['history'], [])

    def test_unknown_player_and_definition_return_not_found(self):
        self.assertEqual(self.client.get('/api/medal/staff/players/-1').status_code, 404)
        for mode in ['grant', 'revoke', 'auto']:
            with self.subTest(mode=mode):
                self.assertEqual(self.override(user_id=-1, mode=mode).status_code, 404)
                self.assertEqual(self.override(code='missing.definition', mode=mode).status_code, 404)

    def test_grant_override_survives_automatic_evaluation_and_is_audited(self):
        response = self.override(granted_on='2020-01-02')
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()
        self.assertEqual(result['mode'], 'grant')
        self.assertFalse(result['enqueued'])
        grant = MedalGrant.objects.get(pk=result['grant_id'])
        self.assertEqual(grant.stage, 50000)
        self.assertEqual(str(timezone.localdate(grant.granted_at)), '2020-01-02')
        evaluate_player(self.user.id)
        grant.refresh_from_db()
        self.assertIsNone(grant.revoked_at)
        self.assertEqual(grant.stage, 50000)
        summary = self.staff_summary()
        self.assertEqual(summary['user_id'], self.user.id)
        self.assertEqual(summary['username'], self.user.username)
        self.assertEqual(len(summary['overrides']), 1)
        self.assertEqual(len(summary['history']), 1)
        self.assertEqual(summary['history'][0]['reason'], '人工核验')
        self.assertEqual(summary['history'][0]['actor_id'], self.staff.id)
        self.assertEqual(summary['history'][0]['definition_code'], self.definition.code)
        self.assertEqual(summary['history'][0]['action'], 'grant')
        self.assertEqual(summary['overrides'][0]['stage'], 50000)
        self.assertEqual(summary['overrides'][0]['actor_id'], self.staff.id)
        self.assertIn(grant.id, [row['id'] for row in summary['grants']])

    def test_revoke_before_any_grant_prevents_later_automatic_award(self):
        ensure_basic_definitions()
        response = self.override(code=NOVICE_REALNAME, mode='revoke', stage=None)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(response.json()['grant_id'])
        self.assertFalse(response.json()['enqueued'])
        UserProfile.objects.filter(pk=self.user.pk).update(_realname='测试姓名')
        evaluate_player(self.user.id)
        self.assertFalse(MedalGrant.objects.filter(user=self.user, definition_code=NOVICE_REALNAME, revoked_at__isnull=True).exists())
        summary = self.staff_summary()
        self.assertEqual(len(summary['overrides']), 1)
        self.assertEqual(summary['overrides'][0]['mode'], 'revoke')

    def test_auto_releases_override_and_enqueues_only_after_commit(self):
        granted = self.override()
        self.assertEqual(granted.status_code, 200, granted.content)
        with patch('medal.api.enqueue_player_refresh') as enqueue:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.override(mode='auto', stage=None, reason='恢复自动规则')
                self.assertEqual(response.status_code, 200, response.content)
                enqueue.assert_not_called()
            enqueue.assert_called_once_with(self.user.id)
        self.assertTrue(response.json()['enqueued'])
        self.assertEqual(response.json()['mode'], 'auto')
        evaluate_player(self.user.id)
        self.assertFalse(MedalGrant.objects.filter(pk=granted.json()['grant_id'], revoked_at__isnull=True).exists())
        summary = self.staff_summary()
        self.assertEqual(summary['overrides'], [])
        self.assertEqual(summary['history'][0]['action'], 'auto')

    def test_rolled_back_auto_request_keeps_override_and_does_not_enqueue(self):
        self.assertEqual(self.override().status_code, 200)
        with patch('medal.api.enqueue_player_refresh') as enqueue, self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                response = self.override(mode='auto', stage=None)
                self.assertEqual(response.status_code, 200, response.content)
                transaction.set_rollback(True)
        enqueue.assert_not_called()
        summary = self.staff_summary()
        self.assertEqual(len(summary['overrides']), 1)
        self.assertEqual(summary['overrides'][0]['mode'], 'grant')
        self.assertEqual(len(summary['history']), 1)

    def test_auto_without_override_does_not_revoke_natural_award(self):
        ensure_basic_definitions()
        UserProfile.objects.filter(pk=self.user.pk).update(_realname='测试姓名')
        evaluate_player(self.user.id)
        grant = MedalGrant.objects.get(user=self.user, definition_code=NOVICE_REALNAME, revoked_at__isnull=True)
        with patch('medal.api.enqueue_player_refresh') as enqueue, self.captureOnCommitCallbacks(execute=True):
            response = self.override(code=NOVICE_REALNAME, mode='auto', stage=None)
        self.assertIn(response.status_code, (200, 400), response.content)
        if response.status_code == 400:
            enqueue.assert_not_called()
        grant.refresh_from_db()
        self.assertIsNone(grant.revoked_at)
        self.assertEqual(self.staff_summary()['history'], [])

    def test_auto_can_release_override_after_definition_was_deleted(self):
        response = self.override()
        self.assertEqual(response.status_code, 200, response.content)
        code = self.definition.code
        self.definition.delete()
        with patch('medal.api.enqueue_player_refresh') as enqueue, self.captureOnCommitCallbacks(execute=True):
            response = self.override(code=code, mode='auto', stage=None)
        self.assertEqual(response.status_code, 200, response.content)
        enqueue.assert_called_once_with(self.user.id)
        self.assertEqual(self.staff_summary()['overrides'], [])

    def test_scoped_manual_overrides_are_independent(self):
        first = self.override(code=self.manual.code, scope_key='event:1', stage=1)
        second = self.override(code=self.manual.code, scope_key='event:2', stage=2)
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 200, second.content)
        response = self.override(code=self.manual.code, scope_key='event:1', mode='revoke', stage=None)
        self.assertEqual(response.status_code, 200, response.content)
        first_grant = MedalGrant.objects.get(pk=first.json()['grant_id'])
        second_grant = MedalGrant.objects.get(pk=second.json()['grant_id'])
        self.assertIsNotNone(first_grant.revoked_at)
        self.assertIsNone(second_grant.revoked_at)
        self.assertEqual(second_grant.stage, 2)
        self.assertEqual({row['scope_key'] for row in self.staff_summary()['overrides']}, {'event:1', 'event:2'})

    def test_ordinary_medal_cannot_create_scoped_grant_or_revoke(self):
        for mode in ['grant', 'revoke']:
            with self.subTest(mode=mode):
                response = self.override(mode=mode, scope_key='extra-copy')
                self.assertEqual(response.status_code, 400, response.content)
        summary = self.staff_summary()
        self.assertEqual(summary['grants'], [])
        self.assertEqual(summary['overrides'], [])
        self.assertEqual(summary['history'], [])

    def test_legacy_grant_supports_all_active_kinds(self):
        for kind in Medal_TextChoices.Kind.values:
            with self.subTest(kind=kind):
                definition = MedalDefinition.objects.create(
                    code=f'staff.kind.{kind}', series='测试', kind=kind, metric='test',
                    direction=Medal_TextChoices.Direction.ASC, thresholds=[1, 2], active=True,
                )
                response = self.post_json('staff/grants', {
                    'user_id': self.user.id, 'code': definition.code, 'reason': '兼容入口',
                    'stage': 2, 'granted_on': '2020-01-02',
                })
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(MedalGrant.objects.get(pk=response.json()['id']).stage, 2)

    def test_legacy_grant_defaults_manual_stage_and_requires_automatic_stage(self):
        payload = {'user_id': self.user.id, 'code': self.manual.code, 'reason': '兼容入口', 'granted_on': '2020-01-02'}
        response = self.post_json('staff/grants', payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(MedalGrant.objects.get(pk=response.json()['id']).stage, 1)
        payload['code'] = self.definition.code
        self.assertIn(self.post_json('staff/grants', payload).status_code, (400, 422))

    def test_legacy_revoke_is_persistent_and_audited(self):
        ensure_basic_definitions()
        UserProfile.objects.filter(pk=self.user.pk).update(_realname='测试姓名')
        evaluate_player(self.user.id)
        grant = MedalGrant.objects.get(user=self.user, definition_code=NOVICE_REALNAME, revoked_at__isnull=True)
        response = self.post_json(f'staff/grants/{grant.id}/revoke', {'reason': '管理员取消资格'})
        self.assertEqual(response.status_code, 200, response.content)
        evaluate_player(self.user.id)
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revoked_at)
        summary = self.staff_summary()
        self.assertEqual(len(summary['overrides']), 1)
        self.assertEqual(summary['overrides'][0]['mode'], 'revoke')
        self.assertEqual(summary['history'][0]['reason'], '管理员取消资格')

    def test_staff_history_returns_only_the_latest_fifty_actions(self):
        for index in range(52):
            response = self.override(mode='revoke', stage=None, reason=f'action-{index:02d}')
            self.assertEqual(response.status_code, 200, response.content)
        history = self.staff_summary()['history']
        self.assertEqual(len(history), 50)
        self.assertEqual([row['reason'] for row in history], [f'action-{index:02d}' for index in range(51, 1, -1)])
