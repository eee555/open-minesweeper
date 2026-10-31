from django.db import transaction
from django.db.models.signals import post_delete
from django.test import TestCase

from config.text_choices import MS_TextChoices
from identifier.models import Identifier
from msuser.models import UserMS
from videomanager.models import ExpandVideoModel, VideoModel
from .models import UserProfile


class UserProfileDeletionTests(TestCase):
    def setUp(self):
        self.userms = UserMS.objects.create(pk=301)
        self.user = UserProfile.objects.create_user(pk=42, username='deleted-player', email='deleted@example.com', userms=self.userms)
        self.other_userms = UserMS.objects.create(pk=42)
        self.other = UserProfile.objects.create_user(pk=301, username='retained-player', email='retained@example.com', userms=self.other_userms)
        self.identifier = Identifier.objects.create(identifier='deleted identifier', safe=True, userms=self.userms)

    def record_userms_deletions(self):
        deleted_ids = []

        def record(sender, instance, **kwargs):
            deleted_ids.append(instance.pk)

        post_delete.connect(record, sender=UserMS, weak=False)
        self.addCleanup(post_delete.disconnect, record, sender=UserMS)
        return deleted_ids

    def test_instance_delete_cleans_actual_userms_and_identifiers(self):
        self.user.delete()
        self.assertFalse(UserProfile.objects.filter(pk=42).exists())
        self.assertFalse(UserMS.objects.filter(pk=301).exists())
        self.assertFalse(Identifier.objects.filter(pk=self.identifier.pk).exists())
        self.assertTrue(UserProfile.objects.filter(pk=301, userms_id=42).exists())
        self.assertTrue(UserMS.objects.filter(pk=42).exists())

    def test_queryset_delete_cleans_each_userms_once(self):
        deleted_ids = self.record_userms_deletions()
        UserProfile.objects.filter(pk__in=[self.user.pk, self.other.pk]).delete()
        self.assertFalse(UserMS.objects.exists())
        self.assertCountEqual(deleted_ids, [301, 42])

    def test_profile_delete_also_cleans_videos_and_expansions(self):
        expansion = ExpandVideoModel.objects.create(identifier=self.identifier.identifier)
        video = VideoModel.objects.create(
            player=self.user, video=expansion, file='videos/deleted-profile.avf', file_size=123,
            software=MS_TextChoices.Software.AVF, state=MS_TextChoices.State.PLAIN,
            level=MS_TextChoices.Level.BEGINNER, mode=MS_TextChoices.Mode.STD, timems=1000, bv=10,
        )
        self.userms.refresh_from_db()
        self.assertEqual(self.userms.video_num_total, 1)
        self.user.delete()
        self.assertFalse(VideoModel.objects.filter(pk=video.pk).exists())
        self.assertFalse(ExpandVideoModel.objects.filter(pk=expansion.pk).exists())
        self.assertFalse(UserMS.objects.filter(pk=301).exists())
        self.assertTrue(UserMS.objects.filter(pk=42).exists())

    def test_profile_without_userms_can_be_deleted(self):
        user = UserProfile.objects.create_user(pk=999, username='no-ms', email='no-ms@example.com')
        user.delete()
        self.assertEqual(UserMS.objects.count(), 2)

    def test_userms_instance_delete_does_not_repeat_cascade(self):
        deleted_ids = self.record_userms_deletions()
        self.userms.delete()
        self.assertEqual(deleted_ids, [301])
        self.assertFalse(UserProfile.objects.filter(pk=42).exists())
        self.assertTrue(UserProfile.objects.filter(pk=301).exists())

    def test_userms_queryset_delete_does_not_repeat_cascade(self):
        deleted_ids = self.record_userms_deletions()
        UserMS.objects.filter(pk=self.userms.pk).delete()
        self.assertEqual(deleted_ids, [301])
        self.assertFalse(UserProfile.objects.filter(pk=42).exists())
        self.assertTrue(UserProfile.objects.filter(pk=301).exists())

    def test_cleanup_failure_rolls_back_profile_and_related_data(self):
        def fail_cleanup(sender, instance, **kwargs):
            raise RuntimeError('cleanup failed')

        post_delete.connect(fail_cleanup, sender=UserMS, weak=False)
        self.addCleanup(post_delete.disconnect, fail_cleanup, sender=UserMS)
        with self.assertRaisesMessage(RuntimeError, 'cleanup failed'), transaction.atomic():
            self.user.delete()
        self.assertTrue(UserProfile.objects.filter(pk=42, userms_id=301).exists())
        self.assertTrue(UserMS.objects.filter(pk=301).exists())
        self.assertTrue(Identifier.objects.filter(pk=self.identifier.pk).exists())
