from .base import (
    cache,
    call_command,
    DBTaskResult,
    GSC_Defaults,
    gsc_encode_best,
    GSCTournament,
    MAX_TOURNAMENT_BEST,
    NORMAL_TOURNAMENT_CACHE_KEY,
    StringIO,
    timedelta,
    timezone,
    Tournament_TextChoices,
    TournamentTestCaseBase,
    TournamentUser,
    UserMS,
    UserProfile,
    weekly_encode_best,
    WeeklyTournament,
)


class TestApi(TournamentTestCaseBase):
    def test_tournament_ninja_api_serializes_gsc_tournament(self):
        list_response = self.client.get('/api/tournament/get_list', {'category': 'normal'})
        detail_response = self.client.get('/api/tournament/get', {'tournament_id': self.tournament.id})

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(list_response.json()[0]['id'], self.tournament.id)
        self.assertEqual(list_response.json()[0]['state'], Tournament_TextChoices.State.NORMAL)
        self.assertEqual(list_response.json()[0]['subclass'], Tournament_TextChoices.Subclass.GSC)
        self.assertEqual(list_response.json()[0]['data']['order'], self.tournament.order)
        self.assertIsNone(list_response.json()[0]['host_id'])
        self.assertEqual(detail_response.json()['id'], self.tournament.id)
        self.assertEqual(detail_response.json()['subclass'], Tournament_TextChoices.Subclass.GSC)
        self.assertEqual(detail_response.json()['data']['order'], self.tournament.order)
        self.assertIsNone(detail_response.json()['host_id'])

    def test_tournament_ninja_normal_list_uses_cache_without_db_fallback(self):
        cache.delete(NORMAL_TOURNAMENT_CACHE_KEY)

        response = self.client.get('/api/tournament/get_list', {'category': 'normal'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_tournament_ninja_list_filters_by_category(self):
        now = timezone.now()
        awarded_tournament = GSCTournament.objects.create(
            order=3,
            _token='G33333',
            start_time=now - timedelta(hours=3),
            end_time=now - timedelta(hours=2),
            state=Tournament_TextChoices.State.AWARDED,
        )
        pending_tournament = GSCTournament.objects.create(
            order=4,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            state=Tournament_TextChoices.State.PENDING,
        )

        normal_response = self.client.get('/api/tournament/get_list', {'category': 'normal'})
        awarded_response = self.client.get('/api/tournament/get_list', {'category': 'awarded'})
        other_response = self.client.get('/api/tournament/get_list', {'category': 'other'})
        all_response = self.client.get('/api/tournament/get_list', {'category': 'all'})

        self.assertEqual(normal_response.status_code, 200)
        self.assertEqual(awarded_response.status_code, 200)
        self.assertEqual(other_response.status_code, 200)
        self.assertEqual(all_response.status_code, 200)
        self.assertEqual({item['id'] for item in normal_response.json()}, {self.tournament.id})
        self.assertEqual({item['id'] for item in awarded_response.json()}, {awarded_tournament.id})
        self.assertEqual({item['id'] for item in other_response.json()}, {pending_tournament.id})
        self.assertEqual(
            {item['id'] for item in all_response.json()},
            {self.tournament.id, awarded_tournament.id, pending_tournament.id},
        )

    def test_tournament_user_ranking_api_sorts_best_fields_ascending(self):
        better_user = self.create_user('tournament_rank_best_better')
        worse_user = self.create_user('tournament_rank_best_worse')
        default_user = self.create_user('tournament_rank_best_default')
        better_score = TournamentUser.objects.create(
            user=better_user,
            gsc_best=gsc_encode_best(1000, 2),
            weekly_classic_best=weekly_encode_best(3000, 2026, 1),
        )
        worse_score = TournamentUser.objects.create(
            user=worse_user,
            gsc_best=gsc_encode_best(2000, 1),
            weekly_classic_best=weekly_encode_best(4000, 2026, 1),
        )
        default_score = TournamentUser.objects.create(
            user=default_user,
            gsc_best=MAX_TOURNAMENT_BEST,
            weekly_classic_best=MAX_TOURNAMENT_BEST,
        )
        self.tournament_cache.update_tournament_users([better_score, worse_score, default_score])

        response = self.client.get('/api/tournament/user-ranking', {
            'sort_by': 'gsc_best',
            'start': 0,
            'end': 20,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total'], 2)
        self.assertEqual([item['user_id'] for item in response.json()['data']], [better_user.id, worse_user.id])
        self.assertEqual(response.json()['data'][0]['gsc_best'], gsc_encode_best(1000, 2))
        self.assertEqual(response.json()['data'][0]['weekly_classic_best'], weekly_encode_best(3000, 2026, 1))

    def test_tournament_user_ranking_api_rejects_invalid_sort_field(self):
        response = self.client.get('/api/tournament/user-ranking', {
            'sort_by': 'invalid',
        })

        self.assertEqual(response.status_code, 400)

    def test_tournament_ninja_validate_saves_gsc_changes(self):
        now = timezone.now()
        tournament = GSCTournament.objects.create(
            order=3,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            state=Tournament_TextChoices.State.PENDING,
        )
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff', 'date_updated'])
        self.client.force_login(self.user)

        response = self.client.post('/api/tournament/validate', {
            'id': tournament.id,
            'valid': 'true',
        })

        self.assertEqual(response.status_code, 200)
        tournament.refresh_from_db()
        self.assertEqual(tournament.state, Tournament_TextChoices.State.NORMAL)
        self.assertTrue(tournament._token.startswith('G'))
        self.assertEqual(tournament.token, '')

    def test_new_gsc_tournament_api_creates_pending_without_token(self):
        admin = UserProfile.objects.create_user(
            id=GSC_Defaults.HOST_ID,
            username='gsc_admin',
            email='gsc_admin@example.com',
            password='password',
            userms=UserMS.objects.create(),
        )
        self.client.force_login(admin)
        now = timezone.now()

        response = self.client.post('/api/tournament/gsc/new', {
            'id': 9,
            'start_time': (now + timedelta(hours=1)).isoformat(),
            'end_time': (now + timedelta(hours=2)).isoformat(),
        })

        self.assertEqual(response.status_code, 200)
        tournament = GSCTournament.objects.get(order=9)
        self.assertEqual(tournament.state, Tournament_TextChoices.State.PENDING)
        self.assertEqual(tournament.token, '')

    def test_gsc_finish_api_reuses_existing_task(self):
        admin = UserProfile.objects.create_user(
            id=GSC_Defaults.HOST_ID,
            username='gsc_admin',
            email='gsc_admin@example.com',
            password='password',
            userms=UserMS.objects.create(),
        )
        self.client.force_login(admin)
        GSCTournament.objects.filter(pk=self.tournament.pk).update(
            end_time=timezone.now() - timedelta(minutes=1),
        )

        no_task_response = self.client.get('/api/tournament/gsc/task', {'order': self.tournament.order})
        first_response = self.client.post('/api/tournament/gsc/task/finish', {'order': self.tournament.order})
        second_response = self.client.post('/api/tournament/gsc/task/finish', {'order': self.tournament.order})

        self.assertEqual(no_task_response.status_code, 200)
        self.assertIsNone(no_task_response.json())
        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        first_task_id = first_response.json()['data']['task_id']
        second_task_id = second_response.json()['data']['task_id']
        self.assertEqual(first_task_id, second_task_id)
        self.tournament.refresh_from_db()
        self.assertEqual(str(self.tournament.task_id), first_task_id)
        self.assertEqual(
            DBTaskResult.objects.filter(
                task_path='tournament.gsc.tasks.task_gsc_finish',
            ).count(),
            1,
        )
        task_response = self.client.get('/api/tournament/gsc/task', {'order': self.tournament.order})
        self.assertEqual(task_response.status_code, 200)
        self.assertEqual(task_response.json()['id'], first_task_id)
        self.assertEqual(task_response.json()['status'], 'READY')

    def test_new_weekly_tournament_api_creates_next_week_normal_tournament(self):
        self.user.is_staff = True
        self.user.save(update_fields=['is_staff', 'date_updated'])
        self.client.force_login(self.user)

        response = self.client.post('/api/tournament/weekly/new', {
            'tournament_format': Tournament_TextChoices.WeeklyFormat.CLASSIC,
        })
        duplicate_response = self.client.post('/api/tournament/weekly/new', {
            'tournament_format': Tournament_TextChoices.WeeklyFormat.CLASSIC,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(duplicate_response.status_code, 409)
        tournament = WeeklyTournament.objects.get()
        self.assertEqual(tournament.state, Tournament_TextChoices.State.NORMAL)
        self.assertEqual(tournament.subclass, Tournament_TextChoices.Subclass.WEEKLY)
        self.assertEqual(tournament.host, self.user)
        self.assertEqual(tournament.weight, 50)
        self.assertEqual(tournament.start_time.weekday(), 0)
        self.assertEqual(tournament.end_time - tournament.start_time, timedelta(days=7))
        task = DBTaskResult.objects.get(task_path='tournament.weekly.tasks.task_weekly_finish')
        self.assertEqual(task.args_kwargs['args'], [tournament.id])
        self.assertEqual(task.run_after, tournament.end_time + timedelta(hours=1))
        self.assertNotIn('task', response.json())

    def test_weekly_set_api_only_updates_state(self):
        tournament = self.create_weekly_tournament(state=Tournament_TextChoices.State.CANCELLED)
        self.client.force_login(self.user)

        response = self.client.post('/api/tournament/weekly/set', {
            'id': tournament.id,
            'state': Tournament_TextChoices.State.NORMAL,
        })

        self.assertEqual(response.status_code, 200)
        tournament.refresh_from_db()
        self.assertEqual(tournament.state, Tournament_TextChoices.State.NORMAL)
        self.assertEqual(tournament.year, 2026)
        self.assertEqual(tournament.week, 1)

    def test_weekly_tournament_cache_and_rebuild_use_subclass_data(self):
        tournament = self.create_weekly_tournament(year=2027, week=3)
        self.tournament_cache.update_tournament(tournament)

        cached_tournament = self.tournament_cache.get_tournament(tournament.id)
        self.assertEqual(cached_tournament.subclass, Tournament_TextChoices.Subclass.WEEKLY)
        self.assertEqual(cached_tournament.data.year, 2027)
        self.assertEqual(cached_tournament.data.week, 3)

        cache.delete(NORMAL_TOURNAMENT_CACHE_KEY)
        call_command('rebuild_tournament_cache', stdout=StringIO())

        rebuilt_tournament = self.tournament_cache.get_tournament(tournament.id)
        self.assertEqual(rebuilt_tournament.subclass, Tournament_TextChoices.Subclass.WEEKLY)
        self.assertEqual(rebuilt_tournament.data.tournament_format, Tournament_TextChoices.WeeklyFormat.CLASSIC)
