from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models.signals import post_delete
from django.test import Client, override_settings, TestCase

from config.text_choices import Tournament_TextChoices
from msuser.models import UserMS
from tournament.models import TournamentUser, WeeklyParticipant, WeeklyTournament
from userprofile.models import UserProfile
from utils.ranking_lock import RankingRefreshBusy
from .models import ExpandVideoModel, VideoModel


class VideoDeletionTestCaseBase(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        configuration = override_settings(MEDIA_ROOT=media.name)
        configuration.enable()
        self.addCleanup(configuration.disable)
        for target in ['speedranking.services._sync_video', 'effranking.services._sync_video', 'videomanager.cache.cache']:
            replacement = patch(target)
            replacement.start()
            self.addCleanup(replacement.stop)
        self.user = UserProfile.objects.create_user(username='video-delete', email='video-delete@example.com', userms=UserMS.objects.create())

    def create_video(self, *, player=None):
        return VideoModel.objects.create(
            player=player or self.user, video=ExpandVideoModel.objects.create(identifier='delete'),
            file=ContentFile(b'fixture', name='delete.evf'), file_size=7,
            state='a', software='e', level='b', mode='00', bv=4, timems=1000,
        )


class VideoDeletionTests(VideoDeletionTestCaseBase):
    def test_instance_and_queryset_delete_remove_expansion_and_file(self):
        unrelated = ExpandVideoModel.objects.create(identifier='unrelated')
        for queryset in (False, True):
            with self.subTest(queryset=queryset):
                video = self.create_video()
                video_id, expansion_id, path = video.pk, video.video_id, Path(video.file.path)
                with self.captureOnCommitCallbacks(execute=True):
                    if queryset:
                        VideoModel.objects.filter(pk=video_id).delete()
                    else:
                        video.delete()
                self.assertFalse(VideoModel.objects.filter(pk=video_id).exists())
                self.assertFalse(ExpandVideoModel.objects.filter(pk=expansion_id).exists())
                self.assertFalse(path.exists())
                self.assertTrue(ExpandVideoModel.objects.filter(pk=unrelated.pk).exists())

    def test_expansion_origin_does_not_delete_expansion_twice(self):
        events = []

        def deleted(sender, instance, **kwargs):
            events.append(instance.pk)

        post_delete.connect(deleted, sender=ExpandVideoModel, weak=False)
        self.addCleanup(post_delete.disconnect, deleted, sender=ExpandVideoModel)
        for queryset in (False, True):
            with self.subTest(queryset=queryset):
                video = self.create_video()
                video_id, expansion_id = video.pk, video.video_id
                with self.captureOnCommitCallbacks(execute=True):
                    if queryset:
                        ExpandVideoModel.objects.filter(pk=expansion_id).delete()
                    else:
                        video.video.delete()
                self.assertFalse(VideoModel.objects.filter(pk=video_id).exists())
                self.assertEqual(events.count(expansion_id), 1)

    def test_user_queryset_cascade_also_cleans_expansions(self):
        videos = [self.create_video(), self.create_video()]
        expansion_ids = [video.video_id for video in videos]
        paths = [Path(video.file.path) for video in videos]
        with self.captureOnCommitCallbacks(execute=True):
            UserProfile.objects.filter(pk=self.user.pk).delete()
        self.assertFalse(ExpandVideoModel.objects.filter(pk__in=expansion_ids).exists())
        self.assertTrue(all(not path.exists() for path in paths))

    def test_rollback_restores_video_and_expansion_and_keeps_file(self):
        video = self.create_video()
        video_id, expansion_id, path = video.pk, video.video_id, Path(video.file.path)
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaisesMessage(RuntimeError, 'rollback'), transaction.atomic():
                video.delete()
                self.assertFalse(ExpandVideoModel.objects.filter(pk=expansion_id).exists())
                raise RuntimeError('rollback')
        self.assertTrue(VideoModel.objects.filter(pk=video_id).exists())
        self.assertTrue(ExpandVideoModel.objects.filter(pk=expansion_id).exists())
        self.assertTrue(path.exists())


class VideoDeletionApiTests(VideoDeletionTestCaseBase):
    url = '/api/video/admin/delete'

    def setUp(self):
        super().setUp()
        self.superuser = UserProfile.objects.create_user(username='video-delete-superuser', email='video-delete-superuser@example.com', is_superuser=True)

    def test_only_superusers_can_delete_including_without_staff_flag(self):
        video = self.create_video()
        for user, staff in ((None, False), (self.user, False), (self.user, True)):
            with self.subTest(user=user.pk if user else None, staff=staff):
                self.client.logout()
                if user is not None:
                    user.is_staff = staff
                    user.save(update_fields=['is_staff'])
                    self.client.force_login(user)
                self.assertEqual(self.client.get(self.url).status_code, 401)
                response = self.client.post(self.url, {'id': video.pk}, content_type='application/json')
                self.assertEqual(response.status_code, 401, response.content)
                self.assertTrue(VideoModel.objects.filter(pk=video.pk).exists())
        self.client.force_login(self.superuser)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url, {'id': video.pk}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(VideoModel.objects.filter(pk=video.pk).exists())

    def test_rejects_arrays_and_invalid_ids_before_deleting(self):
        video = self.create_video()
        self.client.force_login(self.superuser)
        for payload in ([], [video.pk], {'ids': [video.pk]}, {}, {'id': 0}, {'id': -1}, {'id': True}, {'id': 1.5}, {'id': str(video.pk)}, {'id': None}, {'id': 2**63}):
            with self.subTest(payload=payload):
                response = self.client.post(self.url, payload, content_type='application/json')
                self.assertEqual(response.status_code, 422, response.content)
                self.assertTrue(VideoModel.objects.filter(pk=video.pk).exists())

    def test_deletes_one_video_from_another_owner_and_retries_safely(self):
        other = UserProfile.objects.create_user(username='video-delete-other', email='video-delete-other@example.com', userms=UserMS.objects.create(), is_staff=True)
        video = self.create_video(player=other)
        untouched = self.create_video()
        video_id, expansion_id, path = video.pk, video.video_id, Path(video.file.path)
        self.client.force_login(self.superuser)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url, {'id': video_id}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {'id': video_id, 'deleted': True, 'affected_tournament_ids': []})
        self.assertFalse(VideoModel.objects.filter(pk=video_id).exists())
        self.assertFalse(ExpandVideoModel.objects.filter(pk=expansion_id).exists())
        self.assertFalse(path.exists())
        self.assertTrue(VideoModel.objects.filter(pk=untouched.pk).exists())
        self.assertTrue(Path(untouched.file.path).exists())
        self.user.userms.refresh_from_db()
        other.userms.refresh_from_db()
        self.assertEqual(self.user.userms.video_num_total, 1)
        self.assertEqual(other.userms.video_num_total, 0)
        response = self.client.post(self.url, {'id': video_id}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {'id': video_id, 'deleted': False, 'affected_tournament_ids': []})

    def test_reports_tournaments_and_preserves_settled_results(self):
        video = self.create_video()
        with patch('tournament.signals.cache'), patch('tournament.weekly.signals.tournament_cache'):
            tournament = WeeklyTournament.objects.create(year=2026, week=1, state=Tournament_TextChoices.State.AWARDED)
            participant = WeeklyParticipant.objects.create(tournament=tournament, user=self.user, classic_et=[[video.pk, 1000], [0, 240000]], classic_score=541000, rank=1, rank_score=50)
        tournament.videos.add(video)
        participant_before = WeeklyParticipant.objects.values().get(pk=participant.pk)
        user_before = TournamentUser.objects.values().get(user_id=self.user.pk)
        self.client.force_login(self.superuser)
        with self.captureOnCommitCallbacks(execute=True), self.assertLogs('videomanager', level='WARNING') as logs:
            response = self.client.post(self.url, {'id': video.pk}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['affected_tournament_ids'], [tournament.pk])
        self.assertTrue(any('saved results are not recalculated' in line for line in logs.output))
        self.assertFalse(tournament.videos.exists())
        self.assertEqual(WeeklyParticipant.objects.values().get(pk=participant.pk), participant_before)
        self.assertEqual(TournamentUser.objects.values().get(user_id=self.user.pk), user_before)

    def test_failure_rolls_back_current_video_but_preserves_previous_request(self):
        videos = [self.create_video(), self.create_video()]
        video_ids = [video.pk for video in videos]
        expansion_ids = [video.video_id for video in videos]
        paths = [Path(video.file.path) for video in videos]
        self.client.force_login(self.superuser)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url, {'id': video_ids[0]}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)

        def fail_delete(sender, instance, **kwargs):
            raise RuntimeError('abort video deletion')

        post_delete.connect(fail_delete, sender=VideoModel, weak=False)
        self.addCleanup(post_delete.disconnect, fail_delete, sender=VideoModel)
        self.client.raise_request_exception = False
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url, {'id': video_ids[1]}, content_type='application/json')
        self.assertEqual(response.status_code, 500, response.content)
        self.assertFalse(VideoModel.objects.filter(pk=video_ids[0]).exists())
        self.assertFalse(ExpandVideoModel.objects.filter(pk=expansion_ids[0]).exists())
        self.assertFalse(paths[0].exists())
        self.assertTrue(VideoModel.objects.filter(pk=video_ids[1]).exists())
        self.assertTrue(ExpandVideoModel.objects.filter(pk=expansion_ids[1]).exists())
        self.assertTrue(paths[1].exists())
        self.user.userms.refresh_from_db()
        self.assertEqual(self.user.userms.video_num_total, 1)

    def test_ranking_rebuild_rejects_request_before_deletion(self):
        video = self.create_video()
        self.client.force_login(self.superuser)
        with patch('utils.ranking_lock.ranking_access', side_effect=RankingRefreshBusy):
            response = self.client.post(self.url, {'id': video.pk}, content_type='application/json')
        self.assertEqual(response.status_code, 503, response.content)
        self.assertEqual(response['Retry-After'], '1')
        self.assertTrue(VideoModel.objects.filter(pk=video.pk).exists())

    def test_requires_csrf_token_for_superuser_session(self):
        video = self.create_video()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.superuser)
        response = client.post(self.url, {'id': video.pk}, content_type='application/json')
        self.assertEqual(response.status_code, 403, response.content)
        self.assertTrue(VideoModel.objects.filter(pk=video.pk).exists())
        access = client.get(self.url)
        self.assertEqual(access.status_code, 200, access.content)
        self.assertIn(settings.CSRF_COOKIE_NAME, access.cookies)
        self.assertIn('no-store', access['Cache-Control'])
        token = access.json()['csrf_token']
        with self.captureOnCommitCallbacks(execute=True):
            response = client.post(self.url, {'id': video.pk}, content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(VideoModel.objects.filter(pk=video.pk).exists())

    def test_access_check_does_not_delete_and_trailing_slash_is_not_an_alias(self):
        video = self.create_video()
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.delete(self.url).status_code, 405)
        self.assertEqual(self.client.post(f'{self.url}/', {'id': video.pk}, content_type='application/json').status_code, 404)
        self.assertTrue(VideoModel.objects.filter(pk=video.pk).exists())
