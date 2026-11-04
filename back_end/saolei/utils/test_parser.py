from unittest.mock import Mock, patch

from django.core.files.base import ContentFile
from django.test import SimpleTestCase

from config.text_choices import MS_TextChoices
from .exceptions import ExceptionToResponse
from .parser import MSVideoParser


class IncompleteVideoParserTests(SimpleTestCase):
    def test_both_parser_entry_points_normalize_modes_by_file_format(self):
        for metadata_only in [False, True]:
            for software in MS_TextChoices.Software:
                with self.subTest(metadata_only=metadata_only, software=software):
                    video = Mock(is_completed=True, level=3, mode=10, player_identifier='player', race_identifier='', end_time=0)
                    video.is_valid.return_value = 0
                    parser_method = MSVideoParser.parse_video_metadata if metadata_only else MSVideoParser
                    read_path = 'utils.parser.create_video_from_data' if metadata_only else 'utils.parser.MSVideoParser.read_file'
                    with patch(read_path, return_value=(video, software)), patch('utils.parser.calculate_pluck_from_video', return_value=None) as pluck:
                        result = parser_method(ContentFile(b'replay', name='replay'))
                    expected = '10' if software == MS_TextChoices.Software.EVF else '00'
                    self.assertEqual(result['mode'] if metadata_only else result.mode, expected)
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
