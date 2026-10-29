from contextlib import nullcontext
from datetime import timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.files.base import ContentFile
from django.core.management import call_command, CommandError
from django.db import connection
from django.db.migrations import DeleteModel
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings, TestCase, TransactionTestCase
from django.utils import timezone
import httpx
from saolei_api import Client, RateLimitError, ResponseError, VideoInfo, VideoListResponse

from config.text_choices import MS_TextChoices
from identifier.models import Identifier
from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from utils.parser import MSVideoParser
from videomanager.models import VideoModel
from .models import AccountLinkQueue, AccountSaolei, Platform, SaoleiApiVideo
from .saolei.services import import_saolei_video, save_catalogue_page, sync_saolei_catalogue, update_saolei_account_info

FIXTURE = Path(__file__).resolve().parents[1] / 'common/test_fixtures/video_upload_ranking/beginner_personal.evf'


def remote_video(remote_id=1, **changes):
    return {
        'id': remote_id, 'level': 'beg', 'userId': 101, 'userName': 'Remote', 'hash': 'ignored',
        'status': 20, 'uploadTime': 1681657187, 'reviewTime': 1681657187,
        'realTime': 1000, 'board3bv': 4, '3bvs': 4000, 'nf': False,
        'software': 'Arbiter', 'version': '0.52', **changes,
    }


def remote_page(items, cursor=0, following=None, more=False):
    return {
        'generatedAt': 1, 'items': items, 'cursor': cursor, 'size': 200,
        'nextCursor': following if following is not None else max([cursor, *[item['id'] + 1 for item in items]]),
        'hasMore': more,
    }


def bound_account(remote_id=101, username='saolei_import'):
    user = UserProfile.objects.create_user(username=username, email=f'{username}@example.com')
    account = AccountSaolei.objects.create(pk=remote_id, parent=user)
    AccountLinkQueue.objects.create(platform=Platform.SAOLEI, identifier=str(remote_id), userprofile=user, verified=True)
    return user, account


class SaoleiCatalogueTests(TestCase):
    def setUp(self):
        self.user, self.account = bound_account()

    def test_profile_updates_only_basic_fields_and_keeps_directory_progress(self):
        completed_at = timezone.now() - timedelta(days=1)
        self.account.video_update_time = completed_at
        self.account.video_sync_cursor = 91
        self.account.save(update_fields=['video_update_time', 'video_sync_cursor'])
        client = Mock()
        client.user_info.return_value.users = [SimpleNamespace(id=101, name='新名字', banned=True)]
        update_saolei_account_info(self.account, client)
        self.account.refresh_from_db()
        self.assertEqual((self.account.name, self.account.banned), ('新名字', True))
        self.assertEqual((self.account.video_update_time, self.account.video_sync_cursor), (completed_at, 91))

    def test_page_and_cursor_rollback_together_on_ownership_conflict(self):
        _, other = bound_account(102, 'other_source')
        SaoleiApiVideo.objects.create(remote_id=2, user=other, upload_time=timezone.now(), level='b', software='Clone', status=20)
        page = VideoListResponse.model_validate(remote_page([remote_video(1), remote_video(2)]))
        with self.assertRaises(ExceptionToResponse):
            save_catalogue_page(self.account, page, cursor=0, upper_bound=10)
        self.account.refresh_from_db()
        self.assertEqual(self.account.video_sync_cursor, 0)
        self.assertFalse(SaoleiApiVideo.objects.filter(remote_id=1).exists())

    def test_failed_page_resumes_from_committed_cursor_and_saves_unsupported_metadata(self):
        client = Mock()
        client.video_list.side_effect = [
            VideoListResponse.model_validate(remote_page([remote_video(1, software='Saolei.wang', status=0)], more=True)),
            ResponseError('offline failure'),
        ]
        with self.assertRaises(ResponseError):
            sync_saolei_catalogue(self.account, client, upper_bound=10)
        self.account.refresh_from_db()
        self.assertEqual(self.account.video_sync_cursor, 2)
        self.assertIsNone(self.account.video_update_time)
        self.assertEqual(SaoleiApiVideo.objects.get(remote_id=1).software, 'Saolei.wang')
        client.video_list.side_effect = None
        client.video_list.return_value = VideoListResponse.model_validate(remote_page([remote_video(3)], cursor=2))
        sync_saolei_catalogue(self.account, client, upper_bound=10)
        client.video_list.assert_called_with(player_id=101, cursor=2, size=200)
        self.account.refresh_from_db()
        self.assertEqual(self.account.video_sync_cursor, 4)
        self.assertIsNotNone(self.account.video_update_time)

    def test_snapshot_boundary_does_not_skip_unprocessed_tail(self):
        client = Mock()
        client.video_list.return_value = VideoListResponse.model_validate(remote_page([remote_video(1), remote_video(11)], following=12, more=True))
        sync_saolei_catalogue(self.account, client, upper_bound=10)
        self.account.refresh_from_db()
        self.assertEqual(self.account.video_sync_cursor, 11)
        self.assertFalse(SaoleiApiVideo.objects.filter(remote_id=11).exists())
        client.video_list.assert_called_once()

    def test_full_refresh_updates_metadata_without_regressing_saved_cursor(self):
        page = VideoListResponse.model_validate(remote_page([remote_video(1)]))
        save_catalogue_page(self.account, page, cursor=0, upper_bound=100)
        source = SaoleiApiVideo.objects.get(remote_id=1)
        source.file_url = '2023/04/16/sample.evf'
        source.save(update_fields=['file_url'])
        self.account.video_sync_cursor = 90
        self.account.save(update_fields=['video_sync_cursor'])
        client = Mock()
        client.video_list.return_value = VideoListResponse.model_validate(remote_page([remote_video(1, software='Vienna', status=99)]))
        sync_saolei_catalogue(self.account, client, upper_bound=100, full=True)
        self.account.refresh_from_db()
        self.assertEqual(self.account.video_sync_cursor, 90)
        source = SaoleiApiVideo.objects.get(remote_id=1)
        self.assertEqual((source.software, source.status), ('Vienna', 99))
        self.assertEqual(source.file_url, '2023/04/16/sample.evf')

    def test_wrong_remote_owner_and_nonadvancing_cursor_leave_no_progress(self):
        for page in [
            remote_page([remote_video(userId=102)]),
            remote_page([remote_video()], following=0, more=True),
        ]:
            with self.subTest(page=page), self.assertRaises(ResponseError):
                save_catalogue_page(self.account, VideoListResponse.model_validate(page), cursor=0, upper_bound=10)
        self.assertFalse(SaoleiApiVideo.objects.exists())


class SaoleiImportTests(TestCase):
    def setUp(self):
        self.user, self.account = bound_account()
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.content = FIXTURE.read_bytes()

    def source(self, remote_id=1, account=None, **changes):
        return SaoleiApiVideo.objects.create(remote_id=remote_id, user=account or self.account, upload_time=timezone.now() - timedelta(days=365), level='b', software=changes.pop('software', 'Arbiter'), status=changes.pop('status', 20), **changes)

    def remote_client(self, source, **changes):
        client = Mock()
        detail = {
            **remote_video(source.remote_id, userId=source.user_id, software=source.software, status=source.status, **changes),
            'signature': None, 'metrics': None, 'fileUrl': '2023/04/16/sample.evf',
        }
        client.video_info.return_value.items = [VideoInfo.model_validate(detail)]
        client.download_videos.return_value = [self.content]
        return client

    def test_all_statuses_import_with_identifier_validation_same_source_reuse_and_userms_persistence(self):
        parser = MSVideoParser(ContentFile(self.content, FIXTURE.name))
        Identifier.objects.create(identifier=parser.identifier, userms=None, safe=True)
        source = self.source()
        for status, software in zip((0, 10, 20, 99), ('Clone', 'Vienna', 'Arbiter', '元扫雷3.3.4'), strict=True):
            # 模拟同一来源在目录重建后重新关联已有本站录像。
            source.status, source.software, source.import_video = status, software, None
            source.save(update_fields=['status', 'software', 'import_video'])
            with self.subTest(status=status):
                self.assertEqual(import_saolei_video(source, self.remote_client(source, uploadTime=1681657187 - status)), 'imported')
                source.refresh_from_db()
                self.assertEqual(source.import_video.player_id, self.user.pk)
                self.assertEqual(source.import_video.state, MS_TextChoices.State.IDENTIFIER)
                self.assertEqual(int(source.import_video.upload_time.timestamp()), 1681657187 - status)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.userms_id)
        self.assertEqual(VideoModel.objects.count(), 1)
        with VideoModel.objects.get().file.open('rb') as recording:
            self.assertEqual(recording.read(), self.content)

    def test_whitelist_is_exact_and_latest_detail_is_checked_before_download(self):
        for number, software in enumerate(('Saolei.wang', 'Other', '', 'clone', '元扫雷3.3.5'), 1):
            source = self.source(number, software=software)
            client = Mock()
            self.assertEqual(import_saolei_video(source, client), 'skipped')
            client.video_info.assert_not_called()
            client.download_videos.assert_not_called()
        source = self.source(10)
        client = self.remote_client(source)
        client.video_info.return_value.items[0].software = 'Saolei.wang'
        self.assertEqual(import_saolei_video(source, client), 'skipped')
        client.download_videos.assert_not_called()
        self.assertFalse(VideoModel.objects.exists())

    def test_cross_owner_duplicate_never_changes_existing_video_or_links_source(self):
        _, other_account = bound_account(102, 'other_player')
        original_source = self.source(1, account=other_account)
        import_saolei_video(original_source, self.remote_client(original_source))
        existing = VideoModel.objects.get()
        previous_time, previous_owner = existing.upload_time, existing.player_id
        source = self.source(2)
        client = self.remote_client(source, uploadTime=1)
        with self.assertRaises(ExceptionToResponse) as caught:
            import_saolei_video(source, client)
        self.assertEqual(caught.exception.category, 'collision')
        existing.refresh_from_db()
        source.refresh_from_db()
        self.assertEqual((existing.upload_time, existing.player_id), (previous_time, previous_owner))
        self.assertIsNone(source.import_video_id)
        self.assertEqual(VideoModel.objects.count(), 1)

    def test_binding_changed_during_download_does_not_write_to_new_owner(self):
        source = self.source()
        client = self.remote_client(source)
        replacement = UserProfile.objects.create_user(username='replacement')

        def replace_binding(*args):
            AccountSaolei.objects.filter(pk=self.account.pk).update(parent=replacement)
            return [self.content]

        client.download_videos.side_effect = replace_binding
        with self.assertRaises(ExceptionToResponse) as caught:
            import_saolei_video(source, client)
        self.assertEqual(caught.exception.category, 'binding_changed')
        self.assertFalse(VideoModel.objects.exists())

    def test_missing_detail_or_file_keeps_source_retryable(self):
        source = self.source(file_url='2023/04/16/old.evf')
        for missing in ('detail', 'file'):
            client = self.remote_client(source)
            if missing == 'detail':
                client.video_info.return_value.items = []
            else:
                client.video_info.return_value.items[0].file_url = None
            with self.subTest(missing=missing), self.assertRaises(ExceptionToResponse):
                import_saolei_video(source, client)
            client.download_videos.assert_not_called()
            source.refresh_from_db()
            self.assertIsNone(source.import_video_id)
            self.assertEqual(source.file_url, '2023/04/16/old.evf' if missing == 'detail' else None)

    def test_command_resumes_directory_and_recovers_previously_committed_pending_file(self):
        requests = []
        fail_download = True

        def respond(request):
            requests.append(request)
            endpoint = request.url.path.rsplit('/', 1)[-1]
            if endpoint == 'stats':
                return httpx.Response(200, json={'generatedAt': 1, 'maxVideoId': 1, 'maxUserId': 101, 'stats': dict.fromkeys(['userTotal', 'rankedTotal', 'videoTotal', 'videoCommentTotal', 'bbsTopicTotal', 'bbsReplyTotal', 'practiceTotal'], 1)})
            if endpoint == 'user_info':
                score = {'time': 1, 'timeVideoId': 0, '3bvs': 1, '3bvsVideoId': 0}
                scores = {'beg': score, 'int': score, 'exp': score, 'sum': {'time': 3, '3bvs': 3}}
                return httpx.Response(200, json={'generatedAt': 1, 'users': [{'id': 101, 'name': 'API name', 'banned': False, 'englishName': '', 'sex': 0, 'area': '', 'registeredAt': 1, 'scores': scores, 'scoresNf': scores, 'signatures': []}]})
            if endpoint == 'video_list':
                self.assertEqual(request.url.params['player_id'], '101')
                cursor = int(request.url.params['cursor'])
                return httpx.Response(200, json=remote_page([remote_video()] if cursor == 0 else [], cursor=cursor))
            if endpoint == 'video_info':
                return httpx.Response(200, json={'generatedAt': 1, 'items': [{**remote_video(), 'signature': None, 'metrics': None, 'fileUrl': 'https://saolei.wang/videos/2023/04/16/sample.evf'}]})
            return httpx.Response(503 if fail_download else 200, content=self.content)

        def client_factory():
            return Client('sk-test-only', min_interval=0, download_interval=0, transport=httpx.MockTransport(respond))

        target = 'accountlink.management.commands.sync_saolei_api.saolei_client'
        with patch(target, side_effect=client_factory):
            with self.assertRaises(CommandError):
                call_command('sync_saolei_api', account_id=[101], stdout=StringIO(), stderr=StringIO())
            self.account.refresh_from_db()
            self.assertEqual(self.account.video_sync_cursor, 2)
            self.assertFalse(VideoModel.objects.exists())
            self.assertEqual(SaoleiApiVideo.objects.get(remote_id=1).file_url, '2023/04/16/sample.evf')
            fail_download = False
            requests.clear()
            call_command('sync_saolei_api', account_id=[101], stdout=StringIO(), stderr=StringIO())
        self.assertTrue(SaoleiApiVideo.objects.get(remote_id=1).import_video_id)
        self.assertEqual(VideoModel.objects.count(), 1)
        self.assertIn('https://saolei.wang/videos/2023/04/16/sample.evf', [str(request.url) for request in requests])
        # 游标已越过本轮上界，无需再请求目录，仍补导了本地未完成录像。
        self.assertNotIn('video_list', [request.url.path.rsplit('/', 1)[-1] for request in requests])

    def test_profile_failure_does_not_abort_catalogue_or_file_import(self):
        source = self.source()
        client = self.remote_client(source)
        client.stats.return_value.max_video_id = 1
        client.user_info.side_effect = ResponseError('Unavailable profile')
        client.video_list.return_value = VideoListResponse.model_validate(remote_page([remote_video()]))
        with patch('accountlink.management.commands.sync_saolei_api.saolei_client', return_value=nullcontext(client)):
            with self.assertRaises(CommandError):
                call_command('sync_saolei_api', account_id=[101], stdout=StringIO(), stderr=StringIO())
        source.refresh_from_db()
        self.assertIsNotNone(source.import_video_id)
        self.assertTrue(AccountLinkQueue.objects.filter(userprofile=self.user, verified=True).exists())

    def test_rate_limit_stops_without_retry_or_advancing_directory(self):
        source = self.source()
        client = self.remote_client(source)
        client.stats.return_value.max_video_id = 1
        client.user_info.side_effect = RateLimitError('user_info', 5)
        with patch('accountlink.management.commands.sync_saolei_api.saolei_client', return_value=nullcontext(client)):
            with self.assertRaisesMessage(CommandError, 'Retry-After=5'):
                call_command('sync_saolei_api', account_id=[101], stdout=StringIO(), stderr=StringIO())
        client.user_info.assert_called_once()
        client.video_list.assert_not_called()
        client.download_videos.assert_not_called()
        self.account.refresh_from_db()
        self.assertEqual(self.account.video_sync_cursor, 0)


class SaoleiSourceMigrationTests(TransactionTestCase):
    def test_replacing_old_table_preserves_account_native_video_expansion_and_file(self):
        executor = MigrationExecutor(connection)
        replacement = next((migration for (app, _), migration in executor.loader.disk_migrations.items() if app == 'accountlink' and any(isinstance(operation, DeleteModel) and operation.name == 'VideoSaolei' for operation in migration.operations)), None)
        if replacement is None:
            self.skipTest('Fresh installations have no legacy source table to replace')
        before = [dependency for dependency in replacement.dependencies if dependency[0] == 'accountlink']
        after = [node for node in executor.loader.graph.leaf_nodes() if node[0] == 'accountlink']
        executor.migrate(before)
        try:
            old_apps = executor.loader.project_state(before).apps
            user = UserProfile.objects.create_user(username='migration_player')
            parser = MSVideoParser(ContentFile(FIXTURE.read_bytes(), FIXTURE.name))
            with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
                video = VideoModel.create_from_parser(parser, user, original_hash='a' * 24)
                old_account = old_apps.get_model('accountlink', 'AccountSaolei').objects.create(pk=101, parent_id=user.pk, name='Saved')
                old_apps.get_model('accountlink', 'VideoSaolei').objects.create(pk=video.pk, user_id=old_account.pk, upload_time=timezone.now(), level='b', state='o', import_video_id=video.pk)
                executor = MigrationExecutor(connection)
                executor.migrate(after)
                self.assertTrue(VideoModel.objects.filter(pk=video.pk, video_id=video.video_id).exists())
                self.assertTrue(Path(video.file.path).exists())
                self.assertEqual(AccountSaolei.objects.get(pk=101).parent_id, user.pk)
                self.assertEqual(AccountSaolei.objects.get(pk=101).video_sync_cursor, 0)
                self.assertFalse(SaoleiApiVideo.objects.exists())
                self.assertNotIn('accountlink_videosaolei', connection.introspection.table_names())
        finally:
            MigrationExecutor(connection).migrate(after)
