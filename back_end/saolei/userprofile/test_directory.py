from datetime import datetime, timezone

from django.test import override_settings, TestCase
from django.utils.dateparse import parse_datetime

from accountlink.models import AccountLinkQueue, Platform
from msuser.models import UserMS
from userprofile.models import UserProfile


@override_settings(RATELIMIT_ENABLE=False)
class UserDirectoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alpha = UserProfile.objects.create_user(
            username='AlphaUser', email='directory-alpha@example.com',
            date_joined=datetime(2024, 1, 2, 3, 4, 5, 123000, tzinfo=timezone.utc),
            userms=UserMS.objects.create(video_num_total=4, video_num_tournament=1, video_size_total=100, video_size_tournament=900),
        )
        cls.beta = UserProfile.objects.create_user(
            username='BetaUser', email='directory-beta@example.com',
            userms=UserMS.objects.create(video_num_total=1, video_num_tournament=5, video_size_total=800, video_size_tournament=100),
        )
        cls.missing = UserProfile.objects.create_user(username='NoStats', email='directory-missing@example.com')
        cls.zero = UserProfile.objects.create_user(username='ZeroStats', email='directory-zero@example.com', userms=UserMS.objects.create())
        cls.negative = UserProfile.objects.create_user(
            username='PendingRecount', email='directory-negative@example.com',
            userms=UserMS.objects.create(video_num_total=-1, video_size_total=-8),
        )
        cls.linked = UserProfile.objects.create_user(
            username='LinkedAccount', email='directory-linked@example.com',
            userms=UserMS.objects.create(video_num_total=2, video_num_tournament=2, video_size_total=256, video_size_tournament=256),
        )
        cls.members = [cls.alpha, cls.beta, cls.missing, cls.zero, cls.negative, cls.linked]
        AccountLinkQueue.objects.bulk_create([
            AccountLinkQueue(userprofile=cls.alpha, platform=Platform.SAOLEI, identifier='101', verified=True),
            AccountLinkQueue(userprofile=cls.alpha, platform=Platform.MSGAMES, identifier='201', verified=True),
            AccountLinkQueue(userprofile=cls.alpha, platform=Platform.WOM, identifier='301', verified=True),
            AccountLinkQueue(userprofile=cls.alpha, platform=Platform.MINERACER, identifier='mr-alpha_01', verified=True),
            AccountLinkQueue(userprofile=cls.beta, platform=Platform.SAOLEI, identifier='102', verified=True),
            AccountLinkQueue(userprofile=cls.beta, platform=Platform.MSGAMES, identifier='202', verified=True),
            AccountLinkQueue(userprofile=cls.beta, platform=Platform.WOM, identifier='302', verified=True),
            AccountLinkQueue(userprofile=cls.beta, platform=Platform.MINERACER, identifier='mr-beta_02', verified=True),
            AccountLinkQueue(userprofile=cls.missing, platform=Platform.MINERACER, identifier='mr-pending_04', verified=False),
            AccountLinkQueue(userprofile=cls.linked, platform=Platform.BILIBILI, identifier='499', verified=True),
            AccountLinkQueue(userprofile=cls.linked, platform=Platform.QQ, identifier='12345678', verified=True),
            AccountLinkQueue(userprofile=cls.linked, platform=Platform.MINERACER, identifier='mr-linked_03', verified=True),
        ])

    def query(self, **params):
        return self.client.get('/api/userprofile/query', params)

    def test_public_fields_and_statistics_without_n_plus_one_queries(self):
        with self.assertNumQueries(3):
            response = self.query(page_size=100)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data['count'], 6)
        self.assertEqual([user['id'] for user in data['users']], [user.id for user in self.members])
        alpha = data['users'][0]
        self.assertEqual(set(alpha), {'id', 'date_joined', 'statistics', 'accounts', 'is_memorial'})
        self.assertEqual(parse_datetime(alpha['date_joined']), self.alpha.date_joined)
        self.assertEqual(alpha['statistics'], {
            'video_num_total': 4, 'video_num_tournament': 1, 'video_num_all': 5,
            'video_size_total': 100, 'video_size_tournament': 900, 'video_size_all': 1000,
        })
        self.assertEqual(alpha['accounts'], {'c': '101', 'a': '201', 'w': '301', 'm': 'mr-alpha_01'})
        self.assertEqual(data['users'][2]['accounts'], {})
        self.assertEqual(data['users'][5]['accounts'], {'m': 'mr-linked_03'})
        self.assertTrue(all(value == 0 for value in data['users'][2]['statistics'].values()))
        self.assertEqual(data['users'][4]['statistics']['video_size_all'], -8)

    def test_all_numeric_fields_sort_both_ways_with_stable_id_ties(self):
        fields = ['id', 'video_num_total', 'video_num_tournament', 'video_num_all', 'video_size_total', 'video_size_tournament', 'video_size_all']
        for field in fields:
            for reverse in (False, True):
                with self.subTest(field=field, reverse=reverse):
                    if field == 'id':
                        expected = sorted(self.members, key=lambda user: user.id, reverse=reverse)
                    else:
                        def key(user, field=field, reverse=reverse):
                            value = getattr(user.userms, field) if user.userms is not None else 0
                            return (-value if reverse else value, user.id)
                        expected = sorted(self.members, key=key)
                    response = self.query(sort=field, reverse=reverse, page_size=100)
                    self.assertEqual(response.status_code, 200, response.content)
                    self.assertEqual([user['id'] for user in response.json()['users']], [user.id for user in expected])

    def test_site_id_and_platform_ids_match_exactly(self):
        for platform, term in [('', self.alpha.id), ('c', '101'), ('a', '201'), ('w', '301'), ('m', 'mr-alpha_01')]:
            with self.subTest(platform=platform):
                response = self.query(platform=platform, id=term)
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual([user['id'] for user in response.json()['users']], [self.alpha.id])
        self.assertEqual(self.query(platform='c', id='10').json()['count'], 0)
        self.assertEqual(self.query(platform='m', id='mr-alpha').json()['count'], 0)
        self.assertEqual(self.query(id=9223372036854775807).json()['count'], 0)
        self.assertEqual([user['id'] for user in self.query(id=self.alpha.id).json()['users']], [self.alpha.id])

    def test_unverified_links_cannot_be_queried_or_displayed(self):
        self.assertEqual(self.query(platform='m', id='mr-pending_04').json(), {'count': 0, 'users': []})
        self.assertEqual(self.query(id=self.missing.id).json()['users'][0]['accounts'], {})

    def test_duplicate_links_do_not_duplicate_users_or_change_pagination(self):
        AccountLinkQueue.objects.create(userprofile=self.alpha, platform=Platform.SAOLEI, identifier='101', verified=True)
        response = self.query(platform='c', id='101', page_size=1).json()
        self.assertEqual(response['count'], 1)
        self.assertEqual([user['id'] for user in response['users']], [self.alpha.id])

    def test_pagination_and_empty_results(self):
        response = self.query(page=2, page_size=2)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['count'], 6)
        self.assertEqual([user['id'] for user in response.json()['users']], [self.missing.id, self.zero.id])
        self.assertEqual(self.query(page=100, page_size=20).json(), {'count': 6, 'users': []})
        self.assertEqual(self.query(platform='c', id='99999').json(), {'count': 0, 'users': []})
        self.assertEqual(self.query(id='').json()['count'], 6)
        self.assertEqual(self.query(platform='m').json()['count'], 6)

    def test_validation_bounds_and_sort_allowlist(self):
        for params in [
            {'sort': '_realname'}, {'sort': 'userms__video_num_all'}, {'sort': '-id'},
            {'page': 0}, {'page': -1}, {'page_size': 0}, {'page_size': 101},
            {'id': 0}, {'id': -1}, {'id': 'abc'}, {'id': 9223372036854775808},
            {'platform': 'c', 'id': 'x'}, {'platform': 'a', 'id': '%'}, {'platform': 'w', 'id': '301 OR 1=1'},
            {'platform': 'm', 'id': 'x' * 65}, {'platform': 'c', 'id': '1' * 129},
            {'platform': 'B', 'id': '401'}, {'platform': 'q', 'id': '12345'}, {'id': '1,2'},
        ]:
            with self.subTest(params=params):
                self.assertEqual(self.query(**params).status_code, 422)
