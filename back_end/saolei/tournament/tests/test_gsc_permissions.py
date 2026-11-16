from .base import DBTaskResult, GSC_Defaults, GSCTournament, timedelta, timezone, Tournament_TextChoices, TournamentTestCaseBase, UserMS, UserProfile


class GscPermissionsTests(TournamentTestCaseBase):
    def setUp(self):
        super().setUp()
        self.host = UserProfile.objects.create_user(
            id=GSC_Defaults.HOST_ID, username='gsc_host', email='gsc_host@example.com',
            password='password', userms=UserMS.objects.create(),
        )
        self.staff = self.create_user('gsc_staff')
        self.staff.is_staff = True
        self.staff.save(update_fields=['is_staff', 'date_updated'])
        self.tournament.host = self.host
        self.tournament.end_time = timezone.now() - timedelta(minutes=1)
        self.tournament.save(update_fields=['host', 'end_time'])

    def test_host_and_staff_can_manage_gsc(self):
        for order, user in ((9, self.host), (10, self.staff)):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.post('/api/tournament/gsc/new', {'id': order})
                self.assertEqual(response.status_code, 200)
                created = GSCTournament.objects.get(order=order)
                self.assertEqual(created.host_id, user.id)
                self.assertEqual(created.state, Tournament_TextChoices.State.PENDING)

                start_time = timezone.now() - timedelta(hours=2)
                response = self.client.post('/api/tournament/set', {
                    'id': self.tournament.id, 'start_time': start_time.isoformat(),
                })
                self.assertEqual(response.status_code, 200)
                self.tournament.refresh_from_db()
                self.assertEqual(self.tournament.start_time, start_time)

                response = self.client.get('/api/tournament/gsc/task', {'order': self.tournament.order})
                self.assertEqual(response.status_code, 200)
                response = self.client.post('/api/tournament/gsc/task/finish', {'order': self.tournament.order})
                self.assertEqual(response.status_code, 200)
                task_id = response.json()['data']['task_id']
                response = self.client.get('/api/tournament/gsc/task', {'order': self.tournament.order})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['id'], task_id)
                self.assertEqual(response.json()['status'], 'READY')
                queued = DBTaskResult.objects.get(pk=task_id)
                self.assertEqual(queued.run_after, self.tournament.end_time + timedelta(hours=1))
        self.assertEqual(DBTaskResult.objects.filter(task_path='tournament.gsc.tasks.task_gsc_finish').count(), 1)

    def test_anonymous_and_unrelated_users_cannot_manage_gsc(self):
        original_start_time = self.tournament.start_time
        for user in (None, self.user):
            with self.subTest(user=user):
                if user is None:
                    self.client.logout()
                else:
                    self.client.force_login(user)
                self.assertEqual(self.client.post('/api/tournament/gsc/new', {'id': 9}).status_code, 403)
                self.assertEqual(self.client.get('/api/tournament/gsc/task', {'order': self.tournament.order}).status_code, 403)
                self.assertEqual(self.client.post('/api/tournament/gsc/task/finish', {'order': self.tournament.order}).status_code, 403)
                response = self.client.post('/api/tournament/set', {
                    'id': self.tournament.id, 'start_time': timezone.now().isoformat(),
                })
                self.assertEqual(response.status_code, 403)
        self.assertFalse(GSCTournament.objects.filter(order=9).exists())
        self.assertFalse(DBTaskResult.objects.filter(task_path='tournament.gsc.tasks.task_gsc_finish').exists())
        self.tournament.refresh_from_db()
        self.assertEqual(self.tournament.start_time, original_start_time)

    def test_restarting_finish_task_preserves_the_settlement_buffer(self):
        self.client.force_login(self.staff)
        response = self.client.post('/api/tournament/gsc/task/finish', {'order': self.tournament.order})
        task_id = response.json()['data']['task_id']
        DBTaskResult.objects.filter(pk=task_id).update(status='FAILED')
        response = self.client.post('/api/common/tasks/restart', {'task_id': task_id})
        self.assertEqual(response.status_code, 200, response.content)
        task = DBTaskResult.objects.get(pk=response.json()['id'])
        self.assertEqual(task.run_after, self.tournament.end_time + timedelta(hours=1))

    def test_staff_cannot_finish_gsc_before_end_time(self):
        self.client.force_login(self.staff)
        self.tournament.end_time = timezone.now() + timedelta(hours=1)
        self.tournament.save(update_fields=['end_time'])

        response = self.client.post('/api/tournament/gsc/task/finish', {'order': self.tournament.order})

        self.assertEqual(response.status_code, 403)
        self.assertFalse(DBTaskResult.objects.filter(task_path='tournament.gsc.tasks.task_gsc_finish').exists())

    def test_staff_access_does_not_change_weekly_set_permissions(self):
        tournament = self.create_weekly_tournament(host=self.host)
        self.client.force_login(self.staff)
        original_start_time = tournament.start_time

        response = self.client.post('/api/tournament/set', {
            'id': tournament.id, 'start_time': timezone.now().isoformat(),
        })

        self.assertEqual(response.status_code, 403)
        tournament.refresh_from_db()
        self.assertEqual(tournament.start_time, original_start_time)
