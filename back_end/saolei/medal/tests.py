from datetime import timedelta
import json

from django.db import connection, IntegrityError, transaction
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.tasks import TaskResultStatus
from django.test import override_settings, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from accountlink.models import AccountLinkQueue, Platform
from config.text_choices import Medal_TextChoices, MS_TextChoices
from userprofile.models import UserProfile
from videomanager.models import ExpandVideoModel, STNB_COEFFICIENTS, VideoModel
from .models import MedalContribution, MedalDefinition, MedalGrant, MedalPins, MedalScan, PlayerProgress
from .services import active_definitions, ensure_basic_definitions, ensure_shareholder_definition, evaluate_min_video_id, evaluate_player, player_summary, replace_pins, write_stage
from .signals import enqueue_medal_refresh_on_video
from .tasks import task_backfill_player_medals, task_refresh_player_medals
from .utils import BVS_SCALE, MAX_PINS, NOVICE_LEVELS, NOVICE_LEVELS_NF, NOVICE_MODES, NOVICE_REALNAME, NOVICE_REVIEW, NOVICE_SAOLEI, open_modes, reached_asc_stage, REFRESH_COALESCE_DELAY, SHAREHOLDER_CODE, STANDARD_LEVELS, THRP_SCALE, to_units


@override_settings(
    RATELIMIT_ENABLE=False,
    SESSION_ENGINE='django.contrib.sessions.backends.db',
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'medal-tests'}},
)
class MedalTestCase(TestCase):
    def delete_video(self, video_id):
        signals = (pre_save, post_save, pre_delete, post_delete)
        saved = [(signal, list(signal.receivers), dict(signal.sender_receivers_cache)) for signal in signals]
        for signal in signals:
            signal.receivers = []
            signal.sender_receivers_cache.clear()
        try:
            VideoModel.objects.filter(pk=video_id).delete()
        finally:
            for signal, receivers, cache in saved:
                signal.receivers = receivers
                signal.sender_receivers_cache.clear()
                signal.sender_receivers_cache.update(cache)

    def wear(self, user, codes=None):
        stored = MedalPins.objects.filter(pk=user.pk).values_list('grant_ids', flat=True).first() or []
        grants = MedalGrant.objects.filter(user=user, revoked_at__isnull=True, stage__gt=0)
        if codes:
            grants = grants.filter(definition_code__in=list(codes))
        ids = [item for item in stored if isinstance(item, int)]
        for grant_id in grants.order_by('scope_key', 'id').values_list('id', flat=True):
            if grant_id not in ids:
                ids.append(grant_id)
        ids = ids[:MAX_PINS]
        if ids == list(stored):
            return
        with self.captureOnCommitCallbacks(execute=True):
            replace_pins(user, ids)


class MedalShellFixture(MedalTestCase):
    def setUp(self):
        self.user = UserProfile.objects.create_user(username='medal_user', email='medal-user@example.com', password='password')
        self.definition = MedalDefinition.objects.create(
            code='ability.time.b', series=Medal_TextChoices.Series.BREAKTHROUGH, subseries='破限', kind=Medal_TextChoices.Kind.PB, metric='timems',
            direction=Medal_TextChoices.Direction.DESC, level='b', thresholds=[60000, 50000, 20000], score_by_stage=[3, 5, 8], active=True,
        )
        self.granted_at = timezone.now() - timedelta(days=3)


class MedalShellTests(MedalShellFixture):
    def test_catalog_serializes_compact_enum_values(self):
        response = self.client.get('/api/medal/catalog')
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertTrue(rows)
        for row in rows:
            with self.subTest(code=row['code']):
                self.assertIn(row['series'], Medal_TextChoices.Series.values)
                self.assertLessEqual(len(row['series']), 2)
                self.assertIn(row['kind'], Medal_TextChoices.Kind.values)
                self.assertEqual(len(row['kind']), 1)
                self.assertIn(row['direction'], Medal_TextChoices.Direction.values)
                self.assertEqual(len(row['direction']), 1)
                self.assertIn(row['style'], ['', *Medal_TextChoices.Style.values])
                self.assertLessEqual(len(row['style']), 1)
                self.assertIn(row['level'], ['', *Medal_TextChoices.Level.values])

    def test_summary_and_pins_serialize_compact_enum_values(self):
        MedalScan.objects.create(user=self.user, scanned_at=timezone.now())
        grant = write_stage(self.user, self.definition, stage=50000, granted_at=self.granted_at)
        replace_pins(self.user, [grant.id])
        response = self.client.get(f'/api/medal/players/{self.user.id}')
        self.assertEqual(response.status_code, 200)
        summary = response.json()
        items = [item for group in summary['series'] for item in group['items'] if item['code'] == self.definition.code]
        self.assertEqual(len(items), 1)
        self.assertEqual(len(summary['pins']), 1)
        expected = (Medal_TextChoices.Series.BREAKTHROUGH.value, Medal_TextChoices.Kind.PB.value, Medal_TextChoices.Direction.DESC.value)
        for item in [items[0], summary['pins'][0]]:
            self.assertEqual((item['series'], item['kind'], item['direction']), expected)

    def test_catalog_cache_hit_does_not_query_definitions(self):
        expected = active_definitions()
        with self.assertNumQueries(0):
            self.assertEqual(active_definitions(), expected)

    def test_warm_summary_uses_one_query_without_definition_reads(self):
        MedalScan.objects.create(user=self.user, scanned_at=timezone.now())
        player_summary(self.user.id)
        with self.assertNumQueries(1):
            summary = player_summary(self.user.id)
        self.assertFalse(summary['scan_pending'])

    def test_write_stage_rewrites_one_grant(self):
        first = write_stage(self.user, self.definition, stage=60000, current_value=59000, granted_at=self.granted_at, evidence={'video_id': 1})
        same = write_stage(self.user, self.definition, stage=60000, current_value=58000, granted_at=timezone.now(), evidence={'video_id': 2})
        self.assertEqual(same.id, first.id)
        self.assertEqual(same.evidence, {'video_id': 1})
        self.assertEqual(same.granted_at, self.granted_at)
        self.assertIsNone(PlayerProgress.objects.get(user=self.user, code=self.definition.code).current_value)

        higher_at = timezone.now() - timedelta(days=1)
        higher = write_stage(self.user, self.definition, stage=50000, current_value=49000, granted_at=higher_at, evidence={'video_id': 3})
        self.assertEqual(higher.id, first.id)
        self.assertEqual(higher.stage, 50000)
        self.assertEqual(higher.evidence, {'video_id': 3})
        self.assertEqual(higher.granted_at, self.granted_at)
        self.assertEqual([item['stage'] for item in higher.stage_log], [60000, 50000])
        summary = player_summary(self.user.id)
        self.assertEqual(summary['score'], 5)
        ability = next(item for group in summary['series'] for item in group['items'] if item['code'] == 'ability.time.b')
        self.assertEqual(ability['next_threshold'], 20000)

        self.definition.thresholds = [10000]
        self.definition.save(update_fields=['thresholds'])
        rewritten = write_stage(self.user, self.definition, stage=10000, current_value=9000, granted_at=timezone.now(), evidence={'video_id': 4})
        self.assertEqual(rewritten.id, first.id)
        self.assertEqual(rewritten.stage, 10000)
        revoked = write_stage(self.user, self.definition, stage=0, current_value=None, granted_at=timezone.now())
        self.assertEqual(revoked.id, first.id)
        self.assertIsNotNone(revoked.revoked_at)
        self.assertEqual(MedalGrant.objects.filter(user=self.user, definition_code=self.definition.code).count(), 1)
        self.assertEqual(PlayerProgress.objects.get(user=self.user).current_stage, 0)

        reopened = write_stage(self.user, self.definition, stage=10000, current_value=9000, granted_at=timezone.now(), evidence={'video_id': 5})
        self.assertEqual(reopened.id, first.id)
        self.assertIsNone(reopened.revoked_at)
        self.assertEqual(reopened.granted_at, self.granted_at)

    def test_scope_key_is_a_separate_medal(self):
        first = write_stage(self.user, self.definition, scope_key='1', stage=60000, current_value=1, granted_at=self.granted_at)
        second = write_stage(self.user, self.definition, scope_key='2', stage=60000, current_value=1, granted_at=self.granted_at)
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(PlayerProgress.objects.filter(user=self.user, code=self.definition.code).count(), 1)

    def test_manual_grant_is_not_revoked_by_stage_zero(self):
        manual = MedalDefinition.objects.create(
            code='manual.sample', series='纪念', kind=Medal_TextChoices.Kind.MANUAL, metric='manual', direction=Medal_TextChoices.Direction.ASC, thresholds=[], active=True,
        )
        grant = write_stage(self.user, manual, stage=1, current_value=1, granted_at=self.granted_at, evidence={'reason': '早期建设'})
        kept = write_stage(self.user, manual, stage=0, current_value=0, granted_at=timezone.now())
        self.assertEqual(kept.id, grant.id)
        self.assertIsNone(kept.revoked_at)

    def test_contribution_source_key_is_unique(self):
        MedalContribution.objects.create(user=self.user, code='practice.count.b', source_key='video:1')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MedalContribution.objects.create(user=self.user, code='practice.count.b', source_key='video:1')

    def test_catalog_hides_inactive_and_locked_hidden(self):
        MedalDefinition.objects.create(
            code='ability.off', series='能力', kind=Medal_TextChoices.Kind.PB, metric='timems', direction=Medal_TextChoices.Direction.DESC, thresholds=[60000], active=False,
        )
        hidden = MedalDefinition.objects.create(
            code='hidden.sample', series='隐藏', kind=Medal_TextChoices.Kind.ONCE, metric='timems', direction=Medal_TextChoices.Direction.ASC,
            thresholds=[1], hidden=True, active=True, annotation='彩蛋',
        )
        anonymous = self.client.get('/api/medal/catalog')
        self.assertEqual(anonymous.status_code, 200)
        codes = [item['code'] for item in anonymous.json()]
        self.assertIn('ability.time.b', codes)
        self.assertIn(SHAREHOLDER_CODE, codes)
        self.assertIn('novice.realname', codes)
        self.assertNotIn('ability.off', codes)
        self.assertNotIn('hidden.sample', codes)
        self.assertNotIn('scope', anonymous.json()[0])

        self.client.force_login(self.user)
        logged_in = [item['code'] for item in self.client.get('/api/medal/catalog').json()]
        self.assertIn('ability.time.b', logged_in)
        self.assertNotIn('hidden.sample', logged_in)
        write_stage(self.user, hidden, stage=1, current_value=1, granted_at=self.granted_at, evidence={'video_id': 9})
        unlocked = self.client.get('/api/medal/catalog').json()
        hidden_row = next(item for item in unlocked if item['code'] == 'hidden.sample')
        self.assertEqual(hidden_row['annotation'], '彩蛋')

        other = UserProfile.objects.create_user(username='medal_other', email='medal-other@example.com', password='password')
        self.client.force_login(other)
        self.assertNotIn('hidden.sample', [item['code'] for item in self.client.get('/api/medal/catalog').json()])
        visitor = self.client.get(f'/api/medal/players/{self.user.id}')
        self.assertEqual(visitor.status_code, 200)
        shown = [item['code'] for group in visitor.json()['series'] for item in group['items']]
        self.assertIn('hidden.sample', shown)
        self.assertNotIn('ability.off', shown)

    def test_locked_hidden_is_absent_from_player_summary(self):
        MedalDefinition.objects.create(
            code='hidden.locked', series='隐藏', kind=Medal_TextChoices.Kind.ONCE, metric='timems', direction=Medal_TextChoices.Direction.ASC, thresholds=[1], hidden=True, active=True,
        )
        response = self.client.get(f'/api/medal/players/{self.user.id}')
        self.assertEqual(response.status_code, 200)
        codes = [item['code'] for group in response.json()['series'] for item in group['items']]
        self.assertIn('ability.time.b', codes)
        self.assertIn(SHAREHOLDER_CODE, codes)
        self.assertNotIn('hidden.locked', codes)
        ability = next(item for group in response.json()['series'] for item in group['items'] if item['code'] == 'ability.time.b')
        self.assertIsNone(ability['grant_id'])
        self.assertEqual(self.client.get('/api/medal/players/0').status_code, 404)

    def test_pins_belong_to_the_owner_and_keep_order(self):
        other = UserProfile.objects.create_user(username='medal_other', email='medal-other@example.com', password='password')
        second = MedalDefinition.objects.create(
            code='ability.bvs.b', series=Medal_TextChoices.Series.SPEED, subseries='神速', kind=Medal_TextChoices.Kind.PB, metric='bvs', direction=Medal_TextChoices.Direction.ASC, thresholds=[10000], active=True,
        )
        own = write_stage(self.user, self.definition, stage=60000, current_value=59000, granted_at=self.granted_at)
        other_grant = write_stage(other, second, stage=10000, current_value=10000, granted_at=self.granted_at)
        later = write_stage(self.user, second, stage=10000, current_value=12000, granted_at=self.granted_at)

        self.assertEqual(self.client.put('/api/medal/pins', data=json.dumps({'grant_ids': [own.id]}), content_type='application/json').status_code, 403)
        self.client.force_login(self.user)
        rejected = self.client.put('/api/medal/pins', data=json.dumps({'grant_ids': [own.id] * 7}), content_type='application/json')
        self.assertEqual(rejected.status_code, 400)
        foreign = self.client.put('/api/medal/pins', data=json.dumps({'grant_ids': [other_grant.id]}), content_type='application/json')
        self.assertEqual(foreign.status_code, 400)
        saved = self.client.put('/api/medal/pins', data=json.dumps({'grant_ids': [later.id, own.id]}), content_type='application/json')
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()['pin_ids'], [later.id, own.id])
        summary = self.client.get(f'/api/medal/players/{self.user.id}').json()
        self.assertEqual(summary['max_pins'], MAX_PINS)
        self.assertEqual(summary['pin_ids'], [later.id, own.id])
        self.assertEqual([item['stage'] for item in summary['pins']], [10000, 60000])

        write_stage(self.user, second, stage=0, current_value=0, granted_at=timezone.now())
        revoked = self.client.put('/api/medal/pins', data=json.dumps({'grant_ids': [later.id]}), content_type='application/json')
        self.assertEqual(revoked.status_code, 400)
        after = self.client.get(f'/api/medal/players/{self.user.id}').json()
        self.assertEqual(after['pin_ids'], [own.id])

    def test_refresh_coalesces_ready_tasks(self):
        self.client.force_login(self.user)
        before = timezone.now()
        self.assertEqual(self.client.post('/api/medal/refresh').status_code, 200)
        rows = DBTaskResult.objects.filter(task_path=task_refresh_player_medals.module_path, status=TaskResultStatus.READY)
        self.assertEqual(rows.count(), 1)
        row = rows.get()
        self.assertEqual(row.priority, 1)
        self.assertEqual(row.args_kwargs['args'], [self.user.id])
        self.assertGreaterEqual(row.run_after, before + REFRESH_COALESCE_DELAY)
        self.assertLessEqual(row.run_after, timezone.now() + REFRESH_COALESCE_DELAY)
        scheduled = row.run_after
        self.assertEqual(self.client.post('/api/medal/refresh').status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.run_after, scheduled)
        self.assertEqual(self.client.post('/api/medal/refresh').status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.post('/api/medal/refresh').status_code, 403)

    def test_staff_grant_and_revoke(self):
        staff = UserProfile.objects.create_user(username='medal_staff', email='medal-staff@example.com', password='password', is_staff=True)
        MedalDefinition.objects.create(
            code='manual.sample', series='纪念', kind=Medal_TextChoices.Kind.MANUAL, metric='manual', direction=Medal_TextChoices.Direction.ASC, thresholds=[1], active=True,
        )
        body = {'code': 'manual.sample', 'user_id': self.user.id, 'reason': '早期建设', 'granted_on': '2020-01-02'}
        self.client.force_login(self.user)
        self.assertEqual(self.client.post('/api/medal/staff/grants', data=json.dumps(body), content_type='application/json').status_code, 403)
        self.client.force_login(staff)
        created = self.client.post('/api/medal/staff/grants', data=json.dumps(body), content_type='application/json')
        self.assertEqual(created.status_code, 200)
        grant_id = created.json()['id']
        self.assertEqual(MedalGrant.objects.get(pk=grant_id).evidence['reason'], '早期建设')
        empty = self.client.post(f'/api/medal/staff/grants/{grant_id}/revoke', data=json.dumps({'reason': '  '}), content_type='application/json')
        self.assertEqual(empty.status_code, 400)
        revoked = self.client.post(f'/api/medal/staff/grants/{grant_id}/revoke', data=json.dumps({'reason': '更正'}), content_type='application/json')
        self.assertEqual(revoked.status_code, 200)
        self.assertIsNotNone(MedalGrant.objects.get(pk=grant_id).revoked_at)
        rebuild = self.client.post('/api/medal/staff/rebuild', data=json.dumps({'user_id': self.user.id}), content_type='application/json')
        self.assertEqual(rebuild.status_code, 200)
        self.assertEqual(self.client.get(f'/api/medal/players/{self.user.id}/grants').json()['count'], 0)

    def test_first_summary_scans_videos_already_in_the_library(self):
        self.user.realname = '已实名'
        self.user.save(update_fields=['_realname', 'date_updated'])
        expand = ExpandVideoModel.objects.create(identifier='history-scan')
        VideoModel.objects.bulk_create([
            VideoModel(
                id=9100001, player=self.user, video=expand, file='videos/9100001.evf', software='e',
                level='e', mode='00', state=MS_TextChoices.State.OFFICIAL, timems=56258, bv=100,
                left=100, right=36, double=0, left_ce=100, right_ce=36, double_ce=0,
            ),
        ])
        before = self.client.get(f'/api/medal/players/{self.user.id}')
        self.assertEqual(before.status_code, 200)
        self.assertTrue(before.json()['scan_pending'])
        self.assertFalse(MedalGrant.objects.filter(user=self.user, revoked_at__isnull=True).exists())
        queued = DBTaskResult.objects.filter(task_path=task_backfill_player_medals.module_path, status=TaskResultStatus.READY)
        self.assertEqual(queued.count(), 1)
        self.assertEqual(queued.get().args_kwargs['args'], [self.user.id])
        evaluate_player(self.user.id)
        self.assertTrue(MedalScan.objects.filter(user=self.user).exists())
        granted = set(MedalGrant.objects.filter(user=self.user, revoked_at__isnull=True).values_list('definition_code', flat=True))
        self.assertIn(NOVICE_REALNAME, granted)
        self.assertIn(NOVICE_REVIEW, granted)
        again = self.client.get(f'/api/medal/players/{self.user.id}')
        self.assertEqual(again.status_code, 200)
        self.assertFalse(again.json()['scan_pending'])
        self.assertEqual(queued.count(), 1)


class ShareholderTests(MedalShellFixture):
    def make_video(self, video_id, upload_time):
        expand = ExpandVideoModel.objects.create(identifier=f'shareholder-{video_id}')
        VideoModel.objects.bulk_create([
            VideoModel(
                id=video_id, player=self.user, video=expand, file=f'videos/{video_id}.evf',
                software='e', level='b', mode='00', state='a', timems=1000, bv=1,
            ),
        ])
        VideoModel.objects.filter(pk=video_id).update(upload_time=upload_time)
        return VideoModel.objects.get(pk=video_id)

    def test_min_id_rewrites_one_grant(self):
        first_time = timezone.now() - timedelta(days=4)
        later = timezone.now() - timedelta(days=1)
        broad = self.make_video(50000, first_time)
        grant = evaluate_min_video_id(self.user)
        self.assertEqual(grant.stage, 100000)
        self.assertEqual(grant.video_id, broad.id)
        self.assertEqual(grant.granted_at, broad.upload_time)
        self.assertEqual([item['stage'] for item in grant.stage_log], [100000])

        closer = self.make_video(20000, later)
        same = evaluate_min_video_id(self.user)
        self.assertEqual(same.id, grant.id)
        self.assertEqual(same.stage, 100000)
        self.assertEqual(same.video_id, broad.id)
        self.assertEqual(same.granted_at, broad.upload_time)
        progress = PlayerProgress.objects.get(user=self.user, code=SHAREHOLDER_CODE)
        self.assertEqual(progress.current_value, 20000)
        self.assertEqual(progress.best_video_id, closer.id)

        self.delete_video(broad.id)
        replaced = evaluate_min_video_id(self.user)
        self.assertEqual(replaced.video_id, closer.id)
        self.assertEqual([item['stage'] for item in replaced.stage_log], [100000])

        rare = self.make_video(500, later)
        higher = evaluate_min_video_id(self.user)
        self.assertEqual(higher.id, grant.id)
        self.assertEqual(higher.stage, 1000)
        self.assertEqual(higher.video_id, rare.id)
        self.assertEqual(higher.granted_at, broad.upload_time)
        self.assertEqual([item['stage'] for item in higher.stage_log], [100000, 1000])

        self.delete_video(rare.id)
        self.delete_video(closer.id)
        revoked = evaluate_min_video_id(self.user)
        self.assertIsNotNone(revoked.revoked_at)
        self.assertEqual(PlayerProgress.objects.get(user=self.user, code=SHAREHOLDER_CODE).current_stage, 0)

    def test_boundary_is_strict_and_plain_videos_count(self):
        now = timezone.now()
        self.make_video(100000, now)
        missed = evaluate_min_video_id(self.user)
        self.assertIsNone(missed)
        self.assertEqual(PlayerProgress.objects.get(user=self.user, code=SHAREHOLDER_CODE).current_value, 100000)

        self.make_video(1000, now)
        middle = evaluate_min_video_id(self.user)
        self.assertEqual(middle.stage, 10000)
        self.make_video(999, now)
        task_refresh_player_medals.call(self.user.id)
        top = MedalGrant.objects.get(user=self.user, definition_code=SHAREHOLDER_CODE, revoked_at__isnull=True)
        self.assertEqual(top.id, middle.id)
        self.assertEqual(top.stage, 1000)

    def test_existing_thresholds_are_kept(self):
        definition = ensure_shareholder_definition()
        definition.thresholds = [50]
        definition.save(update_fields=['thresholds'])
        self.assertEqual(ensure_shareholder_definition().thresholds, [50])

    def test_video_change_enqueues_current_and_previous_player(self):
        other = UserProfile.objects.create_user(username='medal_prev', email='medal-prev@example.com', password='password')
        instance = type('Video', (), {'player_id': self.user.id, '_old_values': {'player_id': other.id}})()
        with self.captureOnCommitCallbacks(execute=True):
            enqueue_medal_refresh_on_video(sender=VideoModel, instance=instance)
        rows = DBTaskResult.objects.filter(task_path=task_refresh_player_medals.module_path, status=TaskResultStatus.READY)
        self.assertCountEqual([row.args_kwargs['args'] for row in rows], [[self.user.id], [other.id]])


@override_settings(
    RATELIMIT_ENABLE=False,
    SESSION_ENGINE='django.contrib.sessions.backends.db',
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'medal-basic'}},
)
class BasicMedalTests(MedalTestCase):
    def setUp(self):
        self.user = UserProfile.objects.create_user(username='medal_basic', email='medal-basic@example.com', password='password')
        self.ids = iter(range(3_000_000, 4_000_000))
        self.earlier = timezone.now() - timedelta(days=4)
        self.middle = timezone.now() - timedelta(days=2)
        self.later = timezone.now() - timedelta(days=1)

    def make_video(self, *, level='b', mode='00', state=None, timems=10000, bv=10, right_ce=0, left_ce=None, double_ce=0, ongoing=False, upload_time=None, video_id=None):
        if state is None:
            state = MS_TextChoices.State.OFFICIAL
        if left_ce is None:
            left_ce = bv
        video_id = next(self.ids) if video_id is None else video_id
        expand = ExpandVideoModel.objects.create(identifier=f'basic-{video_id}')
        VideoModel.objects.bulk_create([
            VideoModel(
                id=video_id, player=self.user, video=expand, file=f'videos/{video_id}.evf', software='e',
                level=level, mode=mode, state=state, timems=timems, bv=bv, ongoing_tournament=ongoing,
                left=max(left_ce, 1), right=right_ce, double=double_ce, left_ce=left_ce, right_ce=right_ce, double_ce=double_ce,
            ),
        ])
        VideoModel.objects.filter(pk=video_id).update(upload_time=upload_time or timezone.now())
        return VideoModel.objects.get(pk=video_id)

    def active(self, code):
        return MedalGrant.objects.filter(user=self.user, definition_code=code, revoked_at__isnull=True).first()

    def test_pb_threshold_changes_revoke_and_regrant_without_new_video(self):
        self.make_video(timems=19000)
        evaluate_player(self.user.id)
        grant = self.active('ability.time.b')
        definition = MedalDefinition.objects.get(pk='ability.time.b')
        definition.thresholds = [10000]
        definition.save(update_fields=['thresholds'])
        evaluate_player(self.user.id)
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revoked_at)
        self.assertEqual(PlayerProgress.objects.get(user=self.user, code=definition.code).current_stage, 0)
        definition.thresholds = [30000]
        definition.save(update_fields=['thresholds'])
        evaluate_player(self.user.id)
        grant.refresh_from_db()
        self.assertIsNone(grant.revoked_at)
        self.assertEqual(grant.stage, 30000)

    def test_pb_invalid_evidence_is_replaced_while_later_faster_video_remains(self):
        first = self.make_video(timems=19000, upload_time=self.earlier)
        evaluate_player(self.user.id)
        best = self.make_video(timems=16000, upload_time=self.middle)
        evaluate_player(self.user.id)
        grant = self.active('ability.time.b')
        self.assertEqual(grant.video_id, first.id)
        VideoModel.objects.filter(pk=first.id).update(state=MS_TextChoices.State.FROZEN)
        evaluate_player(self.user.id)
        grant.refresh_from_db()
        self.assertEqual(grant.video_id, best.id)
        self.assertIsNone(grant.revoked_at)
        self.assertEqual([entry['stage'] for entry in grant.stage_log], [20000])

    def test_pb_deleted_evidence_is_replaced_while_later_faster_video_remains(self):
        first = self.make_video(timems=19000, upload_time=self.earlier)
        evaluate_player(self.user.id)
        best = self.make_video(timems=16000, upload_time=self.middle)
        evaluate_player(self.user.id)
        self.delete_video(first.id)
        evaluate_player(self.user.id)
        grant = self.active('ability.time.b')
        self.assertEqual(grant.video_id, best.id)
        self.assertEqual(grant.evidence['video_id'], best.id)

    def test_unchanged_refresh_reuses_state_and_does_not_write(self):
        self.user.realname = '刷新测试'
        self.user.save(update_fields=['_realname'])
        AccountLinkQueue.objects.create(platform=Platform.SAOLEI, identifier='no-op-scan', userprofile=self.user, verified=True)
        self.make_video(video_id=500, upload_time=self.earlier)
        for level in STANDARD_LEVELS:
            self.make_video(level=level, bv=100, left_ce=100, right_ce=0)
            self.make_video(level=level, bv=120, left_ce=80, right_ce=20)
        for mode in open_modes():
            self.make_video(mode=mode)
        evaluate_player(self.user.id)
        for code in [NOVICE_REALNAME, NOVICE_REVIEW, NOVICE_LEVELS, NOVICE_LEVELS_NF, NOVICE_MODES, NOVICE_SAOLEI, SHAREHOLDER_CODE, 'ability.thrp.nf.three', 'ability.thrp.fl.three']:
            self.assertIsNotNone(self.active(code), code)
        with CaptureQueriesContext(connection) as captured:
            evaluate_player(self.user.id)
        writes = [query['sql'] for query in captured if query['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE '))]
        self.assertEqual(writes, [])
        progress_reads = [query['sql'] for query in captured if query['sql'].startswith('SELECT ') and 'medal_playerprogress' in query['sql']]
        self.assertEqual(len(progress_reads), 1)

    def test_scaled_thresholds_are_not_overwritten(self):
        self.assertEqual(to_units(1.5, BVS_SCALE), 15000)
        self.assertEqual(to_units(0.95, THRP_SCALE), 95000)
        self.assertEqual(to_units(2.3, THRP_SCALE), 230000)
        self.assertNotEqual(to_units(1.5, BVS_SCALE), 2)
        evaluate_player(self.user.id)
        definition = MedalDefinition.objects.get(code='ability.bvs.b')
        self.assertEqual(definition.series, Medal_TextChoices.Series.SPEED)
        self.assertEqual(definition.thresholds[1], 15000)
        self.assertTrue(definition.active)
        self.assertFalse(definition.hidden)
        self.assertEqual(definition.score_by_stage, [])
        self.assertIsNone(definition.bv_min)
        definition.thresholds = [1]
        definition.active = False
        definition.hidden = True
        definition.save(update_fields=['thresholds', 'active', 'hidden'])
        ensure_basic_definitions()
        kept = MedalDefinition.objects.get(code='ability.bvs.b')
        self.assertEqual(kept.thresholds, [1])
        self.assertEqual(kept.series, Medal_TextChoices.Series.SPEED)
        self.assertFalse(kept.active)
        self.assertTrue(kept.hidden)
        self.assertTrue(any(index.name == 'video_player_state_level_idx' for index in VideoModel._meta.indexes))

    def test_time_upgrades_keeps_evidence_then_drops(self):
        missed = self.make_video(timems=20000, upload_time=self.earlier)
        evaluate_player(self.user.id)
        self.assertIsNone(self.active('ability.time.b'))
        first = self.make_video(timems=19000, upload_time=self.earlier)
        evaluate_player(self.user.id)
        grant = self.active('ability.time.b')
        self.assertEqual(grant.stage, 20000)
        self.assertEqual(grant.video_id, first.id)
        self.assertEqual(grant.granted_at, first.upload_time)
        same = self.make_video(timems=16000, upload_time=self.middle)
        evaluate_player(self.user.id)
        grant.refresh_from_db()
        self.assertEqual(grant.stage, 20000)
        self.assertEqual(grant.video_id, first.id)
        self.assertEqual([item['stage'] for item in grant.stage_log], [20000])
        progress = PlayerProgress.objects.get(user=self.user, code='ability.time.b')
        self.assertIsNone(progress.current_value)
        self.assertIsNone(progress.best_video_id)
        higher = self.make_video(timems=14000, upload_time=self.later)
        evaluate_player(self.user.id)
        grant.refresh_from_db()
        self.assertEqual(grant.stage, 15000)
        self.assertEqual(grant.video_id, higher.id)
        self.assertEqual(grant.granted_at, first.upload_time)
        self.assertEqual([item['stage'] for item in grant.stage_log], [20000, 15000])
        VideoModel.objects.filter(pk__in=[same.id, higher.id]).update(state=MS_TextChoices.State.FROZEN)
        evaluate_player(self.user.id)
        grant.refresh_from_db()
        self.assertIsNone(grant.revoked_at)
        self.assertEqual(grant.stage, 20000)
        self.assertEqual(grant.video_id, first.id)
        VideoModel.objects.filter(pk=first.id).update(state=MS_TextChoices.State.FROZEN)
        evaluate_player(self.user.id)
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revoked_at)
        self.assertIsNone(self.active('ability.time.b'))
        self.assertNotEqual(missed.id, first.id)

    def test_speed_and_stnb_use_server_scales(self):
        slow = self.make_video(bv=10, timems=10000, upload_time=self.earlier)
        evaluate_player(self.user.id)
        grant = self.active('ability.bvs.b')
        self.assertEqual(grant.stage, to_units(1, BVS_SCALE))
        self.assertNotEqual(grant.stage, 2)
        exact = self.make_video(bv=15, timems=10000, upload_time=self.middle)
        evaluate_player(self.user.id)
        grant.refresh_from_db()
        self.assertEqual(grant.id, self.active('ability.bvs.b').id)
        self.assertEqual(grant.stage, 15000)
        self.assertEqual(grant.video_id, exact.id)
        self.assertEqual(grant.granted_at, slow.upload_time)
        self.assertIsNone(PlayerProgress.objects.get(user=self.user, code='ability.bvs.b').best_video_id)

    def test_stnb_uses_videomanager_coefficient(self):
        below = self.make_video(bv=12, timems=10000, upload_time=self.earlier)
        evaluate_player(self.user.id)
        below.refresh_from_db()
        stnb = STNB_COEFFICIENTS[below.level] * below.iqg
        self.assertEqual(STNB_COEFFICIENTS[MS_TextChoices.Level.BEGINNER], 36)
        self.assertLess(stnb, 10)
        self.assertGreaterEqual(47.299 * below.iqg, 10)
        self.assertIsNone(self.active('ability.stnb.b'))
        reached = self.make_video(bv=30, timems=10000, upload_time=self.later)
        evaluate_player(self.user.id)
        reached.refresh_from_db()
        expected = reached_asc_stage(
            MedalDefinition.objects.get(code='ability.stnb.b').thresholds, STNB_COEFFICIENTS[reached.level] * reached.iqg,
        )
        self.assertGreaterEqual(expected, 10)
        self.assertEqual(self.active('ability.stnb.b').stage, expected)

    def test_nf_and_fl_stay_separate(self):
        flagged = self.make_video(timems=19999, bv=120, left_ce=80, right_ce=20, upload_time=self.earlier)
        evaluate_player(self.user.id)
        self.assertEqual(self.active('ability.time.b').stage, 20000)
        self.assertIsNone(self.active('ability.time.nf.b'))
        self.assertEqual(self.active('ability.thrp.fl.b').stage, to_units(1.2, THRP_SCALE))
        self.assertIsNone(self.active('ability.thrp.nf.b'))
        broken = self.make_video(timems=30000, bv=200, left_ce=100, right_ce=0, upload_time=self.middle)
        evaluate_player(self.user.id)
        self.assertIsNone(self.active('ability.thrp.nf.b'))
        precise = self.make_video(timems=30000, bv=96, left_ce=100, right_ce=0, upload_time=self.later)
        evaluate_player(self.user.id)
        nf = self.active('ability.thrp.nf.b')
        self.assertEqual(nf.stage, 95000)
        self.assertEqual(nf.video_id, precise.id)
        self.assertNotEqual(nf.video_id, flagged.id)
        self.assertNotEqual(nf.video_id, broken.id)
        self.assertEqual(self.active('ability.thrp.fl.b').video_id, flagged.id)
        flagless_time = self.make_video(timems=18000, bv=10, right_ce=0, upload_time=self.later)
        evaluate_player(self.user.id)
        self.assertEqual(self.active('ability.time.nf.b').video_id, flagless_time.id)
        self.assertEqual(self.active('ability.time.b').video_id, flagged.id)

    def test_three_tier_does_not_replace_single_levels(self):
        beginner = self.make_video(level='b', bv=100, left_ce=100, right_ce=0, upload_time=self.earlier)
        intermediate = self.make_video(level='i', bv=100, left_ce=100, right_ce=0, upload_time=self.middle)
        evaluate_player(self.user.id)
        self.assertIsNotNone(self.active('ability.thrp.nf.b'))
        self.assertIsNotNone(self.active('ability.thrp.nf.i'))
        self.assertIsNone(self.active('ability.thrp.nf.three'))
        expert = self.make_video(level='e', bv=100, left_ce=100, right_ce=0, upload_time=self.later)
        evaluate_player(self.user.id)
        composite = self.active('ability.thrp.nf.three')
        self.assertEqual(composite.stage, 100000)
        self.assertEqual(composite.evidence['video_ids'], [beginner.id, intermediate.id, expert.id])
        self.assertIsNotNone(self.active('ability.thrp.nf.b'))
        self.assertIsNotNone(self.active('ability.thrp.nf.e'))
        self.assertIsNone(self.active('ability.thrp.fl.three'))
        flagged = [
            self.make_video(level=level, bv=120, left_ce=80, right_ce=20, upload_time=self.later)
            for level in ('b', 'i', 'e')
        ]
        evaluate_player(self.user.id)
        self.assertEqual(self.active('ability.thrp.fl.three').stage, to_units(1.2, THRP_SCALE))
        self.assertIsNotNone(self.active('ability.thrp.fl.b'))
        self.delete_video(expert.id)
        evaluate_player(self.user.id)
        self.assertIsNone(self.active('ability.thrp.nf.three'))
        self.assertIsNotNone(self.active('ability.thrp.nf.b'))
        self.assertIsNotNone(self.active('ability.thrp.nf.i'))
        self.assertIsNone(self.active('ability.thrp.nf.e'))
        self.assertEqual(len(flagged), 3)

    def test_novice_realname_review_levels_and_modes(self):
        evaluate_player(self.user.id)
        self.assertIsNone(self.active(NOVICE_REALNAME))
        self.assertIsNone(self.active(NOVICE_REVIEW))
        self.make_video(level=MS_TextChoices.Level.CUSTOM_8_8_40, mode='00')
        evaluate_player(self.user.id)
        self.assertIsNotNone(self.active(NOVICE_REVIEW))
        self.assertIsNone(self.active(NOVICE_LEVELS))
        self.make_video(level='b', right_ce=1)
        self.make_video(level='i', right_ce=1)
        evaluate_player(self.user.id)
        self.assertIsNone(self.active(NOVICE_LEVELS))
        self.make_video(level='e', right_ce=1)
        evaluate_player(self.user.id)
        self.assertIsNotNone(self.active(NOVICE_LEVELS))
        self.assertIsNone(self.active(NOVICE_LEVELS_NF))
        for level in ('b', 'i', 'e'):
            self.make_video(level=level, right_ce=0)
        evaluate_player(self.user.id)
        self.assertIsNotNone(self.active(NOVICE_LEVELS_NF))
        modes = open_modes()
        for mode in modes[:-1]:
            if mode == '00':
                continue
            self.make_video(mode=mode, level='b')
        evaluate_player(self.user.id)
        self.assertIsNone(self.active(NOVICE_MODES))
        self.make_video(mode=modes[-1], level='b')
        evaluate_player(self.user.id)
        self.assertIsNotNone(self.active(NOVICE_MODES))
        self.user.realname = '实名玩家'
        self.user.save(update_fields=['_realname', 'date_updated'])
        evaluate_player(self.user.id)
        self.assertIsNotNone(self.active(NOVICE_REALNAME))
        self.user.realname = '匿名'
        self.user.save(update_fields=['_realname', 'date_updated'])
        evaluate_player(self.user.id)
        self.assertIsNone(self.active(NOVICE_REALNAME))

    def test_saolei_link_grants_only_when_verified(self):
        AccountLinkQueue.objects.create(platform=Platform.BILIBILI, identifier='bili-basic', userprofile=self.user, verified=True)
        AccountLinkQueue.objects.create(platform=Platform.SAOLEI, identifier='saolei-basic', userprofile=self.user, verified=False)
        evaluate_player(self.user.id)
        self.assertIsNone(self.active(NOVICE_SAOLEI))
        self.assertFalse(MedalDefinition.objects.exclude(code=NOVICE_SAOLEI).filter(metric='platform').exists())
        self.assertEqual(MedalDefinition.objects.get(code=NOVICE_SAOLEI).series, Medal_TextChoices.Series.SAOLEI)
        link = AccountLinkQueue.objects.get(platform=Platform.SAOLEI, userprofile=self.user)
        link.verified = True
        link.save(update_fields=['verified'])
        evaluate_player(self.user.id)
        self.assertIsNotNone(self.active(NOVICE_SAOLEI))
        link.verified = False
        link.save(update_fields=['verified'])
        evaluate_player(self.user.id)
        self.assertIsNone(self.active(NOVICE_SAOLEI))
        link.verified = True
        link.save(update_fields=['verified'])
        evaluate_player(self.user.id)
        link.delete()
        evaluate_player(self.user.id)
        self.assertIsNone(self.active(NOVICE_SAOLEI))

    def test_ongoing_and_nonstandard_videos_skip_pb(self):
        self.make_video(timems=1000, ongoing=True)
        self.make_video(timems=1000, mode='05')
        evaluate_player(self.user.id)
        self.assertIsNone(self.active('ability.time.b'))
        self.make_video(timems=19000)
        evaluate_player(self.user.id)
        self.assertEqual(self.active('ability.time.b').stage, 20000)

    def test_profile_and_saolei_link_enqueue_after_commit(self):
        path = task_refresh_player_medals.module_path
        with self.captureOnCommitCallbacks(execute=True):
            AccountLinkQueue.objects.create(platform=Platform.BILIBILI, identifier='bili-signal', userprofile=self.user, verified=True)
        self.assertFalse(DBTaskResult.objects.filter(task_path=path, status=TaskResultStatus.READY).exists())
        with self.captureOnCommitCallbacks(execute=True):
            self.user.realname = '信号实名'
            self.user.save(update_fields=['_realname', 'date_updated'])
        self.assertEqual(DBTaskResult.objects.filter(task_path=path, status=TaskResultStatus.READY).count(), 1)
        DBTaskResult.objects.filter(task_path=path).delete()
        with self.captureOnCommitCallbacks(execute=True):
            link = AccountLinkQueue.objects.create(platform=Platform.SAOLEI, identifier='saolei-signal', userprofile=self.user, verified=True)
        self.assertEqual(DBTaskResult.objects.filter(task_path=path, status=TaskResultStatus.READY).count(), 1)
        DBTaskResult.objects.filter(task_path=path).delete()
        with self.captureOnCommitCallbacks(execute=True):
            link.delete()
        self.assertEqual(DBTaskResult.objects.filter(task_path=path, status=TaskResultStatus.READY).count(), 1)

    def test_staff_rebuild_is_low_priority(self):
        staff = UserProfile.objects.create_user(username='medal_basic_staff', email='medal-basic-staff@example.com', password='password', is_staff=True)
        self.client.force_login(staff)
        body = json.dumps({'user_id': self.user.id})
        self.assertEqual(self.client.post('/api/medal/staff/rebuild', data=body, content_type='application/json').status_code, 200)
        self.assertEqual(self.client.post('/api/medal/staff/rebuild', data=body, content_type='application/json').status_code, 200)
        rows = DBTaskResult.objects.filter(task_path=task_backfill_player_medals.module_path, status=TaskResultStatus.READY)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.get().priority, 0)
        self.assertEqual(rows.get().args_kwargs['args'], [self.user.id])
