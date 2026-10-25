import base64
from copy import deepcopy
from datetime import timedelta
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, TestCase

from userprofile.models import UserProfile
from .archive import pack_replay, unpack_replay
from .models import MiniGameBestScore
from .replay import migrate_replay, MINE_DIRECTIONS, replay_version
from .utils import RANKINGS


def left_recording():
    return {
        'initialBoard': [[10 if row < 4 else 16 for _ in range(8)] for row in range(8)],
        'events': [
            {'timeMs': 0, 'row': 0.5, 'column': 0.5, 'action': 'lr'},
            {'timeMs': 10, 'row': 0.5, 'column': 1.5, 'action': 'lc'},
            {'timeMs': 25, 'row': 0.5625, 'column': 1.40625, 'action': 'mv'},
            {'timeMs': 25, 'cancelled': True},
            {'timeMs': 25, 'row': 0.5625, 'column': 1.40625, 'action': 'lr'},
            {'timeMs': 30, 'cancelled': True},
        ],
    }


def flag_recording(direction=0):
    board = [[0] * 8 for _ in range(8)]
    for row in (1, 5):
        for column in (1, 5):
            for r in range(row - 1, row + 2):
                for c in range(column - 1, column + 2):
                    board[r][c] = 10
            board[row][column] = 1
            dr, dc = MINE_DIRECTIONS[direction]
            board[row + dr][column + dc] = 16
    return {'initialBoard': board, 'events': []}


def missing_recording():
    board = [[sum((row + dr, column + dc) == (0, 0) for dr, dc in MINE_DIRECTIONS) for column in range(8)] for row in range(8)]
    board[0][0] = 16
    board[7][7] = 10
    return {'rounds': [{'board': deepcopy(board), 'timeMs': 100} for _ in range(10)]}


class MiniGameReplayFormatTests(SimpleTestCase):
    def test_touch_contacts_interleave_and_validate_independently(self):
        ranking = RANKINGS['multi-touch-b-50-v1']
        replay = {
            'version': 1, 'cellSize': 32, 'initialBoard': 'AAAAAP////8',
            'events': [[0, 16, 16, 0, 0], [10, 32, 0, 1, 0], [0, -30, -2, 0, 1], [5, 30, 2, 1, 3], [0, -30, -2, 0, 2], [10, 62, 2, 2, 0]],
        }
        self.assertEqual(migrate_replay(ranking, replay), replay)
        self.assertEqual(unpack_replay(pack_replay(replay)), replay)
        for events in (
            [[0, 16, 16, 0, 1]], [[0, 16, 16, 1, 0]], [[0, 16, 16, 0, 0], [1, 0, 0, 0, 0]],
            [[0, 16, 16, 0, 0], [1, 0, 0, 0, 2], [1, 0, 0, 0, 1]], [[-1, 16, 16, 0, 0]], [[0, 16, 16, 0, 4]],
        ):
            with self.subTest(events=events), self.assertRaises(ValueError):
                migrate_replay(ranking, {**replay, 'events': events})
        with self.assertRaises(ValueError):
            migrate_replay(ranking, left_recording())

    def test_shared_browser_and_python_7z_archives(self):
        fixtures = json.loads((Path(__file__).parent / 'fixtures' / 'replay-archives.json').read_text(encoding='utf-8'))
        for writer in ('browser', 'python'):
            with self.subTest(writer=writer):
                self.assertEqual(unpack_replay(base64.b64decode(fixtures[writer])), fixtures['replay'])
        self.assertEqual(unpack_replay(pack_replay(fixtures['replay'])), fixtures['replay'])

    def test_shared_signed_delta_and_special_insertion_example(self):
        ranking = RANKINGS['left-click-b-50-v1']
        source = left_recording()
        expected = {
            'version': 1, 'cellSize': None, 'initialBoard': 'AAAAAP////8',
            'events': [[0, 16, 16, 2], [10, 32, 0, 1], [15, -3, 2, 0], [0, 0, 0, 2]],
            'specialEvents': [[25, 3, 0], [5, 4, 0]],
        }
        self.assertEqual(replay_version(source), 0)
        self.assertEqual(migrate_replay(ranking, source), expected)
        self.assertEqual(migrate_replay(ranking, {**source, 'version': 0}), expected)
        self.assertEqual(migrate_replay(ranking, expected), expected)
        self.assertNotIn('version', source)
        source['events'] = [{'timeMs': 0, 'row': -0.01, 'column': 2 ** 35, 'action': 'mv'}]
        self.assertEqual(migrate_replay(ranking, source)['events'], [[0, 2 ** 40, -1, 0]])

    def test_question_directions_and_missing_cell_target(self):
        for direction in range(8):
            with self.subTest(direction=direction):
                converted = migrate_replay(RANKINGS['flag-chord-b-v1'], flag_recording(direction))
                self.assertEqual(converted['initialBoard'], [[row, column, direction] for row in (1, 5) for column in (1, 5)])
        converted = migrate_replay(RANKINGS['missing-cell-b-v1'], missing_recording())
        self.assertEqual(converted, {'version': 1, 'rounds': [{'board': 'gAAAAAAAAAA', 'target': [7, 7], 'timeMs': 100} for _ in range(10)]})
        self.assertEqual(migrate_replay(RANKINGS['missing-cell-b-v1'], converted), converted)

    def test_unknown_versions_invalid_padding_and_conflicting_special_times(self):
        ranking = RANKINGS['left-click-b-50-v1']
        for version in (None, True, '1', -1, 2):
            with self.subTest(version=version), self.assertRaises(ValueError):
                migrate_replay(ranking, {**left_recording(), 'version': version})
        converted = migrate_replay(ranking, left_recording())
        for replacement in ({'initialBoard': 'AAAAAP////9'}, {'cellSize': 0}, {'specialEvents': [[26, 3, 0]]}, {'specialEvents': [[0, 5, 0]]}, {'events': [[0, 0, 0, 5]]}):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                migrate_replay(ranking, {**converted, **replacement})


class MiniGameReplayMigrationTests(TestCase):
    def setUp(self):
        self.player = UserProfile.objects.create_user(username='replay-migration', email='replay-migration@example.com')
        sources = (
            ('left-click-b-50-v1', left_recording()),
            ('flag-chord-b-v1', flag_recording()),
            ('missing-cell-b-v1', missing_recording()),
        )
        self.records = [MiniGameBestScore.objects.create(player=self.player, ranking_key=key, score=1000, replay=replay) for key, replay in sources]
        self.current = MiniGameBestScore.objects.create(player=self.player, ranking_key='left-click-b-75-v1', score=2000, replay_archive=pack_replay(migrate_replay(RANKINGS['left-click-b-75-v1'], left_recording())))

    def test_dry_run_then_migrate_all_games_without_changing_scores_or_cache(self):
        output = StringIO()
        call_command('migrate_minigame_replays', dry_run=True, stdout=output)
        self.assertIn('pending=3, migrated=0, skipped=1, invalid=0', output.getvalue())
        for record in self.records:
            record.refresh_from_db()
            self.assertIsNone(record.replay_archive)
            self.assertEqual(replay_version(record.replay), 0)
        previous = [(record.pk, record.score, record.achieved_at, deepcopy(record.replay)) for record in self.records]
        with patch('minigame.cache.MiniGameRankingCache') as cache:
            call_command('migrate_minigame_replays', stdout=StringIO())
        cache.assert_not_called()
        for record, (pk, score, achieved_at, source) in zip(self.records, previous):
            record.refresh_from_db()
            self.assertEqual((record.pk, record.score, record.achieved_at), (pk, score, achieved_at))
            self.assertEqual(unpack_replay(record.replay_archive), migrate_replay(RANKINGS[record.ranking_key], source))
            self.assertIsNone(record.replay)
        output = StringIO()
        call_command('migrate_minigame_replays', stdout=output)
        self.assertIn('pending=0, migrated=0, skipped=4, invalid=0', output.getvalue())

    def test_invalid_record_is_reported_and_preserved_while_other_records_convert(self):
        record = self.records[0]
        invalid = {'version': 42, 'original': 'preserve'}
        MiniGameBestScore.objects.filter(pk=record.pk).update(replay=invalid)
        output, errors = StringIO(), StringIO()
        with self.assertRaises(CommandError):
            call_command('migrate_minigame_replays', stdout=output, stderr=errors)
        record.refresh_from_db()
        self.assertEqual(record.replay, invalid)
        self.assertIsNone(record.replay_archive)
        self.assertIn(f'{record.id} ({record.ranking_key})', errors.getvalue())
        self.assertIn('migrated=2, skipped=1, invalid=1', output.getvalue())

    def test_v1_json_is_compressed_and_corrupt_binary_is_preserved(self):
        record = self.records[0]
        source = migrate_replay(RANKINGS[record.ranking_key], record.replay)
        MiniGameBestScore.objects.filter(pk=record.pk).update(replay=source)
        corrupt = b'not a 7z archive'
        MiniGameBestScore.objects.filter(pk=self.current.pk).update(replay_archive=corrupt)
        with self.assertRaises(CommandError):
            call_command('migrate_minigame_replays', stdout=StringIO(), stderr=StringIO())
        record.refresh_from_db()
        self.assertEqual(unpack_replay(record.replay_archive), source)
        self.assertIsNone(record.replay)
        self.current.refresh_from_db()
        self.assertEqual(self.current.replay_archive, corrupt)

    def test_concurrent_new_best_is_not_overwritten_by_old_replay(self):
        record = self.records[0]
        new_replay = migrate_replay(RANKINGS[record.ranking_key], left_recording())
        new_replay['cellSize'] = 48
        new_time = record.achieved_at + timedelta(seconds=1)

        def concurrent_upload(ranking, source):
            if ranking.key == record.ranking_key:
                MiniGameBestScore.objects.filter(pk=record.pk).update(score=500, achieved_at=new_time, replay_archive=pack_replay(new_replay), replay=None)
            return migrate_replay(ranking, source)

        output = StringIO()
        with patch('minigame.management.commands.migrate_minigame_replays.migrate_replay', side_effect=concurrent_upload):
            call_command('migrate_minigame_replays', stdout=output)
        record.refresh_from_db()
        self.assertEqual(unpack_replay(record.replay_archive), new_replay)
        self.assertEqual((record.score, record.achieved_at), (500, new_time))
        self.assertIn('pending=3, migrated=2, skipped=2, invalid=0', output.getvalue())
