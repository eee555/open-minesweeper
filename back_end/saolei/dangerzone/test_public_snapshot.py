from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management.base import CommandError
from django.db import connection
from django.test import override_settings, SimpleTestCase, TestCase
import requests

from config.text_choices import MS_TextChoices
from identifier.models import Identifier
from msuser.models import UserMS
from videomanager.models import VideoModel
from .download_public_data import download, PublicClient
from .public_snapshot import import_snapshot_rows, initialize_local_data, validate_import
from .utils import file_entry, read_json, validate_snapshot, write_json


USERS = [{'id': 2, 'username': 'admin'}, {'id': 48, 'username': 'user'}, {'id': 99, 'username': 'empty'}]
IDENTIFIERS = {2: ['Admin sign'], 48: ['User Sign', '用户 %_\\'], 99: []}


def make_snapshot(root, *, version=2, identifiers=None, videos=None):
    identifiers = IDENTIFIERS if identifiers is None else identifiers
    videos = [] if videos is None else videos
    write_json(root / 'users.json', USERS)
    write_json(root / 'videos.json', videos)
    manifest = {
        'version': version, 'complete': True, 'users': [file_entry(root, root / 'users.json')],
        'videos': [file_entry(root, root / 'videos.json')], 'user_count': len(USERS), 'video_count': len(videos),
    }
    if version == 2:
        manifest['identifiers'] = []
        for user_id, texts in identifiers.items():
            path = root / 'identifiers' / f'{user_id}.json'
            write_json(path, texts)
            manifest['identifiers'].append({**file_entry(root, path), 'user_id': user_id})
        manifest['identifier_count'] = sum(map(len, identifiers.values()))
    write_json(root / 'manifest.json', manifest)
    return manifest


class PublicIdentifierDownloadTests(SimpleTestCase):
    def public_get(self, path, params):
        if path.endswith('/infoupdated'):
            return [row['id'] for row in USERS]
        if path.endswith('/infobulk'):
            return USERS
        if path.endswith('/identifier'):
            return IDENTIFIERS[params['user_id']]
        self.assertEqual(path, '/api/userprofile/videolist')
        return []

    def test_download_records_every_users_identifiers_and_reuses_completed_snapshot(self):
        with TemporaryDirectory() as directory, redirect_stdout(StringIO()):
            root = Path(directory)
            client = PublicClient('https://example.invalid')
            with patch.object(client, 'get', side_effect=self.public_get):
                download(root, client)
            manifest, users = validate_snapshot(root)
            self.assertEqual(manifest['version'], 2)
            self.assertEqual(manifest['identifier_count'], 3)
            self.assertEqual({user_id: row['identifiers'] for user_id, row in users.items()}, IDENTIFIERS)
            with patch.object(client, 'get') as request:
                download(root, client)
                request.assert_not_called()

    def test_interrupted_download_resumes_without_refetching_completed_users(self):
        def interrupted_get(path, params):
            if path.endswith('/identifier') and params['user_id'] == 48:
                raise requests.ConnectionError('Interrupted')
            return self.public_get(path, params)

        with TemporaryDirectory() as directory, redirect_stdout(StringIO()):
            root = Path(directory)
            client = PublicClient('https://example.invalid')
            with patch.object(client, 'get', side_effect=interrupted_get), self.assertRaises(requests.ConnectionError):
                download(root, client)
            self.assertFalse(read_json(root / 'manifest.json')['complete'])
            with patch.object(client, 'get', side_effect=self.public_get) as request:
                download(root, client)
            identifier_ids = [call.args[1]['user_id'] for call in request.call_args_list if call.args[0].endswith('/identifier')]
            self.assertEqual(identifier_ids, [48, 99])
            self.assertEqual(validate_snapshot(root)[0]['identifier_count'], 3)

    def test_repeated_identifiers_for_the_same_user_are_normalized(self):
        def get(path, params):
            result = self.public_get(path, params)
            if path.endswith('/identifier') and params['user_id'] == 48:
                return [*result, result[0], result[0]]
            return result

        with TemporaryDirectory() as directory, redirect_stdout(StringIO()):
            root = Path(directory)
            client = PublicClient('https://example.invalid')
            with patch.object(client, 'get', side_effect=get):
                download(root, client)
            manifest, users = validate_snapshot(root)
            self.assertEqual(manifest['identifier_count'], 3)
            self.assertEqual(users[48]['identifiers'], IDENTIFIERS[48])
            self.assertEqual(read_json(root / 'identifiers' / '48.json'), IDENTIFIERS[48])

    def test_completed_legacy_snapshot_only_downloads_identifiers_and_can_resume_upgrade(self):
        with TemporaryDirectory() as directory, redirect_stdout(StringIO()):
            root = Path(directory)
            original = make_snapshot(root, version=1)
            client = PublicClient('https://example.invalid')
            write_json(root / 'identifiers' / '2.json', IDENTIFIERS[2])
            with patch.object(client, 'get', side_effect=requests.ConnectionError('Interrupted')), self.assertRaises(requests.ConnectionError):
                download(root, client)
            self.assertEqual(read_json(root / 'manifest.json'), original)
            with patch.object(client, 'get', side_effect=self.public_get) as request:
                download(root, client)
            self.assertEqual([call.args for call in request.call_args_list], [
                ('/api/userprofile/identifier', {'user_id': 48}), ('/api/userprofile/identifier', {'user_id': 99}),
            ])
            manifest, users = validate_snapshot(root)
            self.assertEqual(manifest['users'], original['users'])
            self.assertEqual(manifest['videos'], original['videos'])
            self.assertEqual({user_id: row['identifiers'] for user_id, row in users.items()}, IDENTIFIERS)

    def test_invalid_or_conflicting_identifier_lists_are_rejected(self):
        invalid_lists = [[7], [''], ['x' * 129], ['duplicate', 'duplicate'], ['Admin sign']]
        for texts in invalid_lists:
            with self.subTest(texts=texts), TemporaryDirectory() as directory:
                root = Path(directory)
                make_snapshot(root, identifiers={**IDENTIFIERS, 48: texts})
                with self.assertRaises(ValueError):
                    validate_snapshot(root)

    def test_incomplete_coverage_unknown_users_and_counts_are_rejected(self):
        for kind in ['missing', 'unknown', 'duplicate', 'count']:
            with self.subTest(kind=kind), TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = make_snapshot(root)
                if kind == 'missing':
                    manifest['identifiers'].pop()
                elif kind == 'unknown':
                    manifest['identifiers'][0]['user_id'] = 1234
                elif kind == 'duplicate':
                    manifest['identifiers'].append(manifest['identifiers'][0])
                else:
                    manifest['identifier_count'] += 1
                write_json(root / 'manifest.json', manifest)
                with self.assertRaises(ValueError):
                    validate_snapshot(root)

    def test_identifier_files_are_checksummed(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            make_snapshot(root)
            write_json(root / 'identifiers' / '48.json', ['Changed'])
            with self.assertRaisesMessage(ValueError, 'checksum mismatch'):
                validate_snapshot(root)


class PublicIdentifierImportTests(TestCase):
    def test_import_restores_both_sides_of_ownership_without_changing_video_states(self):
        video = {
            'id': 100, 'player': 48, 'level': 'b', 'mode': '00', 'state': MS_TextChoices.State.IDENTIFIER,
            'software': 'e', 'timems': 1000, 'bv': 4, 'upload_time': '2026-10-05T12:34:00Z',
            'left': 1, 'right': 0, 'double': 0, 'left_ce': 1, 'right_ce': 0, 'double_ce': 0, 'path': 10,
            'video__identifier': 'User Sign',
        }
        with TemporaryDirectory() as directory:
            root = Path(directory)
            make_snapshot(root, videos=[video])
            manifest, users = validate_snapshot(root)
            validate_import(root, manifest, users)
            import_snapshot_rows(root, manifest, users, 'admin-password', 'user-password')
        self.assertEqual(dict(UserMS.objects.values_list('id', 'identifiers')), IDENTIFIERS)
        self.assertEqual(dict(Identifier.objects.values_list('identifier', 'userms_id')), {
            text: user_id for user_id, texts in IDENTIFIERS.items() for text in texts
        })
        self.assertFalse(Identifier.objects.filter(safe=False).exists())
        imported = VideoModel.objects.select_related('video').get(id=100)
        self.assertEqual(imported.state, MS_TextChoices.State.IDENTIFIER)
        self.assertEqual(imported.video.identifier, 'User Sign')

    def test_legacy_snapshot_still_imports_with_empty_identifier_lists(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            make_snapshot(root, version=1)
            manifest, users = validate_snapshot(root)
            import_snapshot_rows(root, manifest, users, 'admin-password', 'user-password')
        self.assertEqual(list(UserMS.objects.values_list('identifiers', flat=True)), [[], [], []])
        self.assertFalse(Identifier.objects.exists())

    def test_invalid_identifiers_stop_initialization_before_any_reset(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            make_snapshot(root, identifiers={**IDENTIFIERS, 48: ['Admin sign']})
            with override_settings(PRODUCTION_MARK=root / '.production', DEBUG=True, E2E_TEST=True), patch.dict(connection.settings_dict, HOST='127.0.0.1'), patch('dangerzone.public_snapshot.MigrationExecutor') as executor, patch('dangerzone.public_snapshot.call_command') as command, patch('dangerzone.public_snapshot.reset_local_snapshot_cache') as reset:
                executor.return_value.migration_plan.return_value = []
                with self.assertRaisesMessage(CommandError, 'Preflight failed; no data was cleared'):
                    initialize_local_data(root, 'admin-password', 'user-password', stdout=StringIO())
                command.assert_not_called()
                reset.assert_not_called()


class PublicSnapshotInitializationTests(SimpleTestCase):
    def test_initialization_rebuilds_the_strict_ng_rankings(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            make_snapshot(root)
            with (
                override_settings(PRODUCTION_MARK=root / '.production', DEBUG=True, E2E_TEST=True),
                patch.dict(connection.settings_dict, HOST='127.0.0.1'),
                patch('dangerzone.public_snapshot.MigrationExecutor') as executor,
                patch('dangerzone.public_snapshot.get_local_snapshot_cache'),
                patch('dangerzone.public_snapshot.reset_local_snapshot_cache'),
                patch('dangerzone.public_snapshot.import_snapshot_rows'),
                patch('dangerzone.public_snapshot.UserProfile') as profiles,
                patch('dangerzone.public_snapshot.add_videos_to_custom_pluck_ranks'),
                patch('dangerzone.public_snapshot.snapshot_pages', return_value=[]),
                patch('dangerzone.public_snapshot.call_command') as command,
            ):
                executor.return_value.migration_plan.return_value = []
                profiles.objects.select_related.return_value.iterator.return_value = []
                stdout = StringIO()
                initialize_local_data(root, 'admin-password', 'user-password', stdout=stdout, create_weekly=False)
                self.assertEqual([item.args[0] for item in command.call_args_list], [
                    'flush', 'refresh_video_counts', 'rebuild_speed_ranks', 'rebuild_strict_ng_ranks',
                    'rebuild_pb_ranks', 'rebuild_top_ranks', 'rebuild_eff_ranks', 'rebuild_eff_ranks',
                ])
