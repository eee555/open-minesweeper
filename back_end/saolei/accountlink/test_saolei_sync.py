from contextlib import nullcontext
from datetime import datetime, timedelta, timezone as datetime_timezone
from pathlib import Path
from subprocess import run
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from apscheduler.schedulers.background import BackgroundScheduler
from django.core.management import call_command, CommandError
from django.tasks import TaskResultStatus
from django.test import override_settings, TestCase
from django.utils import timezone
from django_tasks_db.models import DBTaskResult
import httpx
from saolei_api import RateLimitError, ResponseError, TransportError, VideoInfo, VideoListResponse

from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from utils.test_parser import abort_parser_process
from videomanager.models import VideoModel
from .models import AccountLinkQueue, AccountSaolei, SaoleiApiVideo
from .saolei.client import ThrottledTransport
from .saolei.services import save_video_details, sync_saolei_metadata_daily
from .saolei.tasks import enqueue_saolei_hourly_import, task_import_saolei_hourly
from .test_saolei_api import bound_account, FIXTURE, remote_page, remote_video

BASE = '/api/accountlink/saolei'


@override_settings(RATELIMIT_ENABLE=False, BAIDU_VERIFY_SKIP=True)
class SaoleiSyncTests(TestCase):
    def setUp(self):
        self.user, self.account = bound_account()
        self.other = UserProfile.objects.create_user(username='other_saolei')
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        media = override_settings(MEDIA_ROOT=self.media.name)
        media.enable()
        self.addCleanup(media.disable)
        self.remote = Mock()
        self.remote.stats.return_value.max_video_id = 2
        self.remote.user_info.side_effect = lambda account_id: SimpleNamespace(users=[SimpleNamespace(id=account_id, name='API name', banned=False)])
        self.remote.video_list.return_value = VideoListResponse.model_validate(remote_page([remote_video(1)], more=True))
        self.remote.video_info.return_value.items = [VideoInfo.model_validate({**remote_video(), 'fileUrl': '2023/04/16/sample.evf', 'signature': None, 'metrics': None})]
        self.remote.download_videos.return_value = [FIXTURE.read_bytes()]

    def post(self, path, data=None):
        return self.client.post(BASE + path, data or {}, content_type='application/json')

    def test_only_verified_owner_can_write_and_all_writes_check_before_network(self):
        source = SaoleiApiVideo.objects.create(user=self.account, remote_id=1, upload_time=timezone.now(), level='b', status=20, software='Arbiter')
        operations = [
            ('/101/settings', {'auto_sync': False}), ('/101/profile', {}), ('/101/sync/start', {}),
            ('/101/sync/page', {'cursor': 0, 'upper_bound': 2}), (f'/videos/{source.pk}/import', {}),
        ]
        with patch('accountlink.saolei.api.saolei_client') as factory:
            for user in [None, self.other]:
                if user:
                    self.client.force_login(user)
                for path, data in operations:
                    self.assertEqual(self.post(path, data).status_code, 403)
            self.client.force_login(self.user)
            AccountLinkQueue.objects.filter(userprofile=self.user).update(verified=False)
            for path, data in operations:
                self.assertEqual(self.post(path, data).status_code, 409)
            factory.assert_not_called()
        self.account.refresh_from_db()
        self.assertTrue(self.account.auto_sync)

    def test_default_auto_sync_can_be_disabled_without_disabling_manual_pages(self):
        self.assertTrue(self.account.auto_sync)
        self.client.force_login(self.user)
        self.assertEqual(self.post('/101/settings', {'auto_sync': False}).json()['auto_sync'], False)
        with patch('accountlink.saolei.api.saolei_client', return_value=nullcontext(self.remote)):
            self.assertEqual(self.post('/101/sync/start').json(), {'cursor': 0, 'upper_bound': 2})
            self.assertEqual(self.post('/101/sync/page', {'cursor': 0, 'upper_bound': 2}).json(), {'cursor': 1, 'has_more': True})
            self.remote.video_list.assert_called_once_with(player_id=101, cursor=0, size=200)
            self.remote.download_videos.assert_not_called()
            self.account.refresh_from_db()
            self.assertEqual(self.account.video_sync_cursor, 1)
            self.assertIsNone(self.account.video_update_time)
            self.remote.video_list.return_value = VideoListResponse.model_validate(remote_page([remote_video(2, software='Saolei.wang')], cursor=1))
            self.assertEqual(self.post('/101/sync/page', {'cursor': 1, 'upper_bound': 2}).json(), {'cursor': 2, 'has_more': False})
        self.account.refresh_from_db()
        self.assertFalse(self.account.auto_sync)
        self.assertIsNotNone(self.account.video_update_time)
        self.assertEqual(self.client.get(f'{BASE}/101/summary').json()['pending'], 1)

    def test_single_import_and_rejection_survive_later_syncs(self):
        self.client.force_login(self.user)
        source = SaoleiApiVideo.objects.create(user=self.account, remote_id=1, upload_time=timezone.now(), level='b', status=0, software='Arbiter')
        with patch('accountlink.saolei.api.saolei_client', return_value=nullcontext(self.remote)):
            with patch('accountlink.saolei.services.MSVideoParser', side_effect=ExceptionToResponse('file', 'review')):
                response = self.post(f'/videos/{source.pk}/import')
            self.assertEqual(response.status_code, 400, response.content)
            source.refresh_from_db()
            self.assertTrue(source.import_rejected)
            self.remote.reset_mock()
            self.assertEqual(self.post(f'/videos/{source.pk}/import').json()['status'], 'skipped')
            self.remote.video_info.assert_not_called()
            self.remote.download_videos.assert_not_called()
            SaoleiApiVideo.objects.filter(pk=source.pk).update(import_rejected=False)
            response = self.post(f'/videos/{source.pk}/import')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['status'], 'imported')
        self.assertEqual(VideoModel.objects.count(), 1)
        self.assertTrue(Path(VideoModel.objects.get().file.path).is_file())

    def test_upstream_failure_keeps_progress_and_returns_non_success_status(self):
        self.client.force_login(self.user)
        with patch('accountlink.saolei.api.saolei_client', return_value=nullcontext(self.remote)):
            for error, status in [(ResponseError('bad response'), 502), (RateLimitError('stats', 5), 429)]:
                self.remote.stats.side_effect = error
                self.assertEqual(self.post('/101/sync/start').status_code, status)
        self.account.refresh_from_db()
        self.assertEqual(self.account.video_sync_cursor, 0)
        self.assertTrue(AccountLinkQueue.objects.get(userprofile=self.user).verified)

    def test_local_pagination_and_pending_selection_use_source_ids(self):
        SaoleiApiVideo.objects.bulk_create([
            SaoleiApiVideo(user=self.account, remote_id=index, upload_time=timezone.now(), level='b', status=20,
                           software='Saolei.wang' if index == 201 else 'Arbiter', import_rejected=index == 200)
            for index in range(1, 202)
        ])
        with patch('accountlink.saolei.api.saolei_client') as remote:
            first = self.client.get(f'{BASE}/101/videos').json()
            self.assertEqual(len(first['items']), 200)
            tail = self.client.get(f'{BASE}/101/videos', {'after': first['next_after']}).json()
            self.assertEqual(len(tail['items']), 1)
            self.assertIsNone(tail['next_after'])
            pending = self.client.get(f'{BASE}/101/videos', {'pending': 'true'}).json()
            self.assertEqual(len(pending['items']), 199)
            self.assertTrue(all(not item['import_rejected'] for item in pending['items']))
            remote.assert_not_called()

    @patch('accountlink.saolei.services.close_old_connections')
    def test_daily_metadata_uses_incremental_cursor_and_skips_opt_out_and_revoked_binding(self, close):
        _, opted_out = bound_account(102, 'opted_out')
        opted_out.auto_sync = False
        opted_out.save(update_fields=['auto_sync'])
        revoked_user, _ = bound_account(103, 'revoked')
        AccountLinkQueue.objects.filter(userprofile=revoked_user).update(verified=False)
        self.account.video_sync_cursor = 1
        self.account.save(update_fields=['video_sync_cursor'])
        self.remote.video_list.return_value = VideoListResponse.model_validate(remote_page([remote_video(2)], cursor=1))
        self.remote.video_info.return_value.items[0].id = 2
        with patch('accountlink.saolei.services.saolei_client', return_value=nullcontext(self.remote)):
            with self.assertRaises(ExceptionToResponse):  # The revoked binding is reported without blocking other accounts.
                sync_saolei_metadata_daily()
        self.remote.video_list.assert_called_once_with(player_id=101, cursor=1, size=200)
        self.remote.user_info.assert_called_once_with(101)
        self.remote.video_info.assert_called_once_with([2])
        self.remote.download_videos.assert_not_called()
        source = SaoleiApiVideo.objects.get(remote_id=2)
        self.assertIsNone(source.import_video_id)
        self.assertEqual(source.file_url, '2023/04/16/sample.evf')
        self.assertFalse(DBTaskResult.objects.filter(task_path__startswith='accountlink.saolei').exists())

    def test_disabled_accounts_do_not_create_an_upstream_client(self):
        AccountSaolei.objects.update(auto_sync=False)
        with patch('accountlink.saolei.services.saolei_client') as remote:
            self.assertEqual(sync_saolei_metadata_daily(), {})
            remote.assert_not_called()

    @patch('accountlink.saolei.services.close_old_connections')
    def test_opt_out_after_daily_work_starts_is_checked_before_account_sync(self, close):
        def opt_out():
            AccountSaolei.objects.filter(pk=self.account.pk).update(auto_sync=False)
            return SimpleNamespace(max_video_id=2)

        self.remote.stats.side_effect = opt_out
        with patch('accountlink.saolei.services.saolei_client', return_value=nullcontext(self.remote)):
            self.assertEqual(sync_saolei_metadata_daily(), {})
        self.remote.user_info.assert_not_called()
        self.remote.video_list.assert_not_called()

    def test_hourly_enqueue_does_not_duplicate_ready_or_running_work(self):
        with patch.object(type(task_import_saolei_hourly), 'enqueue') as enqueue:
            for status in [TaskResultStatus.READY, TaskResultStatus.RUNNING]:
                row = DBTaskResult.objects.create(
                    task_path=task_import_saolei_hourly.module_path, status=status,
                    args_kwargs={'args': [], 'kwargs': {}}, queue_name='default', backend_name='default',
                )
                enqueue_saolei_hourly_import()
                enqueue.assert_not_called()
                row.delete()
            enqueue_saolei_hourly_import()
            enqueue.assert_called_once_with()

    def test_scheduler_runs_metadata_directly_daily_and_enqueues_import_hourly(self):
        from common.apscheduler import queue_saolei_hourly_import, register_jobs, sync_saolei_daily_catalogue

        scheduler = BackgroundScheduler(timezone=datetime_timezone.utc)
        register_jobs(scheduler)
        job = scheduler.get_job('sync_saolei_metadata_daily')
        now = datetime(2026, 11, 1, 3, 30, tzinfo=datetime_timezone.utc)
        self.assertEqual(job.func, sync_saolei_daily_catalogue)
        self.assertEqual(job.trigger.get_next_fire_time(None, now), now)
        self.assertEqual(job.trigger.get_next_fire_time(now, now), now + timedelta(days=1))
        hourly = scheduler.get_job('import_saolei_hourly')
        self.assertEqual(hourly.func, queue_saolei_hourly_import)
        first = now.replace(minute=0) + timedelta(hours=1)
        self.assertEqual(hourly.trigger.get_next_fire_time(None, now), first)
        self.assertEqual(hourly.trigger.get_next_fire_time(first, first), first + timedelta(hours=1))


class SharedQuotaTests(TestCase):
    def test_separate_clients_share_the_same_quota_and_downloads_have_their_own_gate(self):
        redis = Mock()
        redis.set.side_effect = [True, False, True, True]
        requests = []
        transport = httpx.MockTransport(lambda request: requests.append(request) or httpx.Response(200))
        with patch('accountlink.saolei.client.get_redis_connection', return_value=redis), patch('accountlink.saolei.client.time.sleep') as sleep:
            for path in ['/api/public/v1/stats', '/api/public/v1/video_list', '/videos/2023/04/16/sample.evf']:
                ThrottledTransport(transport).handle_request(httpx.Request('GET', 'https://saolei.wang' + path))
        self.assertEqual(len(requests), 3)
        sleep.assert_called_once_with(0.1)
        self.assertEqual([call.args[0] for call in redis.set.call_args_list], ['saolei:throttle:data'] * 3 + ['saolei:throttle:download'])


@override_settings(BAIDU_VERIFY_SKIP=True)
class SaoleiStageTests(TestCase):
    def setUp(self):
        self.user, self.account = bound_account()
        self.remote = Mock()
        self.remote.stats.return_value.max_video_id = 101
        self.remote.user_info.return_value.users = [SimpleNamespace(id=101, name='API name', banned=False)]
        self.remote.video_info.side_effect = lambda ids: SimpleNamespace(items=[self.detail(remote_id) for remote_id in reversed(ids)])
        self.remote.download_videos.return_value = [FIXTURE.read_bytes()]

    def detail(self, remote_id, **changes):
        return VideoInfo.model_validate({**remote_video(remote_id), 'fileUrl': f'2023/04/16/sample-{remote_id}.evf', 'signature': None, 'metrics': None, **changes})

    def sources(self, count, **changes):
        SaoleiApiVideo.objects.bulk_create([
            SaoleiApiVideo(remote_id=index, user=self.account, upload_time=timezone.now(), level='b', status=20, software='Arbiter', **changes)
            for index in range(1, count + 1)
        ])

    def test_metadata_phase_batches_101_details_without_downloading_files(self):
        from io import StringIO

        self.remote.video_list.return_value = VideoListResponse.model_validate(remote_page([remote_video(index) for index in range(1, 102)]))
        with patch('accountlink.management.commands.sync_saolei_api.saolei_client', return_value=nullcontext(self.remote)):
            call_command('sync_saolei_api', account_id=[101], phase='metadata', stdout=StringIO(), stderr=StringIO())
        self.assertEqual([call.args[0] for call in self.remote.video_info.call_args_list], [list(range(1, 51)), list(range(51, 101)), [101]])
        self.remote.download_videos.assert_not_called()
        self.assertFalse(VideoModel.objects.exists())
        self.assertEqual(SaoleiApiVideo.objects.exclude(file_url__isnull=True).count(), 101)
        self.account.refresh_from_db()
        self.assertEqual(self.account.video_sync_cursor, 101)

    def test_video_phase_uses_only_saved_urls_and_respects_attempt_limit(self):
        from io import StringIO

        self.sources(3, file_url='2023/04/16/sample.evf')
        with patch('accountlink.management.commands.sync_saolei_api.saolei_client', return_value=nullcontext(self.remote)):
            with patch('accountlink.saolei.services.MSVideoParser', side_effect=ExceptionToResponse('file', 'review')):
                with self.assertRaises(CommandError):
                    call_command('sync_saolei_api', account_id=[101], phase='videos', limit=2, stdout=StringIO(), stderr=StringIO())
        self.remote.stats.assert_not_called()
        self.remote.user_info.assert_not_called()
        self.remote.video_list.assert_not_called()
        self.remote.video_info.assert_not_called()
        self.assertEqual(self.remote.download_videos.call_count, 2)
        self.assertEqual(SaoleiApiVideo.objects.filter(import_rejected=True).count(), 2)
        self.assertFalse(SaoleiApiVideo.objects.get(remote_id=3).import_rejected)

    def test_default_command_finishes_metadata_for_all_accounts_before_downloading(self):
        from io import StringIO

        bound_account(102, 'stage_order_other')
        events = []
        self.remote.stats.return_value.max_video_id = 200
        self.remote.user_info.side_effect = lambda account_id: SimpleNamespace(users=[SimpleNamespace(id=account_id, name='Remote', banned=False)])
        self.remote.video_list.side_effect = lambda **params: VideoListResponse.model_validate(remote_page([remote_video(params['player_id'], userId=params['player_id'])]))

        def details(ids):
            events.append(('details', ids))
            return SimpleNamespace(items=[self.detail(remote_id, userId=remote_id) for remote_id in ids])

        def reject_file(file, **kwargs):
            raise ExceptionToResponse('file', 'review')

        self.remote.video_info.side_effect = details
        self.remote.download_videos.side_effect = lambda urls: events.append(('download', urls)) or [FIXTURE.read_bytes()]
        with patch('accountlink.management.commands.sync_saolei_api.saolei_client', return_value=nullcontext(self.remote)):
            with patch('accountlink.saolei.services.MSVideoParser', side_effect=reject_file), self.assertRaises(CommandError):
                call_command('sync_saolei_api', all_linked=True, stdout=StringIO(), stderr=StringIO())
        self.assertEqual([event[0] for event in events], ['details', 'details', 'download', 'download'])

    def test_hourly_limit_is_global_and_failed_attempts_count_towards_100(self):
        def reject_file(file, **kwargs):
            raise ExceptionToResponse('file', 'review')

        self.sources(1001, file_url='2023/04/16/sample.evf')
        _, other = bound_account(1002, 'hourly_other')
        SaoleiApiVideo.objects.filter(remote_id__gt=500).update(user=other)
        SaoleiApiVideo.objects.create(remote_id=1002, user=self.account, upload_time=timezone.now(), level='b', status=20, software='Arbiter')
        self.account.auto_sync = False
        self.account.save(update_fields=['auto_sync'])
        with patch('accountlink.saolei.tasks.saolei_client', return_value=nullcontext(self.remote)):
            with patch('accountlink.saolei.services.MSVideoParser', side_effect=reject_file):
                with self.assertLogs('accountlink', level='ERROR'), self.assertRaises(ExceptionToResponse):
                    task_import_saolei_hourly.call()
        # Disabled accounts are excluded from both stages.
        self.assertEqual(self.remote.download_videos.call_count, 501)
        self.remote.reset_mock()
        SaoleiApiVideo.objects.update(import_rejected=False)
        self.account.auto_sync = True
        self.account.save(update_fields=['auto_sync'])
        with patch('accountlink.saolei.tasks.saolei_client', return_value=nullcontext(self.remote)):
            with patch('accountlink.saolei.services.MSVideoParser', side_effect=reject_file):
                with self.assertLogs('accountlink', level='ERROR'), self.assertRaises(ExceptionToResponse):
                    task_import_saolei_hourly.call()
        self.assertEqual(self.remote.download_videos.call_count, 1000)
        self.remote.stats.assert_not_called()
        self.remote.video_list.assert_not_called()
        self.remote.video_info.assert_not_called()
        self.assertEqual(SaoleiApiVideo.objects.filter(import_rejected=True).count(), 1000)
        self.assertFalse(SaoleiApiVideo.objects.get(remote_id=1001).import_rejected)
        self.assertFalse(SaoleiApiVideo.objects.get(remote_id=1002).import_rejected)

    def test_any_failure_marks_source_as_skipped(self):
        self.sources(2, file_url='2023/04/16/sample.evf')
        with patch('accountlink.saolei.services.import_saolei_video', side_effect=[TransportError('network down'), ExceptionToResponse('file', 'collision', 409)]) as imported:
            with patch('accountlink.saolei.tasks.saolei_client', return_value=nullcontext(self.remote)):
                with self.assertLogs('accountlink', level='ERROR'), self.assertRaises(ExceptionToResponse):
                    task_import_saolei_hourly.call()
        self.assertEqual(imported.call_count, 2)
        self.assertEqual(SaoleiApiVideo.objects.filter(import_rejected=True).count(), 2)
        with patch('accountlink.saolei.tasks.saolei_client', return_value=nullcontext(self.remote)):
            self.assertEqual(task_import_saolei_hourly.call(), {})
        self.assertEqual(imported.call_count, 2)

    def test_command_retries_rejected_sources_from_the_smallest_id(self):
        from io import StringIO

        self.sources(3, file_url='2023/04/16/sample.evf')
        SaoleiApiVideo.objects.filter(remote_id=3).update(software='Saolei.wang')
        SaoleiApiVideo.objects.update(import_rejected=True)
        with patch('accountlink.management.commands.sync_saolei_api.saolei_client', return_value=nullcontext(self.remote)):
            with patch('accountlink.saolei.services.import_saolei_video', return_value='imported') as imported:
                call_command('sync_saolei_api', account_id=[101], phase='videos', stdout=StringIO(), stderr=StringIO())
        self.assertEqual([item.args[0].remote_id for item in imported.call_args_list], [1, 2])
        self.assertEqual([item.kwargs['ignore_rejected'] for item in imported.call_args_list], [True, True])

    def test_hourly_import_continues_after_parser_process_crashes(self):
        self.sources(2, file_url='2023/04/16/sample.evf')
        launches = 0

        def launch(command, **kwargs):
            nonlocal launches
            launches += 1
            return abort_parser_process(command, **kwargs) if launches == 1 else run(command, **kwargs)

        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            with patch('accountlink.saolei.tasks.saolei_client', return_value=nullcontext(self.remote)):
                with patch('utils.parser.subprocess.run', side_effect=launch):
                    with self.assertLogs('utils.parser', level='ERROR'), self.assertLogs('accountlink', level='ERROR') as logs:
                        with self.assertRaises(ExceptionToResponse) as error:
                            task_import_saolei_hourly.call()
            self.assertEqual(error.exception.category, 'partial_sync')
            self.assertIn('来源录像#1', logs.output[0])
            self.assertIn('rust/panic', logs.output[0])
            self.assertEqual(self.remote.download_videos.call_count, 2)
            failed = SaoleiApiVideo.objects.get(remote_id=1)
            imported = SaoleiApiVideo.objects.get(remote_id=2)
            self.assertTrue(failed.import_rejected)
            self.assertIsNone(failed.import_video_id)
            self.assertIsNotNone(imported.import_video_id)
            self.assertEqual(VideoModel.objects.count(), 1)
            self.assertTrue(Path(imported.import_video.file.path).is_file())

    def test_batch_detail_owner_validation_rolls_back_all_writes(self):
        self.sources(2, file_url='2023/04/16/old.evf')
        sources = list(self.account.videos.order_by('remote_id'))
        with self.assertRaises(ResponseError):
            save_video_details(self.account, sources, [self.detail(1), self.detail(2, userId=102)])
        self.assertEqual(set(self.account.videos.values_list('file_url', flat=True)), {'2023/04/16/old.evf'})

    def test_hourly_import_keeps_the_binding_snapshot_between_files(self):
        self.sources(2, file_url='2023/04/16/sample.evf')
        replacement = UserProfile.objects.create_user(username='hourly_replacement')

        def change_binding(urls):
            AccountSaolei.objects.filter(pk=self.account.pk).update(parent=replacement)
            AccountLinkQueue.objects.filter(userprofile=self.user).update(userprofile=replacement)
            return [FIXTURE.read_bytes()]

        self.remote.download_videos.side_effect = change_binding
        with patch('accountlink.saolei.tasks.saolei_client', return_value=nullcontext(self.remote)):
            with self.assertLogs('accountlink', level='ERROR'), self.assertRaises(ExceptionToResponse):
                task_import_saolei_hourly.call()
        self.remote.download_videos.assert_called_once()
        self.assertFalse(VideoModel.objects.exists())
        self.assertEqual(SaoleiApiVideo.objects.filter(import_rejected=True).count(), 2)

    def test_missing_detail_keeps_saved_data_and_explicit_null_clears_url(self):
        self.sources(2, file_url='2023/04/16/old.evf')
        saved = save_video_details(self.account, list(self.account.videos.all()), [self.detail(1, fileUrl=None)])
        self.assertEqual([source.remote_id for source in saved], [1])
        self.assertIsNone(SaoleiApiVideo.objects.get(remote_id=1).file_url)
        self.assertEqual(SaoleiApiVideo.objects.get(remote_id=2).file_url, '2023/04/16/old.evf')

    def test_details_failed_after_cursor_commit_are_recovered_by_metadata_retry(self):
        from io import StringIO

        self.remote.stats.return_value.max_video_id = 1
        self.remote.video_list.return_value = VideoListResponse.model_validate(remote_page([remote_video()]))
        self.remote.video_info.side_effect = ResponseError('temporary response failure')
        with patch('accountlink.management.commands.sync_saolei_api.saolei_client', return_value=nullcontext(self.remote)):
            with self.assertRaises(CommandError):
                call_command('sync_saolei_api', account_id=[101], phase='metadata', stdout=StringIO(), stderr=StringIO())
            self.account.refresh_from_db()
            self.assertEqual(self.account.video_sync_cursor, 1)
            self.remote.video_list.reset_mock()
            self.remote.video_info.side_effect = lambda ids: SimpleNamespace(items=[self.detail(remote_id) for remote_id in ids])
            call_command('sync_saolei_api', account_id=[101], phase='metadata', stdout=StringIO(), stderr=StringIO())
        self.remote.video_list.assert_not_called()
        self.assertEqual(SaoleiApiVideo.objects.get(remote_id=1).file_url, '2023/04/16/sample-1.evf')
        self.remote.download_videos.assert_not_called()
