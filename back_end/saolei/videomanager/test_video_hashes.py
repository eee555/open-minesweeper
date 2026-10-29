from django.core.files.uploadedfile import SimpleUploadedFile, TemporaryUploadedFile
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from userprofile.models import UserProfile
from .models import ExpandVideoModel, VideoModel
from .utils import calculate_original_hash


class OriginalHashTests(SimpleTestCase):
    def test_hashes_entire_memory_or_temporary_upload_and_rewinds_for_parser(self):
        uploads = [SimpleUploadedFile('hash.evf', b'abc'), TemporaryUploadedFile('hash.evf', 'application/octet-stream', 3, None)]
        for upload in uploads:
            with self.subTest(upload=type(upload).__name__), upload:
                if isinstance(upload, TemporaryUploadedFile):
                    upload.write(b'abc')
                upload.seek(2)
                self.assertEqual(calculate_original_hash(upload), 'ba7816bf8f01cfea414140de')
                self.assertEqual(upload.tell(), 0)
                self.assertEqual(upload.read(), b'abc')


class OriginalHashUniquenessTests(TestCase):
    def test_database_rejects_duplicate_hashes_but_allows_multiple_nulls(self):
        user = UserProfile.objects.create_user(username='unique-hash', email='unique-hash@example.com')
        VideoModel.objects.bulk_create([
            VideoModel(player=user, video=ExpandVideoModel.objects.create(), file='hash.evf', software='e', level='b')
            for _ in range(3)
        ])
        video_ids = list(VideoModel.objects.order_by('pk').values_list('pk', flat=True))
        self.assertEqual(VideoModel.objects.filter(original_hash__isnull=True).count(), 3)
        original_hash = 'ba7816bf8f01cfea414140de'
        self.assertEqual(VideoModel.objects.filter(pk=video_ids[0]).update(original_hash=original_hash), 1)

        with self.assertRaises(IntegrityError), transaction.atomic():
            VideoModel.objects.filter(pk=video_ids[1]).update(original_hash=original_hash)

        self.assertEqual(VideoModel.objects.filter(original_hash=original_hash).count(), 1)
        self.assertEqual(VideoModel.objects.filter(original_hash__isnull=True).count(), 2)
