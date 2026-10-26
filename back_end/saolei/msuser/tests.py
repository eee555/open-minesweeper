from datetime import timedelta
from io import StringIO
from urllib.parse import urlencode

from django.core.management import call_command
from django.test import override_settings, TestCase
from django.utils import timezone

from config.text_choices import MS_TextChoices, Tournament_TextChoices
from tournament.models import Tournament
from userprofile.models import UserProfile
from videomanager.models import ExpandVideoModel, VideoModel
from .models import UserMS


class UserMSAdminApiTests(TestCase):
    def setUp(self):
        self.staff = UserProfile.objects.create_user(
            username='msuser_staff',
            email='msuser_staff@example.com',
            password='password',
            is_staff=True,
            userms=UserMS.objects.create(),
        )
        self.userms = UserMS.objects.create(
            identifiers=['alpha', 'beta'],
            video_num_limit=100,
        )
        self.user = UserProfile.objects.create_user(
            username='msuser_player',
            email='msuser_player@example.com',
            password='password',
            userms=self.userms,
        )
        self.client.force_login(self.staff)

    def patch_update(self, userms_id, payload):
        return self.client.patch(
            f'/api/msuser/admin/update/{userms_id}',
            urlencode(payload),
            content_type='application/x-www-form-urlencoded',
        )

    def test_admin_update_user_ms_limit(self):
        old_updated = timezone.now() - timedelta(days=1)
        UserProfile.objects.filter(id=self.user.id).update(date_updated=old_updated)
        self.user.refresh_from_db()
        old_updated = self.user.date_updated

        response = self.patch_update(self.userms.id, {
            'video_num_limit': 250,
        })

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data['identifiers'], ['alpha', 'beta'])
        self.assertEqual(data['video_num_limit'], 250)

        self.user.refresh_from_db()
        self.userms.refresh_from_db()
        self.assertEqual(self.user.date_updated, old_updated)
        self.assertEqual(self.userms.video_num_limit, 250)

    def test_staff_cannot_update_another_staff_user_ms(self):
        other_staff = UserProfile.objects.create_user(
            username='msuser_other_staff',
            email='msuser_other_staff@example.com',
            password='password',
            is_staff=True,
            userms=UserMS.objects.create(video_num_limit=100),
        )

        response = self.patch_update(other_staff.userms_id, {
            'video_num_limit': 250,
        })

        self.assertEqual(response.status_code, 403)
        other_staff.userms.refresh_from_db()
        self.assertEqual(other_staff.userms.video_num_limit, 100)

    def test_non_staff_cannot_use_admin_user_ms_api(self):
        self.client.force_login(self.user)

        response = self.patch_update(self.userms.id, {
            'video_num_limit': 250,
        })

        self.assertEqual(response.status_code, 403)


class UserMSVideoTests(TestCase):
    def setUp(self):
        self.userms = UserMS.objects.create()
        self.user = UserProfile.objects.create_user(
            username='player',
            email='player@example.com',
            password='password',
            userms=self.userms,
        )

    def create_video(self, *, state=MS_TextChoices.State.OFFICIAL, level=MS_TextChoices.Level.BEGINNER, timems=1000, bv=10, mode=MS_TextChoices.Mode.STD, right_ce=1, ongoing_tournament=False):
        expand = ExpandVideoModel.objects.create(identifier='identifier')
        return VideoModel.objects.create(
            player=self.user,
            file='videos/test.avf',
            file_size=1,
            video=expand,
            state=state,
            software=MS_TextChoices.Software.AVF,
            level=level,
            mode=mode,
            ongoing_tournament=ongoing_tournament,
            timems=timems,
            bv=bv,
            left=1,
            right=1,
            double=1,
            left_ce=1,
            right_ce=right_ce,
            double_ce=1,
            path=10,
            flag=1,
            op=1,
            isl=1,
            cell0=1,
            cell1=1,
            cell2=1,
            cell3=1,
            cell4=1,
            cell5=1,
            cell6=1,
            cell7=1,
            cell8=1,
        )

    def test_levels_and_modes_with_nf_each_count_once(self):
        for level, mode in (
            (MS_TextChoices.Level.BEGINNER, MS_TextChoices.Mode.STD),
            (MS_TextChoices.Level.INTERMEDIATE, MS_TextChoices.Mode.JSW),
            (MS_TextChoices.Level.EXPERT, MS_TextChoices.Mode.BZD),
        ):
            with self.subTest(level=level, mode=mode):
                video = self.create_video(level=level, mode=mode, right_ce=0)
                self.userms.refresh_from_db()
                self.assertEqual(self.userms.video_num_total, 1)
                self.assertFalse(video.is_lucky)
                video.delete()
                self.userms.refresh_from_db()
                self.assertEqual(self.userms.video_num_total, 0)
        self.create_video(right_ce=None)
        self.userms.refresh_from_db()
        self.assertEqual(self.userms.video_num_total, 1)

    @override_settings(RATELIMIT_ENABLE=False)
    def test_video_apis_return_right_ce_and_filter_nf_independently(self):
        nf = self.create_video(mode=MS_TextChoices.Mode.JSW, right_ce=0)
        self.create_video(mode=MS_TextChoices.Mode.JSW, right_ce=1)
        unknown = self.create_video(mode=MS_TextChoices.Mode.JSW, right_ce=None)
        self.create_video(mode=MS_TextChoices.Mode.JSW, right_ce=0, ongoing_tournament=True)
        self.create_video(right_ce=0)
        params = {'level': 'b', 'mode': '05', 'nf': True}
        response = self.client.get('/api/video/query', params)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['count'], 1)
        self.assertEqual(response.json()['videos'][0]['id'], nf.id)
        self.assertNotIn('right_ce', response.json()['videos'][0])
        parsed = self.client.get('/api/video/staticdetailbatch', {'ids': nf.id}).json()[0]
        self.assertEqual(parsed['right_ce'], 0)
        response = self.client.get('/api/video/query', {**params, 'nf': False})
        self.assertEqual(response.json()['count'], 3)
        response = self.client.get('/api/video/query_by_id', {'id': self.user.id})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.json()), 4)
        self.assertTrue(all('right_ce' in row for row in response.json()))
        for endpoint in ('infobulk', 'detailbulk'):
            response = self.client.get(f'/api/video/{endpoint}', {'first': nf.id, 'count': 1})
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(response.json()[0]['right_ce'], 0)
            response = self.client.get(f'/api/video/{endpoint}', {'first': unknown.id, 'count': 1})
            self.assertEqual(response.status_code, 200, response.content)
            self.assertIsNone(response.json()[0]['right_ce'])
        response = self.client.get('/api/userprofile/videolist', {'user_id': self.user.id})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(all('right_ce' not in row for row in response.json()))

    def test_create_updates_video_count(self):
        self.create_video()

        self.userms.refresh_from_db()
        self.assertEqual(self.userms.video_num_total, 1)

    def test_frozen_video_updates_video_count(self):
        self.create_video(state=MS_TextChoices.State.FROZEN)

        self.userms.refresh_from_db()
        self.assertEqual(self.userms.video_num_total, 1)

    def test_state_to_official_does_not_update_video_count_again(self):
        video = self.create_video(state=MS_TextChoices.State.FROZEN)

        video.state = MS_TextChoices.State.OFFICIAL
        video.save(update_fields=['state'])

        self.userms.refresh_from_db()
        self.assertEqual(self.userms.video_num_total, 1)

    def test_delete_video_decrements_video_count(self):
        video = self.create_video()

        video.delete()

        self.userms.refresh_from_db()
        self.assertEqual(self.userms.video_num_total, 0)

    def test_tournament_video_is_not_counted_on_create_or_reveal(self):
        video = self.create_video(ongoing_tournament=True)
        self.userms.refresh_from_db()
        self.assertEqual(self.userms.video_num_total, 0)

        video.ongoing_tournament = False
        video.save(update_fields=['ongoing_tournament'])

        self.userms.refresh_from_db()
        self.assertEqual(self.userms.video_num_total, 0)

    def test_deleting_tournament_videos_does_not_decrement_counts(self):
        tournament = Tournament.objects.create(state=Tournament_TextChoices.State.AWARDED)
        for ongoing in (True, False):
            with self.subTest(ongoing=ongoing):
                video = self.create_video(ongoing_tournament=True)
                tournament.videos.add(video)
                VideoModel.objects.filter(pk=video.pk).update(ongoing_tournament=ongoing)

                VideoModel.objects.filter(pk=video.pk).delete()

                self.userms.refresh_from_db()
                self.assertEqual(self.userms.video_num_total, 0)

    def test_refresh_video_counts_excludes_tournaments_and_resets_empty_users(self):
        empty_userms = UserMS.objects.create(video_num_total=9)
        UserProfile.objects.create_user(
            username='empty_player', email='empty_player@example.com', userms=empty_userms,
        )
        other_userms = UserMS.objects.create()
        other_user = UserProfile.objects.create_user(
            username='other_player', email='other_player@example.com', userms=other_userms,
        )
        other_video = self.create_video()
        VideoModel.objects.filter(pk=other_video.pk).update(player=other_user)
        self.create_video(state=MS_TextChoices.State.FROZEN)
        self.create_video(level=MS_TextChoices.Level.INTERMEDIATE, right_ce=0)
        self.create_video(level=MS_TextChoices.Level.EXPERT, mode=MS_TextChoices.Mode.JSW)
        self.create_video(level=MS_TextChoices.Level.EXPERT, mode=MS_TextChoices.Mode.BZD)
        self.create_video(ongoing_tournament=True)
        tournament = Tournament.objects.create(state=Tournament_TextChoices.State.AWARDED)
        other_tournament = Tournament.objects.create()
        revealed = self.create_video()
        tournament.videos.add(revealed)
        other_tournament.videos.add(revealed)
        tournament.videos.add(self.create_video(ongoing_tournament=True))
        self.userms.refresh_from_db()
        old_limit = self.userms.video_num_limit

        UserMS.objects.filter(pk=self.userms.pk).update(video_num_total=99)
        for _ in range(2):
            call_command('refresh_video_counts', batch_size=1, stdout=StringIO())

            self.userms.refresh_from_db()
            empty_userms.refresh_from_db()
            other_userms.refresh_from_db()
            self.assertEqual(self.userms.video_num_total, 4)
            self.assertEqual(empty_userms.video_num_total, 0)
            self.assertEqual(other_userms.video_num_total, 1)
            self.assertEqual(self.userms.video_num_limit, old_limit)

    def test_expert_std_official_video_expands_video_count_limit(self):
        self.create_video(level=MS_TextChoices.Level.EXPERT, timems=59000)

        self.userms.refresh_from_db()
        self.assertEqual(self.userms.video_num_limit, 3000)

    def test_delete_video_does_not_reduce_video_count_limit(self):
        video = self.create_video(level=MS_TextChoices.Level.EXPERT, timems=59000)

        video.delete()

        self.userms.refresh_from_db()
        self.assertEqual(self.userms.video_num_limit, 3000)
