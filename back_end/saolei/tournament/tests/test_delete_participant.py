from tournament.models import TournamentParticipant, TournamentUser, WeeklyParticipant
from tournament.services import award_tournament_rank_scores
from tournament.tasks import task_disqualify_participant
from .base import MS_TextChoices, timedelta, timezone, Tournament_TextChoices, TournamentTestCaseBase, VideoModel


class TestParticipantActions(TournamentTestCaseBase):
    def setUp(self):
        super().setUp()
        self.host = self.create_user('participant_host')
        self.weekly = self.create_weekly_tournament(host=self.host, start_time=timezone.now() - timedelta(hours=4))
        with self.captureOnCommitCallbacks(execute=True):
            self.participant = WeeklyParticipant.objects.create(
                user=self.user, tournament=self.weekly,
                start_time=timezone.now() - timedelta(hours=3), end_time=timezone.now() - timedelta(hours=1),
            )
        self.reset_url = f'/api/tournament/participant/{self.participant.id}/reset'
        self.disqualify_url = f'/api/tournament/participant/{self.participant.id}/disqualify'

    def award(self):
        self.weekly.state = Tournament_TextChoices.State.AWARDED
        with self.captureOnCommitCallbacks(execute=True):
            self.weekly.save(update_fields=['state'])

    def test_host_resets_expired_session_and_preserves_other_registration(self):
        other = self.create_cached_gsc_participant()
        self.client.force_login(self.host)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.reset_url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(TournamentParticipant.objects.filter(pk=self.participant.id).exists())
        self.assertEqual([item.id for item in self.tournament_cache.get_participant_list(self.user.id)], [other.id])
        self.user.realname = 'Registered Player'
        self.user.save(update_fields=['_realname', 'date_updated'])
        self.client.force_login(self.user)
        response = self.client.post('/api/tournament/weekly/participant', {'id': self.weekly.id})
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.json()['id'], self.participant.id)
        self.assertNotEqual(response.json()['token'], self.participant.token)

    def test_staff_can_reset_but_cannot_disqualify_when_not_host(self):
        staff = self.create_user('participant_staff')
        staff.is_staff = True
        staff.save(update_fields=['is_staff'])
        self.client.force_login(staff)
        self.award()
        self.assertEqual(self.client.post(self.disqualify_url).status_code, 403)
        self.weekly.state = Tournament_TextChoices.State.NORMAL
        self.weekly.save(update_fields=['state'])
        self.assertEqual(self.client.post(self.reset_url).status_code, 204)

    def test_reset_rejects_active_session_and_any_video(self):
        self.client.force_login(self.host)
        self.participant.end_time = timezone.now() + timedelta(minutes=10)
        self.participant.save(update_fields=['end_time'])
        self.assertEqual(self.client.post(self.reset_url).status_code, 403)
        self.participant.end_time = timezone.now() - timedelta(minutes=10)
        self.participant.save(update_fields=['end_time'])
        video = self.create_video(tournament_identifier=[])
        self.weekly.videos.add(video)
        for state in (MS_TextChoices.State.OFFICIAL, MS_TextChoices.State.IDENTIFIER, MS_TextChoices.State.FROZEN):
            VideoModel.objects.filter(pk=video.id).update(state=state, ongoing_tournament=True)
            self.assertEqual(self.client.post(self.reset_url).status_code, 403)
        self.assertTrue(TournamentParticipant.objects.filter(pk=self.participant.id).exists())

    def test_reset_and_disqualification_are_unavailable_after_time_end_before_awards(self):
        self.weekly.end_time = timezone.now() - timedelta(minutes=1)
        self.weekly.save(update_fields=['end_time'])
        self.client.force_login(self.host)
        self.assertEqual(self.client.post(self.reset_url).status_code, 403)
        self.assertEqual(self.client.post(self.disqualify_url).status_code, 403)

    def test_host_disqualifies_with_video_via_idempotent_task(self):
        video = self.create_video(tournament_identifier=[])
        self.weekly.videos.add(video)
        self.award()
        self.participant.rank = 1
        self.participant.save(update_fields=['rank'])
        award_tournament_rank_scores(self.weekly)
        self.assertGreater(TournamentUser.objects.get(user=self.user).score_total, 0)
        self.client.force_login(self.host)
        response = self.client.post(self.disqualify_url)
        self.assertEqual(response.status_code, 202, response.content)
        self.assertTrue(TournamentParticipant.objects.filter(pk=self.participant.id).exists())
        task_id = response.json()['id']
        self.assertEqual(self.client.get(f'/api/tournament/disqualification-task/{task_id}').status_code, 200)
        participant_id = self.participant.id
        with self.captureOnCommitCallbacks(execute=True):
            self.assertTrue(task_disqualify_participant.call(participant_id, self.weekly.id))
            self.assertFalse(task_disqualify_participant.call(participant_id, self.weekly.id))
        self.assertFalse(TournamentParticipant.objects.filter(pk=participant_id).exists())
        self.assertTrue(self.weekly.videos.filter(pk=video.id).exists())
        user = TournamentUser.objects.get(user=self.user)
        self.assertEqual((user.score_total, user.weekly_total, user.weekly_classic_total), (0, 0, 0))

    def test_staff_host_may_disqualify_but_other_users_cannot_inspect_task(self):
        self.award()
        self.host.is_staff = True
        self.host.save(update_fields=['is_staff'])
        self.client.force_login(self.host)
        response = self.client.post(self.disqualify_url)
        self.assertEqual(response.status_code, 202)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f"/api/tournament/disqualification-task/{response.json()['id']}").status_code, 403)

    def test_login_and_resource_permissions_are_required(self):
        for actor in (None, self.user):
            self.client.logout()
            if actor:
                self.client.force_login(actor)
            self.assertEqual(self.client.post(self.reset_url).status_code, 403)
            self.assertEqual(self.client.post(self.disqualify_url).status_code, 403)
        self.client.force_login(self.host)
        self.assertEqual(self.client.post('/api/tournament/participant/0/reset').status_code, 404)
