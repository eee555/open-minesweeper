import os
from pathlib import Path
import signal
from subprocess import run, TimeoutExpired
from unittest.mock import Mock, patch

from django.core.files.base import ContentFile
from django.test import SimpleTestCase

from config.text_choices import MS_TextChoices
from .exceptions import ExceptionToResponse
from .parser import MSVideoParser, pack_board_bitmap

FIXTURES = Path(__file__).resolve().parents[1] / 'common/test_fixtures/video_upload_ranking'


def abort_parser_process(command, **kwargs):
    # Linux CI 使用真正的 SIGABRT；Windows 用立即退出避免系统崩溃对话框。
    script = (
        'import os\n'
        'if os.name == "posix":\n'
        '    import resource\n'
        '    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))\n'
        '    os.abort()\n'
        'os._exit(134)\n'
    )
    return run([command[0], '-X', 'faulthandler', '-c', script], **kwargs)


class BoardBitmapTests(SimpleTestCase):
    def test_row_major_lsb_first_packing(self):
        board = [
            [-1, 0, 1, -1],
            [2, -1, 3, 4],
            [-1, 5, 6, -1],
        ]
        self.assertEqual(pack_board_bitmap(board), b'\x29\x09')

    def test_marks_all_mines_without_neighbor_numbers(self):
        self.assertEqual(pack_board_bitmap([[-1, 8], [7, -1]]), b'\x09')

    def test_rejects_empty_and_ragged_boards(self):
        for board in ([], [[]], [[-1, 0], [-1]], [[0, 1], [2]]):
            with self.subTest(board=board), self.assertRaises(ExceptionToResponse) as error:
                pack_board_bitmap(board)
            self.assertEqual(error.exception.body, {'type': 'error', 'object': 'file', 'category': 'level'})

    def test_parser_stores_packed_board_from_native_board(self):
        video = Mock(is_completed=True, level=3, mode=10, software='Arbiter 0.52.3', end_time=0, player_identifier='', race_identifier='', board=[[-1, 8], [7, -1]])
        video.is_valid.return_value = 0
        with patch('utils.parser.MSVideoParser.read_file', return_value=(video, MS_TextChoices.Software.EVF)), patch('utils.parser.calculate_pluck_from_video', return_value=None):
            parser = MSVideoParser(ContentFile(b'replay', name='replay.evf'))
        self.assertEqual(parser.board, b'\x09')


class SkipPluckParserTests(SimpleTestCase):
    def test_skip_pluck_avoids_expensive_analysis_in_both_entry_points(self):
        for metadata_only in [False, True]:
            with self.subTest(metadata_only=metadata_only):
                video = Mock(is_completed=True, level=3, mode=10, software='Arbiter 0.52.3', player_identifier='', race_identifier='', end_time=0, board=[[-1]])
                video.is_valid.return_value = 0
                parser_method = MSVideoParser.parse_video_metadata if metadata_only else MSVideoParser
                read_path = 'utils.parser.create_video_from_data' if metadata_only else 'utils.parser.MSVideoParser.read_file'
                with patch(read_path, return_value=(video, MS_TextChoices.Software.EVF)), patch('utils.parser.calculate_pluck_from_video') as pluck:
                    result = parser_method(ContentFile(b'replay', name='replay'), skip_pluck=True)
                pluck.assert_not_called()
                self.assertIsNone(result['pluck'] if metadata_only else result.pluck)

    def test_isolated_skip_pluck_preserves_metadata_and_null_pluck(self):
        name = 'expert_personal.evf'
        file = ContentFile((FIXTURES / name).read_bytes(), name=name)
        parser = MSVideoParser(file, isolate=True, skip_pluck=True)
        self.assertIsNone(parser.pluck)
        self.assertEqual(sum(byte.bit_count() for byte in parser.board), 99)


class IncompleteVideoParserTests(SimpleTestCase):
    def test_both_parser_entry_points_normalize_modes_by_file_format(self):
        for metadata_only in [False, True]:
            for software in MS_TextChoices.Software:
                with self.subTest(metadata_only=metadata_only, software=software):
                    video = Mock(is_completed=True, level=3, mode=10, software='Arbiter 0.52.3', player_identifier='player', race_identifier='', end_time=0, board=[[-1]])
                    video.is_valid.return_value = 0
                    parser_method = MSVideoParser.parse_video_metadata if metadata_only else MSVideoParser
                    read_path = 'utils.parser.create_video_from_data' if metadata_only else 'utils.parser.MSVideoParser.read_file'
                    with patch(read_path, return_value=(video, software)), patch('utils.parser.calculate_pluck_from_video', return_value=None) as pluck:
                        result = parser_method(ContentFile(b'replay', name='replay'))
                    expected = '10' if software == MS_TextChoices.Software.EVF else '00'
                    self.assertEqual(result['mode'] if metadata_only else result.mode, expected)
                    self.assertEqual(result['version'] if metadata_only else result.version, video.software)
                    pluck.assert_called_once_with(video, MS_TextChoices.Level.BEGINNER, expected)

    def test_incomplete_video_is_rejected_before_review_or_feature_analysis(self):
        for metadata_only in [False, True]:
            with self.subTest(metadata_only=metadata_only):
                video = Mock(is_completed=False)
                video.is_valid.return_value = 0
                parser_method = MSVideoParser.parse_video_metadata if metadata_only else MSVideoParser
                read_path = 'utils.parser.create_video_from_data' if metadata_only else 'utils.parser.MSVideoParser.read_file'
                with patch(read_path, return_value=(video, MS_TextChoices.Software.EVF)):
                    with self.assertRaises(ExceptionToResponse) as error:
                        parser_method(ContentFile(b'replay', name='incomplete.evf'))

                self.assertEqual(error.exception.body, {'type': 'error', 'object': 'file', 'category': 'incomplete'})
                video.is_valid.assert_not_called()
                video.analyse_for_features.assert_not_called()


class IsolatedVideoParserTests(SimpleTestCase):
    def test_click_paths_are_preserved_by_both_parser_entry_points(self):
        name = 'expert_personal.evf'
        file = ContentFile((FIXTURES / name).read_bytes(), name=name)
        video, _ = MSVideoParser.read_file(file)
        video.parse()
        video.analyse()
        video.current_time = 1e8
        expected = (video.c_path, video.e_path)
        self.assertGreater(expected[0], 0)
        self.assertGreater(expected[1], 0)

        parser = MSVideoParser(file)
        self.assertEqual((parser.cpath, parser.epath), expected)
        self.assertEqual(parser.version, video.software)
        metadata = MSVideoParser.parse_video_metadata(file)
        self.assertEqual((metadata['cpath'], metadata['epath']), expected)
        self.assertEqual(metadata['version'], video.software)

    def test_isolated_parser_preserves_all_fields_and_rewinds_the_original_file(self):
        for name in ['beginner_personal.evf', 'expert_personal.evf', 'custom_pluck.evf', 'standard_gsc.evf']:
            with self.subTest(name=name):
                file = ContentFile((FIXTURES / name).read_bytes(), name=name)
                expected = MSVideoParser(file)
                file.seek(5)
                actual = MSVideoParser(file, isolate=True)
                self.assertEqual(vars(actual), vars(expected))
                self.assertIs(actual.file, file)
                self.assertIs(actual.tournament_identifier, actual.tournament_identifiers)
                self.assertEqual(file.tell(), 0)

    def test_file_validation_errors_keep_their_category(self):
        for name, category in [('incomplete.evf', 'incomplete'), ('unsupported.txt', 'type')]:
            with self.subTest(name=name):
                data = (FIXTURES / name).read_bytes() if category == 'incomplete' else b'unsupported'
                with self.assertRaises(ExceptionToResponse) as error:
                    MSVideoParser(ContentFile(data, name=name), isolate=True)
                self.assertEqual(error.exception.body, {'type': 'error', 'object': 'file', 'category': category})

    def test_aborted_child_does_not_terminate_the_caller_or_prevent_the_next_parse(self):
        with patch('utils.parser.subprocess.run', side_effect=abort_parser_process):
            with self.assertLogs('utils.parser', level='ERROR') as logs, self.assertRaises(ExceptionToResponse) as error:
                MSVideoParser(ContentFile(b'crash', name='crashing.evf'), isolate=True)
        self.assertEqual(error.exception.body, {'type': 'error', 'object': 'rust', 'category': 'panic'})
        self.assertEqual(error.exception.status_code, 500)
        exit_code = -signal.SIGABRT if os.name == 'posix' else 134
        self.assertIn(f'exit_code={exit_code}', logs.output[0])
        self.assertIn('crashing.evf', logs.output[0])
        name = 'beginner_personal.evf'
        self.assertGreater(MSVideoParser(ContentFile((FIXTURES / name).read_bytes(), name=name), isolate=True).bv, 0)

    def test_timeout_is_a_parser_failure_and_does_not_reject_the_file(self):
        with patch('utils.parser.subprocess.run', side_effect=TimeoutExpired('parser', 60)):
            with self.assertLogs('utils.parser', level='ERROR'), self.assertRaises(ExceptionToResponse) as error:
                MSVideoParser(ContentFile(b'slow', name='slow.evf'), isolate=True)
        self.assertEqual(error.exception.body, {'type': 'error', 'object': 'rust', 'category': 'panic'})
        self.assertEqual(error.exception.status_code, 500)
