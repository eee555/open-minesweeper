from dataclasses import replace
from datetime import date, datetime, timezone as datetime_timezone
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.test import override_settings, SimpleTestCase, TestCase
import httpx
from msgames_api import AccessDeniedError, Client as MSGamesClient, ParseError, RecordMetric, RequestError
from msgames_api.parsers import parse_profile, parse_records

from accountlink.models import AccountLinkQueue, AccountMinesweeperGames, Platform, VideoMSGames
from accountlink.msgames.client import download_replay, fetch_profile, fetch_replays
from accountlink.msgames.utils import normalize_profile, normalize_replays, supports_replay, upload_date_upper_bound
from accountlink.services import msgames_video_import_one, update_msgames_account, update_msgames_video_list
from config.text_choices import MS_TextChoices
from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from videomanager.models import ExpandVideoModel, VideoModel


def fixture(name):
    return Path(__file__).with_name(name).read_text(encoding='utf-8')


def profile():
    return parse_profile(fixture('profile.html'), 42)


def records(metric=RecordMetric.TIME):
    return parse_records(fixture('records.html'), 42, metric)


def density_records():
    return parse_records(fixture('density.html'), 42, RecordMetric.DENSITY)


class MSGamesMappingTests(SimpleTestCase):
    def test_density_unknown_groups_and_conflicting_metadata_cannot_be_imported(self):
        value = density_records()[0]
        cases = [
            [replace(value, groups=())], [replace(value, groups=('unknown',))],
            [replace(value, groups=('8x8', '9x9'))],
            [value, replace(value, mines=41)],
            [replace(value, metric=RecordMetric.TIME), replace(value, mines=41)],
        ]
        for case in cases:
            with self.subTest(case=case):
                info = normalize_replays(case, 42)[0]
                self.assertFalse(supports_replay(info['filename'], info['category'], info['density_levels']))

    def test_private_local_name_retains_legacy_string(self):
        result = normalize_profile(replace(profile(), name='Private', local_name=None), 42)
        self.assertEqual(result['local_name'], 'None')

    def test_invalid_joined_and_player_id_are_rejected(self):
        for value, player_id in ((replace(profile(), joined=None), 42), (profile(), 99)):
            with self.subTest(player_id=player_id), self.assertRaises(ValueError):
                normalize_profile(value, player_id)

    def test_empty_name_is_rejected_before_binding(self):
        for name in ('', '  '):
            with self.subTest(name=name), self.assertRaises(ValueError):
                normalize_profile(replace(profile(), name=name), 42)

    def test_replays_merge_all_metrics_and_nf_groups_by_original_url(self):
        result = normalize_replays([*records(), *records(RecordMetric.THREE_BVS)], 42)
        self.assertEqual(len(result), 2)
        avf = next(value for value in result if value['filename'] == 'example.avf')
        self.assertEqual(avf['upload_date'], date(2020, 2, 29))
        self.assertIn('beginner_nf', avf['category'])
        self.assertIn('3BVS', avf['category'])
        self.assertIn('Time: 0.490', avf['score'])
        self.assertIn('3BVS: 6.122', avf['score'])
        self.assertIsInstance(avf['score'], str)

    def test_rows_without_replays_are_not_stored(self):
        self.assertEqual(normalize_replays([replace(records()[0], replay=None)], 42), [])

    def test_wrong_owner_invalid_date_and_host_are_rejected(self):
        value = records()[0]
        cases = [
            replace(value, player_id=99), replace(value, date=None),
            replace(value, replay=replace(value.replay, player_id=99)),
            replace(value, replay=replace(value.replay, url='https://example.org/replay.avf')),
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                normalize_replays([case], 42)

    def test_upload_date_uses_following_midnight_utc_including_leap_day(self):
        self.assertEqual(upload_date_upper_bound(date(2020, 2, 29)), datetime(2020, 3, 1, tzinfo=datetime_timezone.utc))
        self.assertEqual(upload_date_upper_bound(date(2020, 12, 31)), datetime(2021, 1, 1, tzinfo=datetime_timezone.utc))
        with self.assertRaises(ValueError):
            upload_date_upper_bound(date.max)

    @patch('accountlink.msgames.client.Client')
    def test_client_reads_all_five_categories_with_empty_problems(self, factory):
        requested = []

        def respond(request):
            self.assertEqual(request.url.path, '/profile.php')
            self.assertEqual(request.url.params['pid'], '42')
            metric = RecordMetric(int(request.url.params['menu']))
            requested.append(metric)
            return httpx.Response(200, text=fixture('empty_records.html' if metric == RecordMetric.PROBLEMS else 'records.html'))

        with httpx.Client(transport=httpx.MockTransport(respond)) as http_client:
            factory.return_value = MSGamesClient(http_client=http_client, min_interval=0)
            self.assertEqual(len(fetch_replays(42)), 2)
        self.assertEqual(requested, list(RecordMetric))

    @patch('accountlink.msgames.client.Client')
    def test_client_error_mapping_and_release(self, factory):
        timeout = RequestError('timeout')
        timeout.__cause__ = httpx.ReadTimeout('timeout')
        cases = [(timeout, 'timeout'), (RequestError('connection'), 'requestexception'), (ParseError('layout'), 'indexerror'), (AccessDeniedError('denied'), 'requestexception')]
        for error, category in cases:
            with self.subTest(category=category):
                factory.reset_mock()
                factory.return_value.__enter__.return_value.get_profile.side_effect = error
                with self.assertRaises(ExceptionToResponse) as caught:
                    fetch_profile(42)
                self.assertEqual(caught.exception.category, category)
                self.assertEqual(caught.exception.status_code, 503)
                factory.return_value.__exit__.assert_called_once()

    @patch('accountlink.msgames.client.Client')
    def test_download_uses_package_method_and_site_file_limit(self, factory):
        factory.return_value.__enter__.return_value.download_replay.return_value = b'replay'
        self.assertEqual(download_replay('https://minesweepergame.com/member/file/42/example.avf'), b'replay')
        self.assertEqual(factory.call_args.kwargs['max_replay_bytes'], 5 * 1024 * 1024)


@override_settings(RATELIMIT_ENABLE=False, STORAGES={'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'}})
class MSGamesAccountTests(TestCase):
    def setUp(self):
        self.owner = UserProfile.objects.create(username='msgames-owner', email='msgames-owner@example.com')
        self.other = UserProfile.objects.create(username='msgames-other', email='msgames-other@example.com')
        self.account = AccountMinesweeperGames.objects.create(id=42, parent=self.owner, name='Previous name')
        self.link = AccountLinkQueue.objects.create(platform=Platform.MSGAMES, identifier='42', userprofile=self.owner, verified=True)
        self.info = normalize_replays(list(records()), 42)[0]
        self.source = VideoMSGames.objects.create(user=self.account, **self.info)
        self.client.force_login(self.owner)

    def stored_video(self, data=b'replay', upload_time=None):
        video = VideoModel.objects.create(
            player=self.owner, video=ExpandVideoModel.objects.create(), file=ContentFile(data, 'test.avf'),
            file_size=len(data), original_hash=hashlib.sha256(data).hexdigest()[:24], level=MS_TextChoices.Level.BEGINNER, software=MS_TextChoices.Software.AVF,
            state=MS_TextChoices.State.OFFICIAL, timems=490, bv=3,
        )
        if upload_time:
            VideoModel.objects.filter(pk=video.pk).update(upload_time=upload_time)
            video.refresh_from_db()
        return video

    @patch('accountlink.services.download_msgames_replay', return_value=b'replay')
    @patch('accountlink.services.MSVideoParser')
    @patch('accountlink.services.VideoModel.create_from_parser')
    def test_api_imports_only_supported_density_configurations_and_formats(self, create, parse, download):
        create.return_value = self.stored_video(data=b'different bytes')
        parse.return_value = SimpleNamespace(identifier='', state=MS_TextChoices.State.PLAIN)
        density = density_records()
        mvr = replace(density[0], replay=replace(density[0].replay, filename='density.mvr', url='https://minesweepergame.com/member/file/42/density.mvr'))
        sources = [VideoMSGames.objects.create(user=self.account, **info) for info in normalize_replays([*density, mvr], 42)]
        expected = {'density-40.avf', 'density-100.avf', 'density-150.avf', 'density-200.avf'}
        for source in sources:
            with self.subTest(filename=source.filename):
                supported = source.filename in expected
                response = self.client.post(f'/api/accountlink/msgames/videos/{source.id}/import')
                self.assertEqual(response.status_code, 200 if supported else 400, response.content)
                source.refresh_from_db()
                self.assertEqual(source.import_video_id is not None, supported)
        self.assertEqual(download.call_count, 4)

    @patch('accountlink.services.fetch_msgames_replays')
    def test_density_without_configuration_requires_sync_before_import(self, fetch):
        info = normalize_replays(density_records(), 42)[0]
        source = VideoMSGames.objects.create(user=self.account, **{**info, 'density_levels': []})
        self.assertFalse(source.can_import)
        with self.assertRaises(ExceptionToResponse):
            msgames_video_import_one(source)
        fetch.return_value = [info]
        update_msgames_video_list(self.account)
        source.refresh_from_db()
        self.assertTrue(source.can_import)

    @patch('accountlink.services.fetch_msgames_profile')
    def test_profile_refresh_saves_text_and_update_time(self, fetch):
        old_time = self.account.update_time
        fetch.return_value = normalize_profile(profile(), 42)
        update_msgames_account(self.account)
        self.account.refresh_from_db()
        self.assertEqual(
            (self.account.name, self.account.local_name, self.account.joined, self.account.country, self.account.state, self.account.hand, self.account.mouse),
            ('Test Player', '测试玩家', date(2020, 2, 29), 'Country outside any enum', '自定义地区', 'Both (custom)', '鼠标原文 / model 123'),
        )
        self.assertGreater(self.account.update_time, old_time)

    @patch('accountlink.services.fetch_msgames_profile', side_effect=ExceptionToResponse('import', 'timeout'))
    def test_failed_profile_keeps_existing_values(self, fetch):
        old_time = self.account.update_time
        with self.assertRaises(ExceptionToResponse):
            update_msgames_account(self.account)
        self.account.refresh_from_db()
        self.assertEqual(self.account.name, 'Previous name')
        self.assertEqual(self.account.update_time, old_time)

    @patch('accountlink.services.fetch_msgames_replays')
    def test_sync_updates_strings_without_losing_imported_video(self, fetch):
        video = self.stored_video()
        self.source.import_video = video
        self.source.save(update_fields=['import_video'])
        fetch.return_value = normalize_replays([*records(), *records(RecordMetric.THREE_BVS)], 42)
        self.assertEqual(len(update_msgames_video_list(self.account)), 1)
        self.source.refresh_from_db()
        self.assertEqual(self.source.import_video_id, video.id)
        self.assertIn('3BVS', self.source.category)
        self.assertEqual(self.account.videos.count(), 2)
        self.account.refresh_from_db()
        self.assertIsNotNone(self.account.video_update_time)

    @patch('accountlink.services.fetch_msgames_replays')
    def test_sync_rejects_source_key_owned_by_another_account(self, fetch):
        other_account = AccountMinesweeperGames.objects.create(id=43, parent=self.other)
        fetch.return_value = [self.info]
        with self.assertRaises(IntegrityError):
            update_msgames_video_list(other_account)
        self.source.refresh_from_db()
        self.assertEqual(self.source.user_id, self.account.id)
        self.assertFalse(other_account.videos.exists())
        other_account.refresh_from_db()
        self.assertIsNone(other_account.video_update_time)

    def test_verified_catalogue_is_public_and_complete(self):
        VideoMSGames.objects.bulk_create([
            VideoMSGames(user=self.account, **{**self.info, 'source_key': str(index).zfill(64)})
            for index in range(50)
        ])
        self.client.logout()
        response = self.client.get('/api/accountlink/msgames/videos', {'msgames_id': 42})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsInstance(response.json(), list)
        self.assertEqual(len(response.json()), 51)
        value = response.json()[0]
        self.assertEqual(value['upload_date'], '2020-02-29')
        self.assertIsInstance(value['score'], str)
        self.assertNotIn('can_import', value)
        self.assertNotIn('source_key', value)

    def test_unverified_catalogue_is_hidden_from_other_users(self):
        self.link.verified = False
        self.link.save(update_fields=['verified'])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get('/api/accountlink/msgames/videos', {'msgames_id': 42}).status_code, 404)

    def test_import_requires_verified_owner(self):
        path = f'/api/accountlink/msgames/videos/{self.source.id}/import'
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(path).status_code, 403)
        self.client.force_login(self.owner)
        self.link.verified = False
        self.link.save(update_fields=['verified'])
        self.assertEqual(self.client.post(path).status_code, 403)

    @patch('accountlink.services.fetch_msgames_replays')
    def test_sync_is_owner_only_and_does_not_import(self, fetch):
        fetch.return_value = normalize_replays(list(records()), 42)
        path = '/api/accountlink/msgames/42/sync'
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(path).status_code, 403)
        fetch.assert_not_called()
        self.client.force_login(self.owner)
        response = self.client.post(path)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['status'], 'SYNCED')
        self.assertEqual(response.json()['count'], 2)
        self.assertIsNotNone(response.json()['video_update_time'])
        self.assertFalse(self.account.videos.filter(import_video__isnull=False).exists())

    @patch('accountlink.services.download_msgames_replay', return_value=b'replay')
    @patch('accountlink.services.MSVideoParser')
    def test_api_finishes_import_and_repeated_import_is_idempotent(self, parse, download):
        video = self.stored_video()
        path = f'/api/accountlink/msgames/videos/{self.source.id}/import'
        response = self.client.post(path)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {'status': 'IMPORTED', 'import_video_id': video.id, 'video_state': video.state})
        self.source.refresh_from_db()
        self.assertEqual(self.source.import_video_id, video.id)
        response = self.client.post(path)
        self.assertEqual(response.json()['status'], 'ALREADY_IMPORTED')
        self.assertEqual(download.call_count, 1)
        summary = self.client.get('/api/accountlink/msgames/summary', {'msgames_id': 42}).json()
        self.assertEqual(summary, {'total': 1, 'imported': 1, 'video_update_time': None})
        parse.assert_not_called()

    @patch('accountlink.services.fetch_msgames_replays', side_effect=ExceptionToResponse('import', 'timeout'))
    def test_api_sync_error_returns_failure_without_changing_catalogue(self, fetch):
        response = self.client.post('/api/accountlink/msgames/42/sync')
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {'type': 'error', 'object': 'import', 'category': 'timeout'})
        self.assertEqual(self.account.videos.count(), 1)
        self.account.refresh_from_db()
        self.assertIsNone(self.account.video_update_time)

    @patch('accountlink.services.download_msgames_replay')
    @patch('accountlink.services.MSVideoParser')
    def test_api_import_failures_are_returned_and_can_be_retried(self, parse, download):
        path = f'/api/accountlink/msgames/videos/{self.source.id}/import'
        download.side_effect = ExceptionToResponse('import', 'timeout')
        response = self.client.post(path)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['category'], 'timeout')
        download.side_effect = None
        download.return_value = b'replay'
        parse.side_effect = ExceptionToResponse('file', 'incomplete')
        response = self.client.post(path)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['category'], 'incomplete')
        self.source.refresh_from_db()
        self.assertIsNone(self.source.import_video_id)
        video = self.stored_video()
        parse.side_effect = None
        response = self.client.post(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['import_video_id'], video.id)

    @patch('accountlink.services.download_msgames_replay', return_value=b'replay')
    @patch('accountlink.services.MSVideoParser')
    @patch('accountlink.services.Identifier.verify', return_value=False)
    @patch('accountlink.services.VideoModel.create_from_parser')
    def test_import_backfills_next_midnight_and_preserves_identifier_review(self, create, verify, parse, download):
        result = self.stored_video(data=b'new fixture not matching the downloaded replay')
        create.return_value = result
        parse.return_value = SimpleNamespace(identifier='unverified identifier', state=MS_TextChoices.State.OFFICIAL)
        msgames_video_import_one(self.source)
        self.source.refresh_from_db()
        result.refresh_from_db()
        self.assertEqual(result.upload_time, datetime(2020, 3, 1, tzinfo=datetime_timezone.utc))
        self.assertEqual(self.source.import_video_id, result.id)
        self.assertEqual(parse.return_value.state, MS_TextChoices.State.IDENTIFIER)
        self.owner.refresh_from_db()
        self.assertIsNotNone(self.owner.userms_id)
        self.assertEqual(create.call_args.kwargs['original_hash'], hashlib.sha256(b'replay').hexdigest()[:24])

    @patch('accountlink.services.download_msgames_replay', return_value=b'replay')
    @patch('accountlink.services.MSVideoParser')
    def test_hash_dedup_keeps_earlier_upload_time_without_parsing(self, parse, download):
        earlier = datetime(2019, 1, 1, tzinfo=datetime_timezone.utc)
        video = self.stored_video(upload_time=earlier)
        with patch('accountlink.services.VideoModel.create_from_parser') as create:
            self.assertEqual(msgames_video_import_one(self.source), video)
        create.assert_not_called()
        parse.assert_not_called()
        video.refresh_from_db()
        self.assertEqual(video.upload_time, earlier)

    @patch('accountlink.services.download_msgames_replay', return_value=b'replay')
    @patch('accountlink.services.MSVideoParser')
    def test_hash_dedup_backfills_later_existing_timestamp_without_parsing(self, parse, download):
        video = self.stored_video(upload_time=datetime(2021, 1, 1, tzinfo=datetime_timezone.utc))
        self.assertEqual(msgames_video_import_one(self.source), video)
        video.refresh_from_db()
        self.assertEqual(video.upload_time, datetime(2020, 3, 1, tzinfo=datetime_timezone.utc))
        parse.assert_not_called()

    @patch('accountlink.services.download_msgames_replay', return_value=b'replay')
    @patch('accountlink.services.MSVideoParser')
    @patch('accountlink.services.VideoModel.create_from_parser')
    def test_today_upload_is_backfilled_to_tomorrow_not_clamped_to_now(self, create, parse, download):
        self.source.upload_date = datetime.now(tz=datetime_timezone.utc).date()
        self.source.save(update_fields=['upload_date'])
        result = self.stored_video(data=b'different bytes to exercise creation')
        create.return_value = result
        parse.return_value = SimpleNamespace(identifier='', state=MS_TextChoices.State.PLAIN)
        msgames_video_import_one(self.source)
        result.refresh_from_db()
        self.assertEqual(result.upload_time, upload_date_upper_bound(self.source.upload_date))

    def test_unlink_deletes_source_rows_but_keeps_imported_files(self):
        video = self.stored_video()
        self.source.import_video = video
        self.source.save(update_fields=['import_video'])
        self.account.delete()
        self.assertFalse(VideoMSGames.objects.exists())
        self.assertTrue(VideoModel.objects.filter(pk=video.pk).exists())
