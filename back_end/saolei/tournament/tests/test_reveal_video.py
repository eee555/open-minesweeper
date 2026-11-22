from unittest.mock import patch

from django.test import override_settings

from customranking.cache import get_player_pluck_records
from videomanager.cache import cache, newest_cache
from .base import GSCParticipant, MS_TextChoices, refresh_gsc_scores, Tournament_TextChoices, TournamentTestCaseBase, VideoModel


# These tests make consecutive requests to verify visibility, not rate limits.
@override_settings(RATELIMIT_ENABLE=False)
class TestRevealVideo(TournamentTestCaseBase):
    def setUp(self):
        super().setUp()
        self.create_cached_gsc_participant()
        self.video = self.create_video()
        self.url = f'/api/tournament/video/{self.video.id}/reveal'
        self.client.force_login(self.user)

    def test_owner_reveal_restores_queue_without_leaving_tournaments(self):
        other = self.create_weekly_tournament()
        other.videos.add(self.video)
        newest_cache.remove(self.video)
        before_count = self.user.userms.video_num_total
        response = self.client.get('/api/userprofile/videolist', {'user_id': self.user.id})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()[0]['ongoing_tournament'])
        self.client.logout()
        response = self.client.get('/api/userprofile/videolist', {'user_id': self.user.id})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), [])
        self.client.force_login(self.user)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b'')
        self.video.refresh_from_db()
        self.assertFalse(self.video.ongoing_tournament)
        response = self.client.get(f'/api/speedranking/player/{self.user.id}')
        self.assertEqual(response.status_code, 200, response.content)
        record = response.json()['saolei']
        self.assertEqual(record['bt_id'], self.video.id)
        self.assertSetEqual(set(self.video.tournaments.values_list('id', flat=True)), {self.tournament.id, other.id})
        self.assertTrue(cache.hexists(newest_cache.key, self.video.id))
        self.user.userms.refresh_from_db()
        self.assertEqual(self.user.userms.video_num_total, before_count)
        refresh_gsc_scores(self.tournament)
        self.assertEqual(GSCParticipant.objects.get(tournament=self.tournament, user=self.user).bt1st, self.video.timems)

        with patch.object(VideoModel, 'save', autospec=True) as save:
            self.assertEqual(self.client.post(self.url).status_code, 204)
        save.assert_not_called()
        self.client.logout()
        response = self.client.get('/api/userprofile/videolist', {'user_id': self.user.id})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()[0]['id'], self.video.id)
        self.assertFalse(response.json()[0]['ongoing_tournament'])
        self.assertEqual(self.client.get('/api/tournament/get_videos/participant', {'tournament_id': self.tournament.id, 'user_id': self.user.id}).status_code, 403)

    def test_reveal_requires_owner_even_for_host_or_staff(self):
        other = self.create_user('other')
        self.tournament.host = other
        self.tournament.save(update_fields=['host'])
        for user, staff in ((None, False), (other, False), (other, True)):
            with self.subTest(user=user, staff=staff):
                self.client.logout()
                if user:
                    user.is_staff = staff
                    user.save(update_fields=['is_staff'])
                    self.client.force_login(user)
                self.assertEqual(self.client.post(self.url).status_code, 403)
                self.video.refresh_from_db()
                self.assertTrue(self.video.ongoing_tournament)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post('/api/tournament/video/999999999/reveal').status_code, 404)

    def test_tournament_video_lists_keep_base_schema(self):
        response = self.client.get('/api/tournament/get_videos/participant', {'tournament_id': self.tournament.id, 'user_id': self.user.id})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('ongoing_tournament', response.json()[0])
        self.tournament.state = Tournament_TextChoices.State.AWARDED
        self.tournament.save(update_fields=['state'])
        response = self.client.get('/api/tournament/get_videos/tournament', {'tournament_id': self.tournament.id})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('ongoing_tournament', response.json()[0])

    def test_reveal_updates_custom_pluck_record(self):
        video = self.create_video(level=MS_TextChoices.Level.CUSTOM_8_8_40)
        VideoModel.objects.filter(pk=video.pk).update(pluck=5)
        self.assertEqual(get_player_pluck_records(video.player_id, [video.level]), {})
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/api/tournament/video/{video.pk}/reveal')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(get_player_pluck_records(video.player_id, [video.level])[video.level]['video_id'], video.pk)
