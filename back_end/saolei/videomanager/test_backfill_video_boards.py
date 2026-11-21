from io import StringIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.management import call_command, CommandError
from django.test import override_settings, TestCase

from msuser.models import UserMS
from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from .models import ExpandVideoModel, VideoModel


class BackfillVideoBoardsTests(TestCase):
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
        self.user = UserProfile.objects.create_user(username='board-backfill', email='board@example.com', userms=UserMS.objects.create())

    def create_video(self, name=b'abc', **fields):
        return VideoModel.objects.create(
            player=self.user, video=ExpandVideoModel.objects.create(identifier='board'),
            file=ContentFile(name, name='board.evf'), file_size=len(name),
            state='a', software='e', level='b', mode='00', bv=4, timems=1000, **fields,
        )

    def test_fills_only_missing_boards_without_saving(self):
        first = self.create_video()
        second = self.create_video()
        filled = self.create_video(board=b'\x01')
        output = StringIO()

        def fake_parser(file, *, isolate=False):
            self.assertTrue(isolate)
            return type('Parser', (), {'board': b'\x09'})()

        with patch('videomanager.management.commands.backfill_video_boards.MSVideoParser', side_effect=fake_parser), patch.object(VideoModel, 'save', side_effect=AssertionError('No save signals')):
            call_command('backfill_video_boards', stdout=output)

        first.refresh_from_db()
        second.refresh_from_db()
        filled.refresh_from_db()
        self.assertEqual((first.board, second.board), (b'\x09', b'\x09'))
        self.assertEqual(filled.board, b'\x01')
        self.assertIn('已回填 2', output.getvalue())

    def test_parse_failure_keeps_board_null_and_continues(self):
        failed = self.create_video()
        succeeded = self.create_video()
        output, errors = StringIO(), StringIO()

        with patch('videomanager.management.commands.backfill_video_boards.MSVideoParser', side_effect=[ExceptionToResponse('file', 'type'), type('Parser', (), {'board': b'\x03'})()]):
            call_command('backfill_video_boards', stdout=output, stderr=errors)

        failed.refresh_from_db()
        succeeded.refresh_from_db()
        self.assertIsNone(failed.board)
        self.assertEqual(succeeded.board, b'\x03')
        self.assertIn(f'录像#{failed.pk}解析失败', errors.getvalue())
        self.assertIn('失败 1', output.getvalue())

    def test_invalid_arguments_are_rejected_before_any_query(self):
        for options in ({'start': -1}, {'end': -1}, {'start': 2, 'end': 1}, {'step': 0}, {'batch_size': 0}):
            with self.subTest(options=options), self.assertRaises(CommandError):
                call_command('backfill_video_boards', stdout=StringIO(), **options)
