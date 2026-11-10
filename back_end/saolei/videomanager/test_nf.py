from types import SimpleNamespace

from django.test import SimpleTestCase

from config.text_choices import MS_TextChoices
from utils.parser import MSVideoParser


class VideoModeTests(SimpleTestCase):
    def test_parser_preserves_mode_independently_of_flags_and_right_ce(self):
        for mode in (0, 5, 10, 11):
            for flag, right_ce in ((0, 0), (1, 0), (0, 1), (1, 1)):
                with self.subTest(mode=mode, flag=flag, right_ce=right_ce):
                    video = SimpleNamespace(mode=mode, flag=flag, rce=right_ce)
                    self.assertEqual(MSVideoParser.get_mode_from_BaseVideo(video, MS_TextChoices.Software.EVF), f'{mode:02d}')

    def test_non_evf_formats_always_count_as_standard(self):
        for software in (MS_TextChoices.Software.AVF, MS_TextChoices.Software.MVF, MS_TextChoices.Software.RMV):
            for mode in (0, 1, 2, 3, 5, 6, 10, 11):
                with self.subTest(software=software, mode=mode):
                    video = SimpleNamespace(mode=mode)
                    self.assertEqual(MSVideoParser.get_mode_from_BaseVideo(video, software), '00')
