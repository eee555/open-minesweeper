from datetime import timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from config.text_choices import MS_TextChoices, Tournament_TextChoices
from identifier.models import Identifier
from identifier.services import bind_identifier
from tournament.cache import cache, TOURNAMENT_USER_CACHE_KEYS
from tournament.gsc.services import GSC_SCORE_FIELDS, refresh_gsc_scores
from tournament.gsc.utils import gsc_encode_best
from tournament.models import GSCParticipant, GSCTournament, TournamentUser
from tournament.services import delete_participants_without_videos
from utils.parser import MSVideoParser
from videomanager.models import VideoModel
from .base import TournamentTestCaseBase


class TestGscHistory(TournamentTestCaseBase):
    def setUp(self):
        super().setUp()
        self.host = self.create_user('history_host')
        self.tournament.host = self.host
        self.tournament.state = Tournament_TextChoices.State.AWARDED
        self.tournament.end_time = timezone.now() - timedelta(days=30)
        self.tournament.start_time = self.tournament.end_time - timedelta(hours=4)
        self.tournament.weight = 1000
        self.tournament.save(update_fields=['host', 'state', 'start_time', 'end_time', 'weight'])
        self.client.force_login(self.host)
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        settings = override_settings(MEDIA_ROOT=self.media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.fixture_dir = Path(__file__).resolve().parents[2] / 'common/test_fixtures/video_upload_ranking'

    def post(self, path, data):
        return self.client.post('/api/tournament/gsc/history' + path, data, content_type='application/json')

    def row(self, **identity):
        return {**dict.fromkeys(GSC_SCORE_FIELDS, 1000), **identity}

    def batch(self, rows):
        return {'order': self.tournament.order, 'rows': rows}

    def replay(self, name='standard_gsc.evf'):
        return SimpleUploadedFile(name, (self.fixture_dir / name).read_bytes())

    def prepare(self):
        return self.post('/prepare', {'order': self.tournament.order, 'user_id': self.user.id})

    def bind(self, participant_id, identifier):
        return self.post(f'/participants/{participant_id}/identifier', {'identifier': identifier})

    def prepare_and_bind(self, identifiers=None):
        if identifiers is None:
            identifiers = [MSVideoParser(self.replay()).identifier]
        response = self.prepare()
        self.assertEqual(response.status_code, 200, response.content)
        for identifier in identifiers:
            bound = self.bind(response.json()['id'], identifier)
            self.assertEqual(bound.status_code, 200, bound.content)
        return response

    def upload(self, participant_id, upload_time, name='standard_gsc.evf'):
        return self.client.post(f'/api/tournament/gsc/history/participants/{participant_id}/videos', {
            'upload_time': upload_time, 'file': self.replay(name),
        })

    @override_settings(RATELIMIT_ENABLE=True)
    def test_history_writes_do_not_apply_rate_limits_to_the_host(self):
        self.assertFalse(self.host.is_staff)
        other = self.create_user('history_no_rate_limit')
        with patch('django_ratelimit.decorators.is_ratelimited', return_value=True) as is_ratelimited:
            participant_id = self.prepare().json()['id']
            identifier = MSVideoParser(self.replay()).identifier
            self.assertEqual(self.bind(participant_id, identifier).status_code, 200)
            self.assertEqual(self.upload(participant_id, self.tournament.end_time.isoformat()).status_code, 200)
            self.assertEqual(self.post('/scores/users', self.batch([self.row(user_id=other.pk)])).status_code, 200)
            self.assertEqual(self.post('/scores/anonymous', self.batch([self.row(arbiter_identifier='no rate limit')])).status_code, 200)
            is_ratelimited.assert_not_called()

    def test_all_history_writes_check_permissions_and_state_before_calling_services(self):
        participant_id = self.prepare().json()['id']
        services = [
            self.enterContext(patch(f'tournament.gsc.api.{name}'))
            for name in ('prepare_gsc_history_videos', 'bind_gsc_history_identifier', 'upload_gsc_history_video', 'import_gsc_history_scores')
        ]
        end_time = self.tournament.end_time
        for actor, state, end, expected in [
            (None, Tournament_TextChoices.State.AWARDED, end_time, 403),
            (self.user, Tournament_TextChoices.State.AWARDED, end_time, 403),
            (self.host, Tournament_TextChoices.State.NORMAL, end_time, 409),
            (self.host, Tournament_TextChoices.State.AWARDED, None, 409),
        ]:
            with self.subTest(actor=actor, state=state, end=end):
                self.tournament.state, self.tournament.end_time = state, end
                self.tournament.save(update_fields=['state', 'end_time'])
                if actor is None:
                    self.client.logout()
                else:
                    self.client.force_login(actor)
                responses = [
                    self.prepare(),
                    self.bind(participant_id, 'not bound'),
                    self.upload(participant_id, end_time.isoformat()),
                    self.post('/scores/users', self.batch([self.row(user_id=self.user.pk)])),
                    self.post('/scores/anonymous', self.batch([self.row(arbiter_identifier='not imported')])),
                ]
                for response in responses:
                    self.assertEqual(response.status_code, expected, response.content)
                for service in services:
                    service.assert_not_called()

    def test_history_listing_reuses_existing_info_and_results(self):
        self.assertEqual(self.post('/scores/users', self.batch([self.row(user_id=self.user.pk)])).status_code, 200)
        self.client.logout()
        info = self.client.get('/api/tournament/gsc/admin-info', {'order': self.tournament.order})
        self.assertEqual(info.status_code, 200)
        self.assertEqual(info.json()['id'], self.tournament.id)
        self.assertIsNotNone(info.json()['end_time'])
        results = self.client.get('/api/tournament/gsc/results', {'tournament_id': info.json()['id']})
        self.assertEqual(results.status_code, 200)
        self.assertEqual(results.json()[0]['user_id'], self.user.pk)
        self.assertTrue(results.json()[0]['manual_scores'])
        self.assertFalse(results.json()[0]['has_videos'])

    def test_video_history_creation_updates_best_from_default_scores(self):
        response = self.prepare()
        self.assertEqual(response.status_code, 200, response.content)
        participant = GSCParticipant.objects.get(pk=response.json()['id'])
        best = gsc_encode_best(participant.t37, self.tournament.order)
        self.assertEqual(TournamentUser.objects.get(user=self.user).gsc_best, best)
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['gsc_best'], self.user.pk), best)
        self.assertIsNone(participant.rank)
        self.assertEqual(participant.rank_score, 0)

    def test_prepare_reuses_video_participant_without_changes_and_allows_more_videos(self):
        identifier = Identifier.objects.create(identifier='original arbiter identifier', safe=True)
        participant = GSCParticipant.objects.create(
            user=self.user, tournament=self.tournament, token='original token', arbiter_identifier=identifier,
            start_time=self.tournament.start_time - timedelta(hours=1), end_time=self.tournament.end_time + timedelta(hours=1),
            rank=7, rank_score=123, **dict.fromkeys(GSC_SCORE_FIELDS, 1000),
        )
        old_video = self.create_video(tournament_identifier=[])
        self.tournament.videos.add(old_video)
        original = GSCParticipant.objects.values().get(pk=participant.pk)

        for _ in range(2):
            response = self.prepare()
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(response.json()['id'], participant.pk)
            self.assertTrue(response.json()['has_videos'])
        self.assertEqual(GSCParticipant.objects.count(), 1)
        self.assertEqual(GSCParticipant.objects.values().get(pk=participant.pk), original)

        bound = self.bind(participant.pk, MSVideoParser(self.replay()).identifier)
        self.assertEqual(bound.status_code, 200, bound.content)
        uploaded = self.upload(participant.pk, self.tournament.end_time.isoformat())
        self.assertEqual(uploaded.status_code, 200, uploaded.content)
        self.assertEqual(set(self.tournament.videos.values_list('pk', flat=True)), {old_video.pk, uploaded.json()['id']})
        self.assertEqual(GSCParticipant.objects.values().get(pk=participant.pk), original)

    def test_manual_import_updates_best_and_preserves_scores_on_refresh_and_cleanup(self):
        response = self.post('/scores/users', self.batch([self.row(user_id=self.user.id)]))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), 1)
        participant = GSCParticipant.objects.get(user=self.user)
        self.assertTrue(participant.manual_scores)
        best = gsc_encode_best(participant.t37, self.tournament.order)
        tournament_user = TournamentUser.objects.get(user=self.user)
        self.assertEqual(tournament_user.gsc_best, best)
        self.assertEqual(cache.zscore(TOURNAMENT_USER_CACHE_KEYS['gsc_best'], self.user.pk), best)
        self.assertEqual(tournament_user.score_total, 0)
        self.assertIsNone(participant.rank)
        self.assertEqual(refresh_gsc_scores(self.tournament), 0)
        self.assertEqual(delete_participants_without_videos(self.tournament), 0)
        participant.refresh_from_db()
        self.assertEqual([getattr(participant, field) for field in GSC_SCORE_FIELDS], [1000] * 9)

    def test_anonymous_uses_identifier_and_shares_rank_without_receiving_points(self):
        self.assertEqual(self.post('/scores/anonymous', self.batch([self.row(arbiter_identifier=' Anonymous ')])).status_code, 200)
        row = self.row(user_id=self.user.id)
        row.update(dict.fromkeys(GSC_SCORE_FIELDS, 2000))
        self.assertEqual(self.post('/scores/users', self.batch([row])).status_code, 200)
        self.assertEqual(TournamentUser.objects.count(), 1)
        for _ in range(2):
            call_command('refresh_tournament_scores', self.tournament.id, stdout=StringIO())
        participants = list(GSCParticipant.objects.order_by('rank'))
        self.assertEqual([(p.user_id, p.rank, p.rank_score) for p in participants], [(None, 1, 0), (self.user.id, 2, 500)])
        self.assertEqual(TournamentUser.objects.get(user=self.user).score_total, 500)
        result = self.client.get('/api/tournament/gsc/results', {'tournament_id': self.tournament.id}).json()
        anonymous = next(p for p in result if p['user_id'] == 0)
        self.assertEqual(anonymous['arbiter_identifier'], ' Anonymous ')
        self.assertTrue(anonymous['manual_scores'])

    def test_batches_are_atomic_and_prior_requests_survive(self):
        self.assertEqual(self.post('/scores/users', self.batch([self.row(user_id=self.user.id)])).status_code, 200)
        other = self.create_user('history_second')
        invalid_batches = [
            [], [self.row(user_id=other.id)] * 11,
            [self.row(user_id=other.id)] * 2,
            [self.row(user_id=other.id), self.row(user_id=self.user.id)],
            [self.row(user_id=other.id), self.row(user_id=99999999)],
            [self.row(user_id=other.id, bt1st='1000')],
        ]
        for rows in invalid_batches:
            response = self.post('/scores/users', self.batch(rows))
            self.assertGreaterEqual(response.status_code, 400, response.content)
            self.assertEqual(list(GSCParticipant.objects.values_list('user_id', flat=True)), [self.user.id])

    def test_anonymous_duplicate_identity_is_rejected_without_creating_accounts(self):
        rows = [self.row(arbiter_identifier='first'), self.row(arbiter_identifier='second')]
        response = self.post('/scores/anonymous', self.batch(rows))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.post('/scores/anonymous', self.batch(rows)).status_code, 409)
        self.assertEqual(self.post('/scores/anonymous', self.batch([self.row(arbiter_identifier='')])).status_code, 422)
        self.assertEqual(GSCParticipant.objects.count(), 2)
        self.assertEqual(TournamentUser.objects.count(), 0)

    def test_prepare_does_not_bind_and_each_request_binds_only_one_identifier(self):
        old = self.create_video(identifier='existing', tournament_identifier=['unrelated'])
        old.state = MS_TextChoices.State.IDENTIFIER
        old.save(update_fields=['state'])
        Identifier.objects.create(identifier='existing', safe=True)
        collision = Identifier.objects.create(identifier='taken', safe=True, userms=self.host.userms)
        with patch('tournament.gsc.services.bind_identifier', wraps=bind_identifier) as bind:
            response = self.prepare()
            self.assertEqual(response.status_code, 200, response.content)
            bind.assert_not_called()
            participant_id = response.json()['id']
            for identifier, expected in [('new', True), ('existing', True), ('taken', False), ('new', True)]:
                bind.reset_mock()
                result = self.bind(participant_id, identifier)
                self.assertEqual(result.status_code, 200, result.content)
                self.assertEqual(result.json(), {'identifier': identifier, 'bound': expected})
                self.assertEqual(bind.call_count, int(expected))
        old.refresh_from_db()
        self.assertEqual(old.state, MS_TextChoices.State.OFFICIAL)
        self.assertFalse(self.tournament.videos.exists())
        collision.refresh_from_db()
        self.assertEqual(collision.userms_id, self.host.userms_id)
        self.assertEqual(self.bind(participant_id, ['bulk', 'not allowed']).status_code, 422)
        self.assertFalse(Identifier.objects.filter(identifier__in=['bulk', 'not allowed']).exists())

    def test_failed_binding_preserves_preparation_and_prior_binding_requests(self):
        Identifier.objects.create(identifier='unsafe', safe=False)
        participant_id = self.prepare().json()['id']
        self.assertEqual(self.bind(participant_id, 'safe new').status_code, 200)
        response = self.bind(participant_id, 'unsafe')
        self.assertEqual(response.status_code, 400)
        self.assertTrue(GSCParticipant.objects.filter(pk=participant_id).exists())
        self.assertEqual(Identifier.objects.get(identifier='safe new').userms_id, self.user.userms_id)
        self.assertFalse(Identifier.objects.get(identifier='unsafe').safe)

    def test_upload_reuses_owned_file_keeps_earlier_time_and_rejects_incomplete_or_naive(self):
        participant_id = self.prepare_and_bind().json()['id']
        timestamp = self.tournament.end_time
        response = self.upload(participant_id, timestamp.isoformat())
        self.assertEqual(response.status_code, 200, response.content)
        video = VideoModel.objects.get()
        self.assertEqual(video.state, MS_TextChoices.State.OFFICIAL)
        self.assertEqual(video.upload_time, timestamp)
        self.assertFalse(self.user.has_realname())
        for delta in (1, -1, 0):
            requested = timestamp + timedelta(days=delta)
            with patch('tournament.gsc.services.MSVideoParser') as parse:
                response = self.upload(participant_id, requested.isoformat())
            parse.assert_not_called()
            self.assertEqual(response.status_code, 200, response.content)
            video.refresh_from_db()
            self.assertEqual(video.upload_time, min(requested, timestamp))
            timestamp = video.upload_time
        self.assertEqual(VideoModel.objects.count(), 1)
        self.assertEqual(self.tournament.videos.count(), 1)
        self.assertEqual(self.upload(participant_id, timestamp.replace(tzinfo=None).isoformat()).status_code, 422)
        self.assertEqual(self.upload(participant_id, timestamp.isoformat(), 'incomplete.evf').status_code, 400)
        self.assertEqual(self.client.post(f'/api/tournament/gsc/history/participants/{participant_id}/videos', {'file': self.replay()}).status_code, 422)

    def test_other_owner_cannot_be_reused_or_retimestamped(self):
        participant_id = self.prepare_and_bind().json()['id']
        response = self.upload(participant_id, self.tournament.end_time.isoformat())
        self.assertEqual(response.status_code, 200)
        video = VideoModel.objects.get()
        old_time = video.upload_time
        VideoModel.objects.filter(pk=video.pk).update(player=self.host)
        response = self.upload(participant_id, (old_time - timedelta(days=1)).isoformat())
        self.assertEqual(response.status_code, 409)
        video.refresh_from_db()
        self.assertEqual((video.player_id, video.upload_time), (self.host.pk, old_time))

    def test_upload_keeps_unbound_video_unmatched_and_rejects_unsafe_identifier(self):
        identifier_text = MSVideoParser(self.replay()).identifier
        identifier = Identifier.objects.create(identifier=identifier_text, safe=True)
        participant_id = self.prepare_and_bind(['another selected identifier']).json()['id']
        participant = GSCParticipant.objects.get(pk=participant_id)
        initial_scores = [getattr(participant, field) for field in GSC_SCORE_FIELDS]
        timestamp = self.tournament.end_time
        response = self.upload(participant_id, timestamp.isoformat())
        self.assertEqual(response.status_code, 200, response.content)
        video = VideoModel.objects.get()
        self.assertEqual(video.state, MS_TextChoices.State.IDENTIFIER)
        self.assertTrue(self.tournament.videos.filter(pk=video.pk).exists())
        self.assertEqual(refresh_gsc_scores(self.tournament), 1)
        participant.refresh_from_db()
        self.assertEqual([getattr(participant, field) for field in GSC_SCORE_FIELDS], initial_scores)

        identifier.safe = False
        identifier.save(update_fields=['safe'])
        with patch('tournament.gsc.services.MSVideoParser') as parse:
            response = self.upload(participant_id, (timestamp - timedelta(days=1)).isoformat())
        self.assertEqual(response.status_code, 200, response.content)
        parse.assert_not_called()
        video.refresh_from_db()
        self.assertEqual(video.upload_time, timestamp - timedelta(days=1))
        VideoModel.objects.filter(pk=video.pk).update(original_hash='f' * 24)
        response = self.upload(participant_id, (timestamp - timedelta(days=1)).isoformat())
        self.assertEqual(response.status_code, 400, response.content)
        video.refresh_from_db()
        self.assertEqual(video.upload_time, timestamp - timedelta(days=1))
        self.assertEqual(VideoModel.objects.count(), 1)

    def test_upload_rejects_manual_and_anonymous_participants(self):
        self.assertEqual(self.post('/scores/users', self.batch([self.row(user_id=self.user.pk)])).status_code, 200)
        self.assertEqual(self.post('/scores/anonymous', self.batch([self.row(arbiter_identifier='anonymous')])).status_code, 200)
        response = self.prepare()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['category'], 'not_video_source')
        for participant in GSCParticipant.objects.all():
            response = self.upload(participant.pk, self.tournament.end_time.isoformat())
            self.assertEqual(response.status_code, 409, response.content)
            self.assertEqual(self.bind(participant.pk, 'not bound').status_code, 409)
        self.assertFalse(VideoModel.objects.exists())

    def test_manual_delete_allows_reimport_but_nonofficial_video_blocks_deletion(self):
        payload = self.batch([self.row(user_id=self.user.id)])
        self.assertEqual(self.post('/scores/users', payload).status_code, 200)
        participant = GSCParticipant.objects.get()
        self.assertEqual(self.client.delete(f'/api/tournament/participant/{participant.pk}').status_code, 204)
        self.assertEqual(self.post('/scores/users', payload).status_code, 200)
        participant = GSCParticipant.objects.get()
        video = self.create_video(tournament_identifier=['not matching'])
        video.state = MS_TextChoices.State.IDENTIFIER
        video.save(update_fields=['state'])
        self.tournament.videos.add(video)
        self.assertEqual(self.client.delete(f'/api/tournament/participant/{participant.pk}').status_code, 409)
        listing = self.client.get('/api/tournament/gsc/results', {'tournament_id': self.tournament.id})
        self.assertTrue(listing.json()[0]['has_videos'])

    def test_imported_timestamp_also_controls_automatic_checkin(self):
        parser = MSVideoParser(self.replay())
        now = timezone.now()
        normal = GSCTournament.objects.create(order=2, _token=parser.tournament_identifier[0], state=Tournament_TextChoices.State.NORMAL, start_time=now - timedelta(hours=1), end_time=now + timedelta(hours=1))
        self.tournament_cache.update_tournament(normal)
        self.create_cached_gsc_participant(tournament=normal)
        participant_id = self.prepare_and_bind().json()['id']
        response = self.upload(participant_id, self.tournament.end_time.isoformat())
        self.assertEqual(response.status_code, 200, response.content)
        video = VideoModel.objects.get()
        self.assertFalse(video.ongoing_tournament)
        self.assertFalse(normal.videos.exists())
        self.assertTrue(self.tournament.videos.filter(pk=video.pk).exists())

    def test_staff_can_import_for_another_host_but_fixed_gsc_host_cannot(self):
        fixed_host = self.create_user('fixed_history_host')
        with patch('config.tournaments.GSC_Defaults.HOST_ID', fixed_host.pk):
            self.client.force_login(fixed_host)
            self.assertEqual(self.prepare().status_code, 403)
        fixed_host.is_staff = True
        fixed_host.save(update_fields=['is_staff'])
        self.client.force_login(fixed_host)
        participant_id = self.prepare_and_bind().json()['id']
        self.assertEqual(self.upload(participant_id, self.tournament.end_time.isoformat()).status_code, 200)

    def test_ten_row_batch_creates_unranked_manual_participants(self):
        rows = [self.row(user_id=self.create_user(f'history_batch_{index}').pk) for index in range(10)]
        with self.captureOnCommitCallbacks(execute=True):
            response = self.post('/scores/users', self.batch(rows))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), 10)
        self.assertEqual(TournamentUser.objects.count(), 10)
        self.assertEqual(GSCParticipant.objects.filter(manual_scores=True, rank__isnull=True, rank_score=0).count(), 10)
