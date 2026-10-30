import errno
import hashlib
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.test import override_settings, TestCase
import msrc

from msuser.models import UserMS
from userprofile.models import UserProfile
from utils.parser import MSVideoParser
from .files import compress_original, CompressionConfigurationError, original_file
from .models import ExpandVideoModel, VideoModel
from .services import compress_video_file
from .utils import pack_compression_format, unpack_compression_format
from .view_utils import refresh_video


class ReplayCompressionTests(TestCase):
    def setUp(self):
        media = self.enterContext(TemporaryDirectory())
        self.enterContext(override_settings(MEDIA_ROOT=media, RATELIMIT_ENABLE=False, DEBUG=True))
        for target in ('speedranking.services._sync_video', 'effranking.services._sync_video', 'videomanager.cache.cache'):
            self.enterContext(patch(target))
        self.user = UserProfile.objects.create_user(username='compression', email='compression@example.com', userms=UserMS.objects.create())

    def video(self, data=b'original replay bytes', **fields):
        return VideoModel.objects.create(
            player=self.user, video=ExpandVideoModel.objects.create(), file=ContentFile(data, 'example.evf'),
            file_size=len(data), original_hash=hashlib.sha256(data).hexdigest()[:24],
            software='e', level='b', timems=1000, bv=10, **fields,
        )

    def test_new_replay_writes_only_a_verified_archive(self):
        data = (Path(__file__).parents[1] / 'common/test_fixtures/video_upload_ranking/beginner_personal.evf').read_bytes()
        source = ContentFile(data, name='original.evf')
        parser = MSVideoParser(source)
        original_hash = hashlib.sha256(data).hexdigest()[:24]
        with patch.object(default_storage, 'save', wraps=default_storage.save) as save:
            video = VideoModel.create_from_parser(parser, self.user, original_hash=original_hash)
        save.assert_called_once()
        self.assertTrue(save.call_args.args[0].endswith('.msrc'))
        self.assertEqual((video.original_filename, video.file_size, video.original_hash), ('original.evf', len(data), original_hash))
        self.assertEqual(video.compression_format, pack_compression_format(1, 1, 2))
        self.assertEqual(video.stored_file_size, video.file.size)
        self.assertFalse(video.compression_failed)
        self.assertEqual(source.tell(), 0)
        self.assertEqual(source.read(), data)
        files = [path for path in Path(default_storage.location).rglob('*') if path.is_file()]
        self.assertEqual(files, [Path(video.file.path)])
        with original_file(video.file.name, video.compression_format, video.original_filename) as restored:
            self.assertEqual(restored.read(), data)
        with patch('videomanager.services.original_file') as read:
            self.assertEqual(compress_video_file(video), 'skipped')
        read.assert_not_called()

    def test_new_replay_roundtrip_failure_stores_original_and_allows_manual_retry(self):
        data = (Path(__file__).parents[1] / 'common/test_fixtures/video_upload_ranking/beginner_personal.evf').read_bytes()
        source = ContentFile(data, name='original.evf')
        parser = MSVideoParser(source)
        original_hash = hashlib.sha256(data).hexdigest()[:24]
        with patch('videomanager.files.msrc.decompress', return_value=b'corrupt restored bytes'), self.assertLogs('videomanager', level='WARNING'):
            video = VideoModel.create_from_parser(parser, self.user, original_hash=original_hash)
        video.refresh_from_db()
        self.assertEqual((video.compression_format, video.stored_file_size, video.file_size), (0, len(data), len(data)))
        self.assertEqual((video.original_filename, video.original_hash), ('original.evf', original_hash))
        self.assertTrue(video.compression_failed)
        self.assertEqual(source.tell(), 0)
        self.assertEqual(Path(video.file.path).read_bytes(), data)
        self.assertFalse(list(Path(default_storage.location).rglob('*.msrc')))
        response = self.client.get(f'/api/video/download/{video.pk}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Replay-Container-Version'], '0')
        self.assertIn('original.evf', response['Content-Disposition'])
        self.assertEqual(b''.join(response.streaming_content), data)
        self.assertEqual(compress_video_file(video), 'skipped')
        with self.captureOnCommitCallbacks(execute=True):
            call_command('compress_video_files', retry_failed=True, stdout=StringIO())
        video.refresh_from_db()
        self.assertEqual(video.compression_format, pack_compression_format(1, 1, 2))
        self.assertFalse(video.compression_failed)
        with original_file(video.file.name, video.compression_format, video.original_filename) as restored:
            self.assertEqual(restored.read(), data)

    def test_new_replay_format_mismatch_stores_original(self):
        data = (Path(__file__).parents[1] / 'common/test_fixtures/video_upload_ranking/beginner_personal.evf').read_bytes()
        parser = MSVideoParser(ContentFile(data, name='original.evf'))
        wrong_format = msrc.compress(data, algorithm_version=1)
        with patch('videomanager.files.msrc.compress', return_value=wrong_format), self.assertLogs('videomanager', level='WARNING'):
            video = VideoModel.create_from_parser(parser, self.user, original_hash=hashlib.sha256(data).hexdigest()[:24])
        self.assertEqual(video.compression_format, 0)
        self.assertTrue(video.compression_failed)
        self.assertEqual(Path(video.file.path).read_bytes(), data)

    def test_switch_roundtrip_cleanup_and_file_responses_without_save_signals(self):
        video = self.video()
        old_name = video.file.name
        before = (video.upload_time, video.file_size, video.original_hash, video.state, video.player_id)
        with patch.object(VideoModel, 'save', side_effect=AssertionError('No business save')), self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(compress_video_file(video), 'converted')
        video.refresh_from_db()
        self.assertEqual(before, (video.upload_time, video.file_size, video.original_hash, video.state, video.player_id))
        self.assertEqual(video.original_filename, Path(old_name).name)
        self.assertEqual(unpack_compression_format(video.compression_format), (1, 1, 2))
        self.assertEqual(pack_compression_format(1, 1, 2), 0x01010002)
        self.assertFalse(default_storage.exists(old_name))
        with original_file(video.file.name, video.compression_format, video.original_filename) as source:
            self.assertEqual(source.read(), b'original replay bytes')
        for url in (f'/api/video/download/{video.pk}', f'/api/video/preview?id={video.pk}.evf'):
            response = self.client.get(url, HTTP_ORIGIN='http://localhost:8080')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['X-Replay-Container-Version'], '1')
            self.assertIn('X-Replay-Container-Version', response['Access-Control-Expose-Headers'])
            self.assertIn(video.original_filename + '.msrc', response['Content-Disposition'])
            self.assertEqual(msrc.decompress(b''.join(response.streaming_content)), b'original replay bytes')

    def test_failure_is_skipped_until_explicit_retry(self):
        video = self.video()
        old_name = video.file.name
        with patch('videomanager.services.compress_original', side_effect=ValueError('bad archive')):
            self.assertEqual(compress_video_file(video), 'failed')
        video.refresh_from_db()
        self.assertTrue(video.compression_failed)
        self.assertEqual((video.file.name, video.compression_format), (old_name, 0))
        self.assertTrue(default_storage.exists(old_name))
        with patch('videomanager.management.commands.compress_video_files.compress_video_file') as convert:
            call_command('compress_video_files', stdout=StringIO())
        convert.assert_not_called()
        with self.captureOnCommitCallbacks(execute=True):
            call_command('compress_video_files', retry_failed=True, batch_size=1, stdout=StringIO())
        video.refresh_from_db()
        self.assertFalse(video.compression_failed)
        self.assertEqual(video.compression_format, 0x01010002)

    def test_path_race_does_not_overwrite_or_delete_replacement(self):
        video = self.video()
        replacement = default_storage.save('replacement.evf', ContentFile(b'replacement'))  # noqa: DJM100

        def convert(data, target):
            result = compress_original(data, target)
            VideoModel.objects.filter(pk=video.pk).update(file=replacement)
            return result

        with patch('videomanager.services.compress_original', side_effect=convert):
            self.assertEqual(compress_video_file(video), 'skipped')
        video.refresh_from_db()
        self.assertEqual(video.file.name, replacement)
        self.assertTrue(default_storage.exists(replacement))
        self.assertFalse(list(Path(default_storage.location).rglob('*.msrc')))

    def test_environment_or_target_errors_do_not_mark_file_failed(self):
        video = self.video()
        with self.assertRaises(CompressionConfigurationError):
            compress_video_file(video, target=(1, 1, 99))
        with patch('videomanager.services.default_storage.save', side_effect=OSError(errno.ENOSPC, 'Disk full')):
            with self.assertRaises(OSError):
                compress_video_file(video)
        video.refresh_from_db()
        self.assertFalse(video.compression_failed)
        self.assertEqual(video.compression_format, 0)

    def test_compressed_replay_remains_usable_for_refresh_and_hash_backfill(self):
        fixture = Path(__file__).parents[1] / 'common/test_fixtures/video_upload_ranking/beginner_personal.evf'
        data = fixture.read_bytes()
        video = self.video(data)
        with self.captureOnCommitCallbacks(execute=True):
            compress_video_file(video)
        video.refresh_from_db()
        refresh_video(video)
        self.assertEqual(video.file_size, len(data))
        VideoModel.objects.filter(pk=video.pk).update(original_hash=None)
        call_command('backfill_video_hashes', stdout=StringIO())
        video.refresh_from_db()
        self.assertEqual(video.original_hash, hashlib.sha256(data).hexdigest()[:24])

    def test_dry_run_and_private_video_access(self):
        video = self.video(ongoing_tournament=True)
        with patch('videomanager.management.commands.compress_video_files.compress_video_file') as convert:
            call_command('compress_video_files', dry_run=True, stdout=StringIO())
        convert.assert_not_called()
        with self.captureOnCommitCallbacks(execute=True):
            compress_video_file(video)
        self.assertEqual(self.client.get(f'/api/video/download/{video.pk}').status_code, 403)
        self.client.force_login(self.user)
        response = self.client.get(f'/api/video/download/{video.pk}')
        self.assertEqual(response.status_code, 200)
        b''.join(response.streaming_content)
