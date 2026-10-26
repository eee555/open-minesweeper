import base64
import json
from pathlib import Path

from django.test import SimpleTestCase

from .archive import pack_replay, unpack_replay


class MiniGameReplayArchiveTests(SimpleTestCase):
    def test_shared_browser_and_python_7z_archives(self):
        fixtures = json.loads((Path(__file__).parent / 'fixtures' / 'replay-archives.json').read_text(encoding='utf-8'))
        for writer in ('browser', 'python'):
            with self.subTest(writer=writer):
                self.assertEqual(unpack_replay(base64.b64decode(fixtures[writer])), fixtures['replay'])
        self.assertEqual(unpack_replay(pack_replay(fixtures['replay'])), fixtures['replay'])
