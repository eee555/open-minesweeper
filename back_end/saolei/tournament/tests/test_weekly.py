from unittest.mock import patch

from .base import (
    _task_award_tournament_impl,
    _task_weekly_finish_impl,
    _task_weekly_refresh_best_impl,
    MS_TextChoices,
    refresh_tournament_ranks,
    refresh_weekly_classic_scores,
    timedelta,
    timezone,
    Tournament_TextChoices,
    TournamentTestCaseBase,
    TournamentUser,
    VideoModel,
    weekly_encode_best,
    WeeklyParticipant,
)


class TestWeekly(TournamentTestCaseBase):
    def test_participants_and_results_serialize_weekly_data(self):
        tournament = self.create_weekly_tournament()

        anonymous_response = self.client.get('/api/tournament/participants', {'tournament_id': tournament.id})
        self.assertEqual(anonymous_response.status_code, 200)
        self.assertEqual(anonymous_response.json(), [])

        participant = WeeklyParticipant.objects.create(
            user=self.user,
            tournament=tournament,
            start_time=tournament.start_time,
            end_time=tournament.end_time,
        )
        external_participant = WeeklyParticipant.objects.create(
            tournament=tournament,
            start_time=tournament.start_time,
            end_time=tournament.end_time,
        )
        self.client.force_login(self.user)
        registered_response = self.client.get('/api/tournament/participants', {'tournament_id': tournament.id})
        registered_data = registered_response.json()
        self.assertEqual(registered_response.status_code, 200)
        registered_data_by_id = {item['id']: item for item in registered_data}
        self.assertEqual(registered_data_by_id[participant.id]['user_id'], self.user.id)
        self.assertEqual(registered_data_by_id[participant.id]['token'], participant.token)
        self.assertIsNone(registered_data_by_id[participant.id]['arbiter_identifier__identifier'])
        self.assertEqual(registered_data_by_id[external_participant.id]['user_id'], 0)

        normal_results_response = self.client.get('/api/tournament/weekly/results', {'tournament_id': tournament.id})
        self.assertEqual(normal_results_response.status_code, 403)

        tournament.state = Tournament_TextChoices.State.AWARDED
        tournament.save(update_fields=['state'])
        awarded_response = self.client.get('/api/tournament/weekly/results', {'tournament_id': tournament.id})
        awarded_data = awarded_response.json()
        self.assertEqual(awarded_response.status_code, 200)
        awarded_data_by_id = {item['id']: item for item in awarded_data}
        self.assertEqual(awarded_data_by_id[participant.id]['user_id'], self.user.id)
        self.assertEqual(awarded_data_by_id[external_participant.id]['user_id'], 0)

    def test_weekly_participant_api_limits_window_to_two_hours_or_tournament_end(self):
        now = timezone.now()
        full_window_tournament = self.create_weekly_tournament(
            year=2026,
            week=2,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(days=1),
        )
        truncated_tournament = self.create_weekly_tournament(
            year=2026,
            week=3,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(minutes=30),
        )
        other_user = self.create_user('weekly_window_user')
        other_user.realname = 'Weekly Window User'
        other_user.save(update_fields=['_realname', 'date_updated'])
        self.client.force_login(other_user)

        with patch('django.utils.timezone.now', return_value=now), self.captureOnCommitCallbacks(execute=True):
            full_response = self.client.post('/api/tournament/weekly/participant', {'id': full_window_tournament.id})
            truncated_response = self.client.post('/api/tournament/weekly/participant', {'id': truncated_tournament.id})

        full_participant = WeeklyParticipant.objects.get(tournament=full_window_tournament, user=other_user)
        truncated_participant = WeeklyParticipant.objects.get(tournament=truncated_tournament, user=other_user)
        self.assertEqual(full_response.status_code, 200)
        self.assertEqual(truncated_response.status_code, 200)
        self.assertEqual(full_response.json()['id'], full_participant.id)
        self.assertEqual(full_response.json()['user_id'], other_user.id)
        self.assertEqual(full_response.json()['tournament_id'], full_window_tournament.id)
        self.assertIsNone(full_response.json()['rank'])
        self.assertEqual(full_response.json()['rank_score'], 0)
        self.assertEqual(truncated_response.json()['id'], truncated_participant.id)
        self.assertEqual(truncated_response.json()['user_id'], other_user.id)
        self.assertEqual(truncated_response.json()['tournament_id'], truncated_tournament.id)
        self.assertEqual(full_participant.start_time, now)
        self.assertEqual(full_participant.end_time, now + timedelta(hours=2))
        self.assertEqual(truncated_participant.start_time, now)
        self.assertEqual(truncated_participant.end_time, truncated_tournament.end_time)

    def test_weekly_participant_api_requires_identity_access(self):
        tournament = self.create_weekly_tournament()
        self.client.force_login(self.user)

        response = self.client.post('/api/tournament/weekly/participant', {'id': tournament.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'type': 'error',
            'object': 'userprofile',
            'category': 'identity_access_required',
        })
        self.assertFalse(WeeklyParticipant.objects.filter(tournament=tournament, user=self.user).exists())

    def test_weekly_participant_create_backfills_and_checkin_uses_token(self):
        tournament = self.create_weekly_tournament()
        existing_video = self.create_video(tournament_identifier=['WEEKLY_TOKEN'])
        WeeklyParticipant.objects.create(
            user=self.user,
            tournament=tournament,
            token='WEEKLY_TOKEN',
            start_time=tournament.start_time,
            end_time=tournament.end_time,
        )
        self.assertTrue(tournament.videos.filter(pk=existing_video.pk).exists())

        other_user = self.create_user('weekly_checkin_user')
        other_user.realname = 'Weekly Checkin User'
        other_user.save(update_fields=['_realname', 'date_updated'])
        self.client.force_login(other_user)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/tournament/weekly/participant', {'id': tournament.id})
        participant = WeeklyParticipant.objects.get(tournament=tournament, user=other_user)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['token'], participant.token)
        self.assertEqual(response.json()['user_id'], other_user.id)
        self.assertEqual(response.json()['tournament_id'], tournament.id)
        video = self.create_video(user=other_user, tournament_identifier=[participant.token])
        video.refresh_from_db()
        self.assertTrue(video.ongoing_tournament)
        self.assertTrue(tournament.videos.filter(pk=video.pk).exists())

    def test_refresh_weekly_classic_scores_only_counts_standard_videos_including_nf(self):
        tournament = self.create_weekly_tournament()
        participant = WeeklyParticipant.objects.create(
            user=self.user,
            tournament=tournament,
            start_time=tournament.start_time,
            end_time=tournament.end_time,
        )
        ignored_expert = self.create_video(tournament_identifier=[], level=MS_TextChoices.Level.EXPERT, mode=MS_TextChoices.Mode.JSW, timems=1000)
        nf_expert = self.create_video(tournament_identifier=[], level=MS_TextChoices.Level.EXPERT, mode=MS_TextChoices.Mode.STD, right_ce=0, timems=110000)
        std_expert = self.create_video(tournament_identifier=[], level=MS_TextChoices.Level.EXPERT, mode=MS_TextChoices.Mode.STD, timems=120000)
        ignored_intermediate = self.create_video(tournament_identifier=[], level=MS_TextChoices.Level.INTERMEDIATE, mode=MS_TextChoices.Mode.JSW, timems=1000)
        intermediate_times = [20000, 21000, 22000, 23000, 24000]
        intermediate_videos = [
            self.create_video(tournament_identifier=[], level=MS_TextChoices.Level.INTERMEDIATE, mode=MS_TextChoices.Mode.STD, timems=timems)
            for timems in intermediate_times
        ]
        tournament.videos.add(ignored_expert, nf_expert, std_expert, ignored_intermediate, *intermediate_videos)
        for level in [MS_TextChoices.Level.INTERMEDIATE, MS_TextChoices.Level.EXPERT]:
            for state in MS_TextChoices.State.values:
                if state != MS_TextChoices.State.OFFICIAL:
                    video = self.create_video(tournament_identifier=[], level=level, timems=1)
                    VideoModel.objects.filter(pk=video.pk).update(state=state)
                    tournament.videos.add(video)

        refresh_weekly_classic_scores(tournament)

        participant.refresh_from_db()
        used_video_ids = {video_id for video_id, _ in participant.classic_et + participant.classic_it}
        self.assertEqual([timems for _, timems in participant.classic_et], [110000, 120000])
        self.assertEqual([timems for _, timems in participant.classic_it], intermediate_times)
        self.assertEqual(participant.classic_score, 110000 + 120000 + sum(intermediate_times))
        self.assertNotIn(ignored_expert.id, used_video_ids)
        self.assertNotIn(ignored_intermediate.id, used_video_ids)

        VideoModel.objects.filter(pk=nf_expert.pk).update(state=MS_TextChoices.State.FROZEN)
        refresh_weekly_classic_scores(tournament)
        participant.refresh_from_db()
        self.assertEqual(participant.classic_et, [[std_expert.id, 120000], [0, 240000]])
        self.assertEqual(participant.classic_score, 120000 + 240000 + sum(intermediate_times))

    def test_refresh_weekly_score_rank_and_finish_tournament(self):
        tournament = self.create_weekly_tournament()
        participant = WeeklyParticipant.objects.create(
            user=self.user,
            tournament=tournament,
            start_time=tournament.start_time,
            end_time=tournament.end_time,
        )
        user_without_video = self.create_user('weekly_without_video')
        participant_without_video = WeeklyParticipant.objects.create(
            user=user_without_video,
            tournament=tournament,
            start_time=tournament.start_time,
            end_time=tournament.end_time,
        )

        expert_times = [100000, 120000, 130000]
        intermediate_times = [20000, 21000, 22000, 23000, 24000, 25000]
        for timems in expert_times:
            tournament.videos.add(self.create_video(tournament_identifier=[], level=MS_TextChoices.Level.EXPERT, timems=timems))
        for timems in intermediate_times:
            tournament.videos.add(self.create_video(tournament_identifier=[], level=MS_TextChoices.Level.INTERMEDIATE, timems=timems))

        score_count = refresh_weekly_classic_scores(tournament)
        rank_count = refresh_tournament_ranks(tournament)

        participant.refresh_from_db()
        participant_without_video.refresh_from_db()
        self.assertEqual(score_count, 2)
        self.assertEqual(rank_count, 2)
        self.assertEqual(participant.classic_score, sum(expert_times[:2]) + sum(intermediate_times[:5]))
        self.assertEqual(participant.rank, 1)
        self.assertEqual(participant.rank_score, 0)
        self.assertEqual(participant_without_video.rank, 2)

        tournament.end_time = timezone.now() - timedelta(minutes=1)
        tournament.save(update_fields=['end_time'])
        TournamentUser.objects.filter(user_id__in=[self.user.id, user_without_video.id]).delete()
        result = _task_weekly_finish_impl(tournament.id)

        tournament.refresh_from_db()
        participant.refresh_from_db()
        self.assertEqual(result['tournament_users'], 1)
        self.assertEqual(result['deleted_participants'], 1)
        self.assertEqual(result['score_count'], 1)
        self.assertEqual(result['rank_count'], 1)
        self.assertEqual(tournament.state, Tournament_TextChoices.State.AWARDED)
        self.assertEqual(participant.rank_score, 0)
        self.assertTrue(WeeklyParticipant.objects.filter(pk=participant.pk).exists())
        self.assertFalse(WeeklyParticipant.objects.filter(pk=participant_without_video.pk).exists())
        self.assertTrue(TournamentUser.objects.filter(user=user_without_video).exists())

        award_count = _task_award_tournament_impl(tournament.id)
        best_count = _task_weekly_refresh_best_impl(tournament.id)
        participant.refresh_from_db()
        tournament_user = TournamentUser.objects.get(user=self.user)
        self.assertEqual(award_count, 1)
        self.assertEqual(best_count, 1)
        self.assertEqual(participant.rank_score, 50)
        self.assertEqual(tournament_user.score_current, 50)
        self.assertEqual(tournament_user.score_total, 50)
        self.assertEqual(tournament_user.weekly_total, 50)
        self.assertEqual(tournament_user.weekly_classic_total, 50)
        self.assertEqual(
            tournament_user.weekly_classic_best,
            weekly_encode_best(participant.classic_score, 2026, 1),
        )
