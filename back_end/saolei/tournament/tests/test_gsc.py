from .base import (
    _task_award_tournament_impl,
    _task_gsc_finish_impl,
    _task_gsc_refresh_best_impl,
    GSC_Defaults,
    gsc_encode_best,
    GSCParticipant,
    GSCTournament,
    Identifier,
    MS_TextChoices,
    refresh_gsc_scores,
    refresh_tournament_ranks,
    reveal_videos_for_tournament,
    timedelta,
    timezone,
    Tournament_TextChoices,
    TournamentTestCaseBase,
    TournamentUser,
    VideoModel,
)


class TestGsc(TournamentTestCaseBase):
    def test_get_results_serializes_awarded_gsc_results(self):
        participant = GSCParticipant.objects.create(
            user=self.user,
            tournament=self.tournament,
            token=self.tournament.token,
            start_time=self.tournament.start_time,
            end_time=self.tournament.end_time,
            rank=1,
            rank_score=100,
        )
        external_participant = GSCParticipant.objects.create(
            tournament=self.tournament,
            token=self.tournament.token,
            start_time=self.tournament.start_time,
            end_time=self.tournament.end_time,
            rank=2,
            rank_score=50,
        )
        video = self.create_video()
        self.tournament.videos.add(video)

        normal_response = self.client.get('/api/tournament/gsc/results', {'tournament_id': self.tournament.id})
        self.assertEqual(normal_response.status_code, 403)

        self.tournament.state = Tournament_TextChoices.State.AWARDED
        self.tournament.save(update_fields=['state'])

        response = self.client.get('/api/tournament/gsc/results', {'tournament_id': self.tournament.id})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        data_by_id = {item['id']: item for item in data}
        self.assertEqual(data_by_id[participant.id]['rank'], 1)
        self.assertEqual(data_by_id[participant.id]['user_id'], self.user.id)
        self.assertEqual(data_by_id[external_participant.id]['user_id'], 0)

    def test_gsc_participant_registration_uses_two_steps(self):
        self.user.realname = 'GSC Player'
        self.user.save(update_fields=['_realname', 'date_updated'])
        self.client.force_login(self.user)

        participant_response = self.client.post('/api/tournament/gsc/participant', {
            'order': self.tournament.order,
        })

        self.assertEqual(participant_response.status_code, 200)
        participant = GSCParticipant.objects.get(tournament=self.tournament, user=self.user)
        self.assertEqual(participant.token, self.tournament.token)
        self.assertEqual(participant.start_time, self.tournament.start_time)
        self.assertEqual(participant.end_time, self.tournament.end_time)
        self.assertIsNone(participant.arbiter_identifier)
        participants_response = self.client.get('/api/tournament/participants', {'tournament_id': self.tournament.id})
        participants_data = participants_response.json()
        self.assertEqual(participants_response.status_code, 200)
        self.assertEqual(participants_data[0]['id'], participant.id)
        self.assertEqual(participants_data[0]['user_id'], self.user.id)
        self.assertEqual(participants_data[0]['token'], self.tournament.token)
        self.assertIsNone(participants_data[0]['arbiter_identifier__identifier'])

        identifier_text = f'Player {self.tournament.token}'
        Identifier.objects.create(identifier=identifier_text, safe=True)
        identifier_response = self.client.post('/api/tournament/gsc/participant/identifier', {
            'order': self.tournament.order,
            'identifier': identifier_text,
        })

        self.assertEqual(identifier_response.status_code, 200)
        self.assertEqual(identifier_response.json()['type'], 'success')
        participant.refresh_from_db()
        self.assertEqual(participant.arbiter_identifier.identifier, identifier_text)
        participants_response = self.client.get('/api/tournament/participants', {'tournament_id': self.tournament.id})
        participants_data = participants_response.json()
        self.assertEqual(participants_data[0]['id'], participant.id)
        self.assertEqual(participants_data[0]['arbiter_identifier__identifier'], identifier_text)

    def test_gsc_participant_registration_requires_identity_access(self):
        self.client.force_login(self.user)

        response = self.client.post('/api/tournament/gsc/participant', {
            'order': self.tournament.order,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'type': 'error',
            'object': 'userprofile',
            'category': 'identity_access_required',
        })
        self.assertFalse(GSCParticipant.objects.filter(tournament=self.tournament, user=self.user).exists())

    def test_gsc_participant_identifier_requires_existing_participant(self):
        self.user.realname = 'GSC Player'
        self.user.save(update_fields=['_realname', 'date_updated'])
        self.client.force_login(self.user)

        response = self.client.post('/api/tournament/gsc/participant/identifier', {
            'order': self.tournament.order,
            'identifier': f'Player {self.tournament.token}',
        })

        self.assertEqual(response.status_code, 404)
        self.assertFalse(GSCParticipant.objects.filter(tournament=self.tournament, user=self.user).exists())

    def test_creating_participant_adds_existing_videos_in_time_window(self):
        matched_video = self.create_video()
        other_software_video = self.create_video(software=MS_TextChoices.Software.MVF)
        outside_video = self.create_video()
        missing_identifier_video = self.create_video(tournament_identifier=[])
        avf_with_token_video = self.create_video(
            software=MS_TextChoices.Software.AVF,
            tournament_identifier=[self.tournament.token],
        )
        VideoModel.objects.filter(pk=outside_video.pk).update(
            upload_time=self.tournament.end_time + timedelta(minutes=1),
        )

        GSCParticipant.objects.create(
            user=self.user,
            tournament=self.tournament,
            token=self.tournament.token,
            start_time=self.tournament.start_time,
            end_time=self.tournament.end_time,
        )

        matched_video.refresh_from_db()
        other_software_video.refresh_from_db()
        outside_video.refresh_from_db()
        missing_identifier_video.refresh_from_db()
        self.assertTrue(self.tournament.videos.filter(pk=matched_video.pk).exists())
        self.assertTrue(self.tournament.videos.filter(pk=other_software_video.pk).exists())
        self.assertFalse(self.tournament.videos.filter(pk=outside_video.pk).exists())
        self.assertFalse(self.tournament.videos.filter(pk=missing_identifier_video.pk).exists())
        self.assertFalse(self.tournament.videos.filter(pk=avf_with_token_video.pk).exists())
        self.assertFalse(matched_video.ongoing_tournament)
        self.assertFalse(other_software_video.ongoing_tournament)
        self.assertFalse(outside_video.ongoing_tournament)
        self.assertFalse(missing_identifier_video.ongoing_tournament)
        self.assertFalse(avf_with_token_video.ongoing_tournament)

    def test_creating_arbiter_participant_adds_matching_avf_videos(self):
        identifier = Identifier.objects.create(identifier='arbiter-id')
        matched_video = self.create_video(
            identifier=identifier.identifier,
            software=MS_TextChoices.Software.AVF,
            tournament_identifier=[],
        )
        token_only_video = self.create_video(
            software=MS_TextChoices.Software.AVF,
            tournament_identifier=[self.tournament.token],
        )

        GSCParticipant.objects.create(
            user=self.user,
            tournament=self.tournament,
            token=self.tournament.token,
            arbiter_identifier=identifier,
            start_time=self.tournament.start_time,
            end_time=self.tournament.end_time,
        )

        matched_video.refresh_from_db()
        token_only_video.refresh_from_db()
        self.assertTrue(self.tournament.videos.filter(pk=matched_video.pk).exists())
        self.assertFalse(self.tournament.videos.filter(pk=token_only_video.pk).exists())
        self.assertFalse(matched_video.ongoing_tournament)
        self.assertFalse(token_only_video.ongoing_tournament)

    def test_reveal_videos_for_tournament_makes_videos_public(self):
        self.create_cached_gsc_participant()
        video = self.create_video()
        GSCTournament.objects.filter(pk=self.tournament.pk).update(
            end_time=timezone.now() - timedelta(hours=1),
            state=Tournament_TextChoices.State.AWARDED,
        )
        self.tournament.refresh_from_db()

        with self.captureOnCommitCallbacks(execute=True):
            changed_count = reveal_videos_for_tournament(self.tournament)

        video.refresh_from_db()
        self.user.userms.refresh_from_db()
        self.assertEqual(changed_count, 1)
        self.assertFalse(video.ongoing_tournament)
        response = self.client.get(f'/api/speedranking/player/{self.user.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['saolei']['bt_id'], video.id)

    def test_reveal_videos_for_tournament_waits_until_awarded(self):
        self.create_cached_gsc_participant()
        video = self.create_video()
        GSCTournament.objects.filter(pk=self.tournament.pk).update(
            end_time=timezone.now() - timedelta(hours=1),
            state=Tournament_TextChoices.State.NORMAL,
        )
        self.tournament.refresh_from_db()

        changed_count = reveal_videos_for_tournament(self.tournament)

        video.refresh_from_db()
        self.assertEqual(changed_count, 0)
        self.assertTrue(video.ongoing_tournament)

    def test_reveal_videos_for_tournament_keeps_videos_in_other_unawarded_tournament(self):
        self.create_cached_gsc_participant()
        video = self.create_video()
        now = timezone.now()
        other_tournament = GSCTournament.objects.create(
            order=2,
            _token='G67890',
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            state=Tournament_TextChoices.State.PENDING,
        )
        other_tournament.videos.add(video)
        GSCTournament.objects.filter(pk=self.tournament.pk).update(
            end_time=now - timedelta(minutes=1),
            state=Tournament_TextChoices.State.AWARDED,
        )
        self.tournament.refresh_from_db()

        changed_count = reveal_videos_for_tournament(self.tournament)

        video.refresh_from_db()
        self.assertEqual(changed_count, 0)
        self.assertTrue(video.ongoing_tournament)

    def test_task_gsc_finish_deletes_participants_without_videos(self):
        participant_with_video = self.create_cached_gsc_participant()
        user_without_video = self.create_user('gsc_without_video')
        participant_without_video = GSCParticipant.objects.create(
            user=user_without_video,
            tournament=self.tournament,
            token=self.tournament.token,
            start_time=self.tournament.start_time,
            end_time=self.tournament.end_time,
        )
        legacy_user = self.create_user('gsc_legacy_without_video')
        legacy_participant = self.create_cached_gsc_participant(user=legacy_user)
        TournamentUser.objects.filter(user=legacy_user).delete()
        video = self.create_video()
        self.tournament.videos.add(video)
        self.tournament.end_time = timezone.now() - timedelta(minutes=1)
        self.tournament.weight = 1000
        self.tournament.save(update_fields=['end_time', 'weight'])

        result = _task_gsc_finish_impl(self.tournament.order)

        self.tournament.refresh_from_db()
        participant_with_video.refresh_from_db()
        self.assertEqual(result['tournament_users'], 1)
        self.assertEqual(result['deleted_participants'], 2)
        self.assertEqual(self.tournament.state, Tournament_TextChoices.State.AWARDED)
        self.assertEqual(participant_with_video.rank_score, 0)
        self.assertTrue(GSCParticipant.objects.filter(pk=participant_with_video.pk).exists())
        self.assertFalse(GSCParticipant.objects.filter(pk=participant_without_video.pk).exists())
        self.assertFalse(GSCParticipant.objects.filter(pk=legacy_participant.pk).exists())
        self.assertTrue(TournamentUser.objects.filter(user=legacy_user).exists())
        self.assertTrue(TournamentUser.objects.filter(user=user_without_video).exists())

        award_count = _task_award_tournament_impl(self.tournament.id)
        best_count = _task_gsc_refresh_best_impl(self.tournament.order)
        participant_with_video.refresh_from_db()
        tournament_user = TournamentUser.objects.get(user=self.user)
        self.assertEqual(award_count, 1)
        self.assertEqual(best_count, 1)
        self.assertEqual(participant_with_video.rank_score, 1000)
        self.assertEqual(tournament_user.score_current, 1000)
        self.assertEqual(tournament_user.score_total, 1000)
        self.assertEqual(tournament_user.gsc_total, 1000)
        self.assertEqual(
            tournament_user.gsc_best,
            gsc_encode_best(participant_with_video.t37, self.tournament.order),
        )

    def test_refresh_gsc_score_and_rank_uses_batch_rules(self):
        participant = GSCParticipant.objects.create(
            user=self.user,
            tournament=self.tournament,
            token=self.tournament.token,
            start_time=self.tournament.start_time,
            end_time=self.tournament.end_time,
        )
        self.tournament_cache.update_participant(participant)
        user_without_valid_score = self.create_user('gsc_default_user')
        participant_without_valid_score = GSCParticipant.objects.create(
            user=user_without_valid_score,
            tournament=self.tournament,
            token=self.tournament.token,
            start_time=self.tournament.start_time,
            end_time=self.tournament.end_time,
        )
        participant_without_valid_score.bt1st = 1
        participant_without_valid_score.bt20th = 1
        participant_without_valid_score.bt20sum = 1
        participant_without_valid_score.it1st = 1
        participant_without_valid_score.it12th = 1
        participant_without_valid_score.it12sum = 1
        participant_without_valid_score.et1st = 1
        participant_without_valid_score.et5th = 1
        participant_without_valid_score.et5sum = 1
        participant_without_valid_score.save(update_fields=[
            'bt1st', 'bt20th', 'bt20sum',
            'it1st', 'it12th', 'it12sum',
            'et1st', 'et5th', 'et5sum',
        ])

        beginner_times = [1000 + index * 100 for index in range(21)]
        intermediate_times = [10000 + index * 1000 for index in range(13)]
        expert_times = [40000 + index * 10000 for index in range(6)]
        for level, bv, times in [
            (MS_TextChoices.Level.BEGINNER, GSC_Defaults.B_BV_MIN, beginner_times),
            (MS_TextChoices.Level.INTERMEDIATE, GSC_Defaults.I_BV_MIN, intermediate_times),
            (MS_TextChoices.Level.EXPERT, GSC_Defaults.E_BV_MIN, expert_times),
        ]:
            for index, timems in enumerate(times):
                self.create_video(level=level, timems=timems, bv=bv, right_ce=index % 2)
            for mode in MS_TextChoices.Mode.values:
                if mode != MS_TextChoices.Mode.STD:
                    self.create_video(level=level, timems=1, bv=bv, mode=mode)
            for state in MS_TextChoices.State.values:
                if state != MS_TextChoices.State.OFFICIAL:
                    video = self.create_video(level=level, timems=1, bv=bv)
                    VideoModel.objects.filter(pk=video.pk).update(state=state)

        self.create_video(level=MS_TextChoices.Level.BEGINNER, timems=999, bv=GSC_Defaults.B_BV_MIN - 1)
        self.create_video(level=MS_TextChoices.Level.INTERMEDIATE, timems=GSC_Defaults.IT, bv=GSC_Defaults.I_BV_MIN)
        self.create_video(level=MS_TextChoices.Level.EXPERT, timems=1, bv=GSC_Defaults.E_BV_MIN - 1)

        score_changed = refresh_gsc_scores(self.tournament)
        rank_changed = refresh_tournament_ranks(self.tournament)

        participant = GSCParticipant.objects.get(tournament=self.tournament, user=self.user)
        participant_without_valid_score.refresh_from_db()

        beginner_top = beginner_times[:20]
        intermediate_top = intermediate_times[:12]
        expert_top = expert_times[:5]
        self.assertEqual(score_changed, 2)
        self.assertEqual(rank_changed, 2)
        self.assertEqual(participant.bt1st, beginner_top[0])
        self.assertEqual(participant.bt20th, beginner_top[-1])
        self.assertEqual(participant.bt20sum, sum(beginner_top))
        self.assertEqual(participant.it1st, intermediate_top[0])
        self.assertEqual(participant.it12th, intermediate_top[-1])
        self.assertEqual(participant.it12sum, sum(intermediate_top))
        self.assertEqual(participant.et1st, expert_top[0])
        self.assertEqual(participant.et5th, expert_top[-1])
        self.assertEqual(participant.et5sum, sum(expert_top))
        self.assertEqual(participant.rank, 1)
        self.assertEqual(participant_without_valid_score.bt1st, GSC_Defaults.BT)
        self.assertEqual(participant_without_valid_score.bt20sum, GSC_Defaults.BT * 20)
        self.assertEqual(participant_without_valid_score.it12sum, GSC_Defaults.IT * 12)
        self.assertEqual(participant_without_valid_score.et5sum, GSC_Defaults.ET * 5)
        self.assertEqual(participant_without_valid_score.rank, 2)
