from django.tasks import TaskResultStatus
from django_tasks_db.models import DBTaskResult

from .tasks import enqueue_player_backfill, enqueue_player_refresh, player_refresh_pending
from .tests import MedalShellFixture


class MedalRefreshStatusTests(MedalShellFixture):
    def test_login_required(self):
        self.assertEqual(self.client.get('/api/medal/refresh-status').status_code, 403)

    def test_only_reads_one_query_and_never_enqueues_or_scans(self):
        with self.assertNumQueries(1):
            self.assertFalse(player_refresh_pending(self.user.id))
        self.assertFalse(DBTaskResult.objects.exists())

    def test_ready_running_and_finished_tasks(self):
        enqueue_player_refresh(self.user.id, video_ids=[123])
        row = DBTaskResult.objects.get()
        for status, expected in [
            (TaskResultStatus.READY, True), (TaskResultStatus.RUNNING, True),
            (TaskResultStatus.SUCCESSFUL, False), (TaskResultStatus.FAILED, False),
        ]:
            DBTaskResult.objects.filter(pk=row.pk).update(status=status)
            with self.subTest(status=status), self.assertNumQueries(1):
                self.assertEqual(player_refresh_pending(self.user.id), expected)

    def test_backfill_and_other_players_are_distinguished(self):
        enqueue_player_backfill(self.user.id)
        self.assertTrue(player_refresh_pending(self.user.id))
        self.assertFalse(player_refresh_pending(self.user.id + 1))
        self.client.force_login(self.user)
        response = self.client.get('/api/medal/refresh-status', {'user_id': self.user.id + 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'user_id': self.user.id, 'pending': True})

    def test_running_older_task_does_not_hide_a_new_ready_task(self):
        enqueue_player_refresh(self.user.id, video_ids=[123])
        row = DBTaskResult.objects.get()
        DBTaskResult.objects.filter(pk=row.pk).update(status=TaskResultStatus.RUNNING)
        enqueue_player_refresh(self.user.id, video_ids=[124])
        DBTaskResult.objects.filter(pk=row.pk).update(status=TaskResultStatus.SUCCESSFUL)
        self.assertTrue(player_refresh_pending(self.user.id))
