from unittest.mock import patch

from django.conf import settings
from django.core.cache import caches
from django.db import transaction
from django.tasks import TaskResultStatus
from django.test import override_settings, TestCase
from django_redis import get_redis_connection
from django_tasks_db.models import DBTaskResult

from config.customranking import CUSTOM_PLUCK_LEVELS, CUSTOM_PLUCK_MODES
from config.text_choices import MS_TextChoices
from customranking.cache import PLuckRankingCache
from customranking.models import CustomPluckRecord
from msuser.models import UserMS
from userprofile.models import UserProfile
from videomanager.models import ExpandVideoModel, VideoModel
from .models import Identifier
from .services import bind_identifier, set_safe, unbind_identifier
from .tasks import task_sync_identifier_videos


@override_settings(RATELIMIT_ENABLE=False)
class IdentifierQueryTest(TestCase):
    def setUp(self):
        self.userms = UserMS.objects.create(identifiers=['Public identifier'])
        self.user = UserProfile.objects.create_user(username='identifier_query_user', email='identifier-query@example.com', userms=self.userms)
        Identifier.objects.create(identifier='Public identifier', safe=True, userms=self.userms)
        Identifier.objects.create(identifier='Unbound identifier', safe=True)
        Identifier.objects.create(identifier='Unapproved identifier', safe=False)

    def query(self, text, mode='exact'):
        return self.client.get(f'/api/identifier/query/{mode}', {'identifier': text})

    def test_public_lookup_ownership_and_visibility(self):
        cases = [
            ('Public identifier', [{'identifier': 'Public identifier', 'user_id': self.user.id}]),
            ('Unbound identifier', [{'identifier': 'Unbound identifier', 'user_id': None}]),
            ('Missing identifier', []), ('Unapproved identifier', []),
        ]
        for text, items in cases:
            with self.subTest(text=text):
                response = self.query(text)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {'items': items})

    def test_staff_can_query_unsafe_identifiers_and_receive_safe(self):
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        self.client.force_login(self.user)
        for mode in ['exact', 'iexact', 'contains', 'icontains', 'startswith', 'istartswith', 'endswith', 'iendswith', 'regex']:
            with self.subTest(mode=mode):
                response = self.query('Unapproved identifier', mode)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['items'], [{'identifier': 'Unapproved identifier', 'user_id': None, 'safe': False}])
        self.assertEqual(self.query('Public identifier').json()['items'], [{'identifier': 'Public identifier', 'user_id': self.user.id, 'safe': True}])

    def test_normal_user_still_cannot_query_unsafe_identifiers(self):
        self.client.force_login(self.user)
        self.assertEqual(self.query('Unapproved identifier').json()['items'], [])
        self.assertNotIn('safe', self.query('Public identifier').json()['items'][0])

    def test_lookup_is_exact_and_preserves_special_characters(self):
        text = ' 玩家 & + '
        Identifier.objects.create(identifier=text, safe=True, userms=self.userms)
        self.assertEqual(self.query(text).json()['items'], [{'identifier': text, 'user_id': self.user.id}])

    def test_identifier_is_required_and_length_is_valid(self):
        for text in ['', 'x' * 129]:
            with self.subTest(text=text):
                self.assertEqual(self.query(text).status_code, 400)

        self.assertEqual(self.client.get('/api/identifier/query/exact').status_code, 422)

    def test_all_matching_modes(self):
        texts = ['AlphaBeta', 'alphabeta', 'XAlphaBetaY', 'alphabetaTail', 'Headalphabeta']
        Identifier.objects.bulk_create([Identifier(identifier=text, safe=True) for text in texts])
        cases = [
            ('exact', 'AlphaBeta', ['AlphaBeta']),
            ('exact', 'Alpha', []), ('exact', 'alphabeta', ['alphabeta']),
            ('iexact', 'ALPHABETA', ['AlphaBeta', 'alphabeta']),
            ('contains', 'AlphaBeta', ['AlphaBeta', 'XAlphaBetaY']),
            ('icontains', 'ALPHABETA', texts),
            ('startswith', 'Alpha', ['AlphaBeta']),
            ('istartswith', 'ALPHA', ['AlphaBeta', 'alphabeta', 'alphabetaTail']),
            ('endswith', 'Beta', ['AlphaBeta']),
            ('iendswith', 'BETA', ['AlphaBeta', 'alphabeta', 'Headalphabeta']),
            ('regex', '^Alpha.*Beta$', ['AlphaBeta']),
            ('regex', '(?i)^alpha.*beta$', ['AlphaBeta', 'alphabeta']),
        ]
        for mode, text, expected in cases:
            with self.subTest(mode=mode):
                response = self.query(text, mode)
                self.assertEqual(response.status_code, 200)
                self.assertEqual([item['identifier'] for item in response.json()['items']], expected)

    def test_case_insensitive_matching_preserves_accents(self):
        Identifier.objects.bulk_create([Identifier(identifier=text, safe=True) for text in ['Éclair', 'éclair', 'eclair']])
        response = self.query('ÉCLAIR', 'iexact')
        self.assertEqual([item['identifier'] for item in response.json()['items']], ['Éclair', 'éclair'])

    def test_plain_modes_escape_like_wildcards(self):
        Identifier.objects.bulk_create([Identifier(identifier=text, safe=True) for text in ['token%_\\value', 'tokenABvalue']])
        for mode in ['contains', 'icontains']:
            with self.subTest(mode=mode):
                response = self.query('%_\\', mode)
                self.assertEqual([item['identifier'] for item in response.json()['items']], ['token%_\\value'])

    def test_invalid_regular_expression(self):
        self.assertEqual(self.query('[', 'regex').status_code, 400)

    def test_all_1000_matches_are_returned_with_owners_in_one_query(self):
        Identifier.objects.bulk_create([Identifier(identifier=f'limit-{index:04}-limit', safe=True, userms=self.userms) for index in range(1000)])
        Identifier.objects.create(identifier='limit-unapproved-limit', safe=False)
        with self.assertNumQueries(1):
            response = self.query('limit-', 'startswith')
        self.assertEqual(response.status_code, 200)
        expected = [{'identifier': f'limit-{index:04}-limit', 'user_id': self.user.id} for index in range(1000)]
        self.assertEqual(response.json(), {'items': expected})

    def test_over_1000_matches_are_rejected_without_partial_results(self):
        Identifier.objects.bulk_create([Identifier(identifier=f'limit-{index:04}-limit', safe=True) for index in range(1001)])
        cases = [
            ('contains', 'limit'), ('icontains', 'LIMIT'), ('startswith', 'limit-'), ('istartswith', 'LIMIT-'),
            ('endswith', '-limit'), ('iendswith', '-LIMIT'), ('regex', '^limit-'),
        ]
        for mode, text in cases:
            with self.subTest(mode=mode), self.assertNumQueries(1):
                response = self.query(text, mode)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['code'], 'too_many_matches')
                self.assertIn('1000', response.json()['detail'])
                self.assertNotIn('items', response.json())

    def test_case_insensitive_exact_matching_also_has_a_total_limit(self):
        texts = [''.join('a' if bit == '0' else 'A' for bit in f'{index:010b}') for index in range(1001)]
        Identifier.objects.bulk_create([Identifier(identifier=text, safe=True) for text in texts])
        response = self.query('a' * 10, 'iexact')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'too_many_matches')
        exact = self.query('a' * 10)
        self.assertEqual(exact.status_code, 200)
        self.assertEqual(exact.json()['items'], [{'identifier': 'a' * 10, 'user_id': None}])

    def test_unknown_mode(self):
        self.assertEqual(self.query('Public', 'unknown').status_code, 404)

    def test_per_mode_rate_limits(self):
        test_caches = {
            **settings.CACHES,
            'identifier-limits': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'identifier-limit-tests',
            },
        }
        with self.settings(RATELIMIT_ENABLE=True, RATELIMIT_USE_CACHE='identifier-limits', CACHES=test_caches), patch('django_ratelimit.core.time.time', return_value=1800000000):
            limits = {'exact': 2, 'startswith': 10, 'iexact': 6, 'contains': 6, 'icontains': 6, 'istartswith': 6, 'endswith': 6, 'iendswith': 6, 'regex': 2}
            for mode, limit in limits.items():
                with self.subTest(mode=mode):
                    caches['identifier-limits'].clear()
                    for _ in range(limit):
                        self.assertEqual(self.query('Public', mode).status_code, 200)
                    with self.assertNumQueries(0):
                        self.assertEqual(self.query('Public', mode).status_code, 429)

    def test_expensive_modes_share_limits_and_other_ips_are_independent(self):
        test_caches = {
            **settings.CACHES,
            'identifier-limits': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'identifier-shared-limit-tests',
            },
        }
        with self.settings(RATELIMIT_ENABLE=True, RATELIMIT_USE_CACHE='identifier-limits', CACHES=test_caches), patch('django_ratelimit.core.time.time', return_value=1800000000):
            caches['identifier-limits'].clear()
            for mode in ['iexact', 'contains', 'icontains', 'istartswith', 'endswith', 'iendswith']:
                self.assertEqual(self.query('Public', mode).status_code, 200)
            self.assertEqual(self.query('Public', 'contains').status_code, 429)
            for _ in range(2):
                self.assertEqual(self.query('Public', 'regex').status_code, 200)
            self.assertEqual(self.query('Public', 'regex').status_code, 429)
            self.assertEqual(self.query('Public', 'exact').status_code, 200)
            self.assertEqual(self.query('Public', 'startswith').status_code, 200)
            response = self.client.get('/api/identifier/query/contains', {'identifier': 'Public'}, REMOTE_ADDR='192.0.2.42')
            self.assertEqual(response.status_code, 200)

    def test_player_lookup(self):
        response = self.client.get('/api/userprofile/identifier', {'user_id': self.user.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), ['Public identifier'])

    def test_player_without_minesweeper_profile(self):
        user = UserProfile.objects.create_user(username='identifier_query_no_ms', email='identifier-no-ms@example.com')
        response = self.client.get('/api/userprofile/identifier', {'user_id': user.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])


class IdentifierAdminApiTest(TestCase):
    def setUp(self):
        self.staff = UserProfile.objects.create_user(username='identifier_admin', email='identifier-admin@example.com', is_staff=True)
        self.userms = UserMS.objects.create()
        self.user = UserProfile.objects.create_user(username='identifier_owner', email='identifier-owner@example.com', userms=self.userms)
        self.client.force_login(self.staff)

    def post(self, path, **data):
        return self.client.post(f'/api/identifier/{path}', data)

    def test_review_bind_unbind_and_reject_unsafe_bound_identifier(self):
        identifier = Identifier.objects.create(identifier='review me', safe=False)
        self.assertEqual(self.post('bind', identifier=identifier.identifier, id=self.user.id).status_code, 409)
        self.assertEqual(self.post('safe', identifier=identifier.identifier, safe=True).status_code, 200)
        response = self.post('bind', identifier=identifier.identifier, id=self.user.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'identifier': identifier.identifier, 'user_id': self.user.id, 'safe': True})
        self.userms.refresh_from_db()
        self.assertIn(identifier.identifier, self.userms.identifiers)

        self.assertEqual(self.post('safe', identifier=identifier.identifier, safe=False).status_code, 409)
        identifier.refresh_from_db()
        self.assertTrue(identifier.safe)
        self.assertEqual(identifier.userms_id, self.userms.id)

        for _ in range(2):
            response = self.post('bind', identifier=identifier.identifier, id=0)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'identifier': identifier.identifier, 'user_id': None, 'safe': True})
        self.userms.refresh_from_db()
        self.assertNotIn(identifier.identifier, self.userms.identifiers)
        self.assertEqual(self.post('safe', identifier=identifier.identifier, safe=False).status_code, 200)
        identifier.refresh_from_db()
        self.assertFalse(identifier.safe)
        self.assertIsNone(identifier.userms_id)

    def test_binding_creates_new_identifier_and_rejects_owner_conflicts(self):
        response = self.post('bind', identifier='new identifier', id=self.user.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user_id'], self.user.id)
        self.assertTrue(response.json()['safe'])
        other = UserProfile.objects.create_user(username='identifier_other', email='identifier-other@example.com', userms=UserMS.objects.create())
        self.assertEqual(self.post('bind', identifier='new identifier', id=other.id).status_code, 409)
        self.assertEqual(self.post('bind', identifier='new identifier', id=self.user.id).status_code, 200)

    def test_invalid_bindings_do_not_create_identifiers(self):
        for user_id, status in [(-1, 422), ('invalid', 422), (0, 404), (999999999, 404), (self.staff.id, 400)]:
            with self.subTest(user_id=user_id):
                self.assertEqual(self.post('bind', identifier='not created', id=user_id).status_code, status)
                self.assertFalse(Identifier.objects.filter(identifier='not created').exists())
        for path in ['bind', 'safe']:
            self.assertEqual(self.post(path, identifier='', id=0, safe=True).status_code, 422)

    def test_admin_player_query_includes_safe_and_unsafe_rows(self):
        Identifier.objects.create(identifier='approved', safe=True, userms=self.userms)
        Identifier.objects.create(identifier='legacy unsafe', safe=False, userms=self.userms)
        response = self.client.get(f'/api/identifier/query/user/{self.user.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['items'], [
            {'identifier': 'approved', 'user_id': self.user.id, 'safe': True},
            {'identifier': 'legacy unsafe', 'user_id': self.user.id, 'safe': False},
        ])

    def test_admin_endpoints_require_staff_and_old_mutation_routes_are_removed(self):
        for user in [None, self.user]:
            if user is None:
                self.client.logout()
            else:
                self.client.force_login(user)
            for path in ['bind', 'safe']:
                self.assertEqual(self.post(path, identifier='protected', id=0, safe=True).status_code, 403)
            self.assertEqual(self.client.get(f'/api/identifier/query/user/{self.user.id}').status_code, 403)
        self.client.force_login(self.staff)
        for path in ['del/staff/', 'add/staff/', 'approve/staff/']:
            self.assertEqual(self.client.post(f'/identifier/{path}', {'identifier': 'removed'}).status_code, 404)


class BindIdentifierServiceTest(TestCase):
    def setUp(self):
        self.userms = UserMS.objects.create()
        self.user = UserProfile.objects.create_user(
            username='identifier_service_user',
            email='identifier_service@example.com',
            password='password',
            userms=self.userms,
        )

    def tearDown(self):
        cache = get_redis_connection('saolei_website')
        cache.delete('newest_queue', 'freeze_queue', 'review_queue')
        for level in CUSTOM_PLUCK_LEVELS:
            PLuckRankingCache(level).flush()

    def create_video(self, identifier: str, *, level=MS_TextChoices.Level.BEGINNER, mode=MS_TextChoices.Mode.STD, pluck=None):
        expand_video = ExpandVideoModel.objects.create(identifier=identifier)
        return VideoModel.objects.create(
            player=self.user,
            file='videos/test.evf',
            video=expand_video,
            state=MS_TextChoices.State.IDENTIFIER,
            software=MS_TextChoices.Software.EVF,
            level=level,
            mode=mode,
            timems=10000,
            bv=50,
            left=1,
            right=1,
            double=1,
            left_ce=1,
            right_ce=1,
            double_ce=1,
            path=20,
            pluck=pluck,
        )

    def sync_pending_videos(self):
        queued = list(DBTaskResult.objects.filter(
            task_path=task_sync_identifier_videos.module_path,
            status=TaskResultStatus.READY,
        ).order_by('id'))
        for row in queued:
            with self.captureOnCommitCallbacks(execute=True):
                task_sync_identifier_videos.call(*row.args_kwargs['args'])
            DBTaskResult.objects.filter(pk=row.pk).update(status=TaskResultStatus.SUCCESSFUL)
        return len(queued)

    def bind_and_sync(self, identifier, userms):
        with self.captureOnCommitCallbacks(execute=True):
            changed_count = bind_identifier(identifier, userms)
        self.sync_pending_videos()
        return changed_count

    def unbind_and_sync(self, identifier, userms=None):
        with self.captureOnCommitCallbacks(execute=True):
            changed_count = unbind_identifier(identifier, userms)
        self.sync_pending_videos()
        return changed_count

    def test_bind_and_unbind_identifier_bulk_update_video_states(self):
        identifier = Identifier.objects.create(identifier='classic-id', safe=True)
        video = self.create_video('classic-id')

        changed_count = self.bind_and_sync(identifier, self.userms)

        identifier.refresh_from_db()
        video.refresh_from_db()
        self.userms.refresh_from_db()
        self.assertEqual(changed_count, 1)
        self.assertEqual(identifier.userms_id, self.userms.id)
        self.assertIn(identifier.identifier, self.userms.identifiers)
        self.assertEqual(video.state, MS_TextChoices.State.OFFICIAL)

        changed_count = self.unbind_and_sync(identifier, self.userms)

        video.refresh_from_db()
        self.userms.refresh_from_db()
        self.assertEqual(changed_count, 1)
        self.assertEqual(video.state, MS_TextChoices.State.IDENTIFIER)
        self.assertNotIn(identifier.identifier, self.userms.identifiers)

    def test_bind_only_enqueues_sync_and_worker_updates_videos(self):
        identifier = Identifier.objects.create(identifier='queued-id', safe=True)
        video = self.create_video('queued-id')

        with self.captureOnCommitCallbacks(execute=True):
            changed_count = bind_identifier(identifier, self.userms)

        self.assertEqual(changed_count, 1)
        video.refresh_from_db()
        self.assertEqual(video.state, MS_TextChoices.State.IDENTIFIER)
        queued = DBTaskResult.objects.get(task_path=task_sync_identifier_videos.module_path)
        self.assertEqual(queued.args_kwargs['args'], ['queued-id', self.user.id])
        self.assertEqual(self.sync_pending_videos(), 1)
        video.refresh_from_db()
        self.assertEqual(video.state, MS_TextChoices.State.OFFICIAL)

    def test_pending_bind_and_unbind_tasks_converge_to_current_binding(self):
        identifier = Identifier.objects.create(identifier='converge-id', safe=True)
        video = self.create_video('converge-id')

        with self.captureOnCommitCallbacks(execute=True):
            bind_identifier(identifier, self.userms)
        with self.captureOnCommitCallbacks(execute=True):
            unbind_identifier(identifier, self.userms)

        self.assertEqual(self.sync_pending_videos(), 2)
        video.refresh_from_db()
        self.assertEqual(video.state, MS_TextChoices.State.IDENTIFIER)

    def test_rolled_back_binding_does_not_enqueue_sync(self):
        identifier = Identifier.objects.create(identifier='rollback-id', safe=True)
        self.create_video('rollback-id')

        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    bind_identifier(identifier, self.userms)
                    raise RuntimeError('rollback')

        self.assertFalse(DBTaskResult.objects.filter(task_path=task_sync_identifier_videos.module_path).exists())
        self.assertFalse(VideoModel.objects.filter(state=MS_TextChoices.State.OFFICIAL).exists())

    def test_bind_identifier_bulk_updates_custom_pluck_record(self):
        identifier = Identifier.objects.create(identifier='custom-id', safe=True)
        video = self.create_video(
            'custom-id',
            level=next(iter(CUSTOM_PLUCK_LEVELS)),
            mode=next(iter(CUSTOM_PLUCK_MODES)),
            pluck=0.25,
        )

        self.bind_and_sync(identifier, self.userms)

        video.refresh_from_db()
        self.assertEqual(video.state, MS_TextChoices.State.OFFICIAL)
        record = CustomPluckRecord.objects.get(player=self.user, level=video.level)
        self.assertEqual(record.video_id, video.id)
        self.assertEqual(record.pluck, video.pluck)

        self.unbind_and_sync(identifier, self.userms)

        video.refresh_from_db()
        self.assertEqual(video.state, MS_TextChoices.State.IDENTIFIER)
        self.assertFalse(CustomPluckRecord.objects.filter(player=self.user, level=video.level).exists())

    def test_set_safe_updates_unbound_identifier(self):
        identifier = Identifier.objects.create(identifier='review-id', safe=False)

        set_safe(identifier, True)
        identifier.refresh_from_db()
        self.assertTrue(identifier.safe)

        set_safe(identifier, False)
        identifier.refresh_from_db()
        self.assertFalse(identifier.safe)

    def test_set_safe_rejects_bound_identifier_marked_unsafe(self):
        identifier = Identifier.objects.create(identifier='bound-id', safe=True, userms=self.userms)

        with self.assertRaises(ValueError):
            set_safe(identifier, False)

        identifier.refresh_from_db()
        self.assertTrue(identifier.safe)
        self.assertEqual(identifier.userms_id, self.userms.id)
