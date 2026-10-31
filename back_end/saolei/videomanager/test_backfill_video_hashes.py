import hashlib
from io import StringIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command, CommandError
from django.test import override_settings, TestCase

from msuser.models import UserMS
from userprofile.models import UserProfile
from .models import ExpandVideoModel, VideoModel


class BackfillVideoHashesTests(TestCase):
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
        self.user = UserProfile.objects.create_user(username='hash-backfill', email='hash@example.com', userms=UserMS.objects.create())

    def create_video(self, data, **fields):
        return VideoModel.objects.create(
            player=self.user, video=ExpandVideoModel.objects.create(identifier='hash'),
            file=ContentFile(data, name='hash.evf'), file_size=len(data),
            state='a', software='e', level='b', mode='00', bv=4, timems=1000, **fields,
        )

    def test_hashes_raw_bytes_without_parsing_or_saving_and_can_be_rerun(self):
        first = self.create_video(b'abc')
        second = self.create_video(b'\x00\xff' * 200000, original_hash='', ongoing_tournament=True)
        existing = self.create_video(b'previously hashed', original_hash='f' * 24)
        before = list(VideoModel.objects.order_by('pk').values('id', 'file', 'file_size', 'state', 'player_id', 'ongoing_tournament'))
        output = StringIO()

        with patch.object(VideoModel, 'save', side_effect=AssertionError('No save signals')), patch('videomanager.models.MSVideoParser', side_effect=AssertionError('No parser')):
            call_command('backfill_video_hashes', batch_size=1, step=1, stdout=output)

        first.refresh_from_db()
        second.refresh_from_db()
        existing.refresh_from_db()
        self.assertEqual(first.original_hash, 'ba7816bf8f01cfea414140de')
        self.assertEqual(second.original_hash, hashlib.sha256(b'\x00\xff' * 200000).hexdigest()[:24])
        self.assertEqual(existing.original_hash, 'f' * 24)
        self.assertEqual(before, list(VideoModel.objects.order_by('pk').values('id', 'file', 'file_size', 'state', 'player_id', 'ongoing_tournament')))
        self.assertIn('0/2（0.0%）', output.getvalue())
        self.assertIn('2/2（100.0%）', output.getvalue())
        with patch('videomanager.management.commands.backfill_video_hashes.default_storage.open', side_effect=AssertionError('Already filled')):
            call_command('backfill_video_hashes', stdout=StringIO())

    def test_missing_file_does_not_skip_later_batches_and_range_end_is_exclusive(self):
        missing = self.create_video(b'missing')
        valid = self.create_video(b'abc')
        outside = self.create_video(b'outside')
        default_storage.delete(missing.file.name)
        output, errors = StringIO(), StringIO()

        call_command('backfill_video_hashes', start=missing.pk, end=outside.pk, batch_size=1, step=1, stdout=output, stderr=errors)

        missing.refresh_from_db()
        valid.refresh_from_db()
        outside.refresh_from_db()
        self.assertIsNone(missing.original_hash)
        self.assertEqual(valid.original_hash, 'ba7816bf8f01cfea414140de')
        self.assertIsNone(outside.original_hash)
        self.assertIn(f'录像#{missing.pk}文件不存在', errors.getvalue())
        self.assertIn('已回填 1 条，失败 1 条', output.getvalue())
        self.assertIn('2/2（100.0%）', output.getvalue())

    def test_environment_error_stops_command_and_completed_hashes_survive_restart(self):
        first = self.create_video(b'abc')
        second = self.create_video(b'later')
        open_file = default_storage.open

        def open_with_error(name, mode):
            if name == second.file.name:
                raise PermissionError(13, 'Permission denied')
            return open_file(name, mode)

        with patch('videomanager.management.commands.backfill_video_hashes.default_storage.open', side_effect=open_with_error):
            with self.assertRaises(CommandError):
                call_command('backfill_video_hashes', batch_size=1, stdout=StringIO())
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.original_hash, 'ba7816bf8f01cfea414140de')
        self.assertIsNone(second.original_hash)
        call_command('backfill_video_hashes', stdout=StringIO())
        second.refresh_from_db()
        self.assertEqual(second.original_hash, hashlib.sha256(b'later').hexdigest()[:24])

    def test_replaced_file_does_not_receive_hash_of_old_file(self):
        video = self.create_video(b'old')
        replacement = default_storage.save('replacement.evf', ContentFile(b'new'))  # noqa: DJM100
        file_digest = hashlib.file_digest

        def hash_and_replace(file, algorithm):
            digest = file_digest(file, algorithm)
            VideoModel.objects.filter(pk=video.pk).update(file=replacement)
            return digest

        output = StringIO()
        with patch('videomanager.utils.hashlib.file_digest', side_effect=hash_and_replace):
            call_command('backfill_video_hashes', stdout=output)

        video.refresh_from_db()
        self.assertEqual(video.file.name, replacement)
        self.assertIsNone(video.original_hash)
        self.assertIn('跳过 1 条', output.getvalue())
