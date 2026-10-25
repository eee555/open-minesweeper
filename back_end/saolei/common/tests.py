from datetime import datetime, timedelta, timezone as datetime_timezone
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlencode

from django.core.files import File
from django.core.files.uploadedfile import SimpleUploadedFile
from django.tasks import TaskResultStatus
from django.test import override_settings, TestCase
from django.utils import timezone
from django_apscheduler.models import DjangoJob
from django_redis import get_redis_connection
from django_tasks_db.models import DBTaskResult, get_date_max

from common.management.commands import db_worker_robust
from config.common import TASK_CLEANUP_CONFIGS
from config.customranking import CUSTOM_PLUCK_LEVELS, CUSTOM_PLUCK_MODES
from config.text_choices import MS_TextChoices, Tournament_TextChoices
from customranking.cache import PLuckRankingCache
from identifier.models import Identifier
from msuser.models import UserMS
from msuser.utils import get_video_num_limit
from speedranking.pb.cache import PBRankingCache
from speedranking.saolei.cache import SpeedRankingCache
from speedranking.saolei.utils import RANK_STATS
from tournament.cache import TournamentCache
from tournament.models import GSCParticipant, GSCTournament
from userprofile.models import UserProfile
from utils.parser import MSVideoParser
from videomanager.models import ExpandVideoModel, VideoModel
from . import api as common_api


FIXTURE_DIR = Path(__file__).resolve().parent / 'test_fixtures' / 'video_upload_ranking'
EXPERT_PERSONAL_PLUCK = 0.16342814596696364
CUSTOM_PLUCK_FIXTURE_PLUCK = 6.493148642054213


class APSchedulerRegistrationTests(TestCase):
    def test_combined_scheduler_registers_all_jobs(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        from common.apscheduler import register_jobs

        scheduler = BackgroundScheduler()
        register_jobs(scheduler)

        self.assertEqual(
            {job.id for job in scheduler.get_jobs()},
            {
                'delete_freezed_video',
                'delete_newest_queue',
                'delete_old_job_executions',
                'delete_overdue_captcha',
                'delete_overdue_emailverifyrecord',
                'delete_overdue_tasks',
                'refresh_tournament_score_reference',
                'refresh_monitor_snapshot',
            },
        )

    def test_monitor_snapshot_runs_on_startup_and_every_five_minutes(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        from common.apscheduler import refresh_monitor_snapshot, register_jobs

        scheduler = BackgroundScheduler(timezone=datetime_timezone.utc)
        now = datetime(2026, 10, 25, 12, 1, tzinfo=datetime_timezone.utc)
        with patch('common.apscheduler.django_timezone.now', return_value=now):
            register_jobs(scheduler)
        job = scheduler.get_job('refresh_monitor_snapshot')
        self.assertEqual(job.func, refresh_monitor_snapshot)
        self.assertEqual(job.next_run_time, now)
        self.assertEqual(job.max_instances, 1)
        self.assertTrue(job.coalesce)
        first_run = job.trigger.get_next_fire_time(None, now)
        self.assertEqual(first_run, now.replace(minute=5))
        self.assertEqual(job.trigger.get_next_fire_time(first_run, first_run), first_run + timedelta(minutes=5))

    def test_task_cleanup_runs_weekly_in_scheduler_timezone(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        from common.apscheduler import delete_overdue_tasks, register_jobs

        scheduler = BackgroundScheduler(timezone=datetime_timezone(timedelta(hours=8)))
        register_jobs(scheduler)
        job = scheduler.get_job('delete_overdue_tasks')
        monday = datetime(2026, 10, 19, 1, 10, tzinfo=scheduler.timezone)

        self.assertEqual(job.func, delete_overdue_tasks)
        self.assertEqual(job.max_instances, 1)
        self.assertEqual(job.trigger.get_next_fire_time(None, monday), monday)
        self.assertEqual(job.trigger.get_next_fire_time(monday, monday), monday + timedelta(days=7))

    def test_newest_queue_cleanup_runs_daily_at_original_time(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        from common.apscheduler import register_jobs
        from videomanager.services import delete_newest_queue

        scheduler = BackgroundScheduler(timezone=datetime_timezone.utc)
        register_jobs(scheduler)
        job = scheduler.get_job('delete_newest_queue')
        now = datetime(2026, 10, 22, 1, 7, tzinfo=job.trigger.timezone)
        first_run = job.trigger.get_next_fire_time(None, now)

        self.assertEqual(job.func, delete_newest_queue)
        self.assertEqual(job.max_instances, 1)
        self.assertEqual(first_run, now.replace(minute=8))
        self.assertEqual(job.trigger.get_next_fire_time(first_run, first_run), first_run + timedelta(days=1))

    def test_registration_removes_only_retired_monitor_job(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        from common.apscheduler import register_jobs

        DjangoJob.objects.create(id='refresh_state_always', job_state=b'old monitor job')
        DjangoJob.objects.create(id='delete_newest_queue', job_state=b'existing cleanup job')

        register_jobs(BackgroundScheduler())

        self.assertFalse(DjangoJob.objects.filter(id='refresh_state_always').exists())
        self.assertTrue(DjangoJob.objects.filter(id='delete_newest_queue').exists())

    def test_score_reference_job_runs_annually_in_utc_and_checks_on_startup(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        from common.apscheduler import register_jobs, refresh_tournament_score_reference

        scheduler = BackgroundScheduler()
        now = datetime(2026, 12, 31, 23, 59, 59, tzinfo=datetime_timezone.utc)
        with patch('common.apscheduler.django_timezone.now', return_value=now):
            register_jobs(scheduler)
        job = scheduler.get_job('refresh_tournament_score_reference')
        self.assertEqual(job.func, refresh_tournament_score_reference)
        self.assertEqual(job.next_run_time, now)
        self.assertIsNone(job.misfire_grace_time)
        self.assertTrue(job.coalesce)
        self.assertEqual(job.max_instances, 1)
        self.assertEqual(job.trigger.get_next_fire_time(now, now), datetime(2027, 1, 1, tzinfo=datetime_timezone.utc))


class LogPollTests(TestCase):
    def setUp(self):
        self.log_dir_context = tempfile.TemporaryDirectory()
        self.log_dir = Path(self.log_dir_context.name)
        self.log_dir_patch = patch.object(common_api, 'LOG_DIR', self.log_dir)
        self.log_dir_patch.start()

    def tearDown(self):
        self.log_dir_patch.stop()
        self.log_dir_context.cleanup()

    def write_log(self, filename: str, content: str):
        path = self.log_dir / filename
        path.write_bytes(content.encode())
        return path

    def test_poll_returns_content_from_offset(self):
        content = 'first\nsecond\n'
        offset = len('first\n'.encode())
        self.write_log('app.log', content)

        response = common_api.poll_log_tail(None, 'app.log', offset=offset)

        self.assertEqual(response, {
            'content': 'second\n',
            'offset': len(content.encode()),
            'size': len(content.encode()),
            'status': 'ok',
        })

    def test_poll_returns_empty_content_when_offset_matches_file_size(self):
        content = 'ready\n'
        self.write_log('app.log', content)

        response = common_api.poll_log_tail(None, 'app.log', offset=len(content.encode()))

        self.assertEqual(response, {
            'content': '',
            'offset': len(content.encode()),
            'size': len(content.encode()),
            'status': 'ok',
        })

    def test_poll_returns_reset_and_tail_when_file_shrinks(self):
        content = 'new-tail'
        self.write_log('app.log', content)

        response = common_api.poll_log_tail(None, 'app.log', offset=20, tail_bytes=4)

        self.assertEqual(response, {
            'content': 'tail',
            'offset': len(content.encode()),
            'size': len(content.encode()),
            'status': 'reset',
        })

    def test_poll_returns_deleted_when_file_disappears(self):
        response = common_api.poll_log_tail(None, 'app.log')

        self.assertEqual(response, {
            'content': '',
            'offset': 0,
            'size': 0,
            'status': 'deleted',
        })

    def test_list_logs_uses_file_modified_time(self):
        log_path = self.write_log('app.log', 'ready\n')
        modified_at = 1710979200
        os.utime(log_path, (modified_at - 3600, modified_at))

        [response] = common_api.list_logs(None)

        self.assertEqual(response['name'], 'app.log')
        self.assertEqual(response['mtime'].timestamp(), modified_at)


class TaskDeletionTests(TestCase):
    def setUp(self):
        self.staff = UserProfile.objects.create_user(
            username='task_delete_staff',
            email='task_delete_staff@example.com',
            password='password',
            is_staff=True,
        )
        self.client.force_login(self.staff)

    def test_task_summary_reads_current_database_counts(self):
        task = self.create_task()
        first = self.client.get('/api/common/tasks/summary')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()['status']['READY'], 1)
        DBTaskResult.objects.filter(pk=task.pk).update(status=TaskResultStatus.SUCCESSFUL)
        second = self.client.get('/api/common/tasks/summary')
        self.assertEqual(second['Cache-Control'], 'no-cache')
        self.assertEqual(second.json()['status']['READY'], 0)
        self.assertEqual(second.json()['status']['SUCCESSFUL'], 1)
        self.assertEqual(second.json()['total'], 1)

    def test_task_summary_requires_staff(self):
        self.client.logout()
        self.assertEqual(self.client.get('/api/common/tasks/summary').status_code, 403)
        self.staff.is_staff = False
        self.staff.save(update_fields=['is_staff'])
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get('/api/common/tasks/summary').status_code, 403)

    def create_task(
        self,
        *,
        status: TaskResultStatus = TaskResultStatus.READY,
        task_path: str = 'videomanager.tasks.task_video_pluck',
        args=None,
        kwargs=None,
        priority: int = 0,
        run_after=None,
        finished_at=None,
        started_at=None,
        worker_ids=None,
    ):
        task = DBTaskResult.objects.create(
            status=status,
            args_kwargs={'args': [] if args is None else args, 'kwargs': {} if kwargs is None else kwargs},
            priority=priority,
            task_path=task_path,
            worker_ids=worker_ids or [],
            queue_name='default',
            backend_name='default',
            run_after=get_date_max() if run_after is None else run_after,
        )
        if started_at is not None:
            DBTaskResult.objects.filter(id=task.id).update(started_at=started_at)
            task.refresh_from_db()
        if finished_at is not None:
            DBTaskResult.objects.filter(id=task.id).update(finished_at=finished_at)
            task.refresh_from_db()
        return task

    def test_delete_ready_task(self):
        task = self.create_task()

        response = self.client.post(
            '/api/common/tasks/delete',
            urlencode({'task_id': str(task.id)}),
            content_type='application/x-www-form-urlencoded',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json())
        self.assertFalse(DBTaskResult.objects.filter(id=task.id).exists())

    def test_delete_running_task_returns_conflict(self):
        task = self.create_task(status=TaskResultStatus.RUNNING)

        response = self.client.post(
            '/api/common/tasks/delete',
            urlencode({'task_id': str(task.id)}),
            content_type='application/x-www-form-urlencoded',
        )

        self.assertEqual(response.status_code, 409)
        self.assertTrue(DBTaskResult.objects.filter(id=task.id).exists())

    def test_task_detail_api_returns_db_task_schema(self):
        task = self.create_task(
            status=TaskResultStatus.FAILED,
            task_path='accountlink.tasks.task_saolei_video_import_bulk',
            args=[100001, 'new'],
            kwargs={'source': 'test'},
            priority=2,
            finished_at=timezone.now(),
            worker_ids=['test-worker'],
        )

        response = self.client.get('/api/common/tasks/detail')

        self.assertEqual(response.status_code, 200)
        data = next(item for item in response.json() if item['id'] == str(task.id))
        self.assertEqual(data['id'], str(task.id))
        self.assertEqual(data['status'], TaskResultStatus.FAILED)
        self.assertEqual(data['args_kwargs'], {'args': [100001, 'new'], 'kwargs': {'source': 'test'}})
        self.assertEqual(data['priority'], 2)
        self.assertEqual(data['task_path'], 'accountlink.tasks.task_saolei_video_import_bulk')
        self.assertEqual(data['worker_ids'], ['test-worker'])
        self.assertEqual(data['queue_name'], 'default')
        self.assertEqual(data['backend_name'], 'default')
        self.assertIn('traceback', data)

    def test_cleanup_tasks_deletes_only_one_batch_per_config(self):
        old_finished_at = timezone.now() - TASK_CLEANUP_CONFIGS[0]['expires'] - timedelta(days=1)
        for _ in range(3):
            self.create_task(
                status=TaskResultStatus.SUCCESSFUL,
                task_path=TASK_CLEANUP_CONFIGS[0]['task_path'],
                finished_at=old_finished_at,
            )

        with patch('common.services.TASK_CLEANUP_BATCH_SIZE', 2):
            deleted_count = common_api.cleanup_tasks(SimpleNamespace(user=self.staff))

        self.assertEqual(deleted_count, 2)
        self.assertEqual(
            DBTaskResult.objects.filter(
                status=TaskResultStatus.SUCCESSFUL,
                task_path=TASK_CLEANUP_CONFIGS[0]['task_path'],
            ).count(),
            1,
        )

    def test_scheduled_cleanup_deletes_all_batches_and_preserves_ineligible_tasks(self):
        from common.apscheduler import delete_overdue_tasks

        for config in TASK_CLEANUP_CONFIGS:
            for _ in range(3):
                self.create_task(
                    status=TaskResultStatus.SUCCESSFUL,
                    task_path=config['task_path'],
                    finished_at=timezone.now() - config['expires'] - timedelta(days=1),
                )
        old_finished_at = timezone.now() - timedelta(days=365)
        retained_tasks = [
            self.create_task(status=TaskResultStatus.SUCCESSFUL, finished_at=timezone.now()),
            self.create_task(status=TaskResultStatus.FAILED, finished_at=old_finished_at),
            self.create_task(status=TaskResultStatus.RUNNING),
            self.create_task(status=TaskResultStatus.READY),
            self.create_task(status=TaskResultStatus.SUCCESSFUL, task_path='unknown.task', finished_at=old_finished_at),
        ]

        with patch('common.services.TASK_CLEANUP_BATCH_SIZE', 2), patch('django_apscheduler.util.db.close_old_connections'):
            delete_overdue_tasks()

        self.assertSetEqual(set(DBTaskResult.objects.values_list('id', flat=True)), {task.id for task in retained_tasks})

    def test_running_task_health_marks_stale_unknown_worker_as_probably_orphaned(self):
        started_at = timezone.now() - timedelta(minutes=10)
        task = self.create_task(
            status=TaskResultStatus.RUNNING,
            started_at=started_at,
            worker_ids=['legacy-random-worker-id'],
        )

        result = common_api.running_task_health(SimpleNamespace(user=self.staff), stale_after_seconds=60)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], str(task.id))
        self.assertEqual(result[0]['worker_state'], common_api.WORKER_STATE_UNKNOWN)
        self.assertTrue(result[0]['stale_by_age'])
        self.assertTrue(result[0]['probably_orphaned'])

    def test_running_task_health_marks_dead_pid_worker_as_orphaned(self):
        started_at = timezone.now()
        task = self.create_task(
            status=TaskResultStatus.RUNNING,
            started_at=started_at,
            worker_ids=['testhost-12345-1700000000'],
        )

        with (
            patch.object(common_api, '_local_hostname_aliases', return_value={'testhost'}),
            patch.object(common_api.psutil, 'Process', side_effect=common_api.psutil.NoSuchProcess(12345)),
        ):
            result = common_api.running_task_health(SimpleNamespace(user=self.staff))

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], str(task.id))
        self.assertEqual(result[0]['worker_state'], common_api.WORKER_STATE_DEAD)
        self.assertFalse(result[0]['stale_by_age'])
        self.assertTrue(result[0]['probably_orphaned'])

    def test_restart_failed_task_reenqueues_same_task_and_updates_task_path_reference(self):
        run_after = timezone.now() - timedelta(minutes=1)
        gsc_task = self.create_task(
            status=TaskResultStatus.FAILED,
            task_path='tournament.gsc.tasks.task_gsc_finish',
            kwargs={'gsc_order': 100},
            run_after=run_after,
            finished_at=timezone.now(),
        )
        tournament = GSCTournament.objects.create(
            order=100,
            start_time=timezone.now() - timedelta(days=1),
            end_time=timezone.now() - timedelta(hours=1),
            state=Tournament_TextChoices.State.AWARDED,
            host=self.staff,
            task=gsc_task,
        )

        cases = [
            (
                gsc_task,
                tournament,
                'task_id',
            ),
        ]
        for old_task, obj, task_field_id in cases:
            response = self.client.post(
                '/api/common/tasks/restart',
                urlencode({'task_id': str(old_task.id)}),
                content_type='application/x-www-form-urlencoded',
            )

            self.assertEqual(response.status_code, 200, response.content)
            response_data = response.json()
            new_task = DBTaskResult.objects.get(id=response_data['id'])
            self.assertNotEqual(old_task.id, new_task.id)
            self.assertEqual(new_task.status, TaskResultStatus.READY)
            self.assertEqual(new_task.task_path, old_task.task_path)
            self.assertEqual(new_task.args_kwargs, old_task.args_kwargs)
            self.assertEqual(new_task.priority, old_task.priority)
            self.assertEqual(new_task.queue_name, old_task.queue_name)
            self.assertEqual(new_task.backend_name, old_task.backend_name)
            self.assertEqual(new_task.run_after, old_task.run_after)

            obj.refresh_from_db()
            self.assertEqual(getattr(obj, task_field_id), new_task.id)
            self.assertEqual(response_data['task_path'], old_task.task_path)
            self.assertEqual(response_data['args_kwargs'], old_task.args_kwargs)

    def test_restart_task_with_stale_business_reference_returns_conflict(self):
        failed_task = self.create_task(
            status=TaskResultStatus.FAILED,
            task_path='tournament.gsc.tasks.task_gsc_finish',
            args=[103],
            finished_at=timezone.now(),
        )
        current_task = self.create_task(
            status=TaskResultStatus.READY,
            task_path='tournament.gsc.tasks.task_gsc_finish',
            args=[103],
        )
        GSCTournament.objects.create(
            order=103,
            start_time=timezone.now() - timedelta(days=1),
            end_time=timezone.now() - timedelta(hours=1),
            state=Tournament_TextChoices.State.AWARDED,
            host=self.staff,
            task=current_task,
        )

        response = self.client.post(
            '/api/common/tasks/restart',
            urlencode({'task_id': str(failed_task.id)}),
            content_type='application/x-www-form-urlencoded',
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {
            'type': 'error',
            'object': 'task_restart',
            'category': 'stale_reference',
        })
        self.assertEqual(DBTaskResult.objects.count(), 2)

    def test_restart_task_with_invalid_business_arguments_returns_error_body(self):
        failed_task = self.create_task(
            status=TaskResultStatus.FAILED,
            task_path='tournament.gsc.tasks.task_gsc_finish',
            finished_at=timezone.now(),
        )

        response = self.client.post(
            '/api/common/tasks/restart',
            urlencode({'task_id': str(failed_task.id)}),
            content_type='application/x-www-form-urlencoded',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {
            'type': 'error',
            'object': 'task_restart',
            'category': 'invalid_args',
        })
        self.assertEqual(DBTaskResult.objects.count(), 1)

    def test_restart_non_failed_task_returns_conflict(self):
        task = self.create_task(status=TaskResultStatus.READY)

        response = self.client.post(
            '/api/common/tasks/restart',
            urlencode({'task_id': str(task.id)}),
            content_type='application/x-www-form-urlencoded',
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(DBTaskResult.objects.count(), 1)

    def robust_command_options(self, pidfile: Path):
        return {
            'queue_name': 'default',
            'interval': 2,
            'batch': False,
            'backend_name': 'default',
            'startup_delay': False,
            'max_tasks': None,
            'worker_id': 'testhost-12345-1700000000',
            'pidfile': str(pidfile),
            'verbosity': 1,
        }

    def test_db_worker_robust_exits_when_worker_is_already_running(self):
        task = self.create_task(status=TaskResultStatus.RUNNING, started_at=timezone.now())

        with tempfile.TemporaryDirectory() as temp_dir:
            pidfile = Path(temp_dir) / 'worker.pid'
            with (
                patch.object(
                    db_worker_robust,
                    'iter_running_worker_processes',
                    return_value=[SimpleNamespace(info={'pid': 98765})],
                ),
                patch.object(db_worker_robust, 'call_command') as call_mock,
            ):
                db_worker_robust.Command().handle(**self.robust_command_options(pidfile))

        task.refresh_from_db()
        self.assertEqual(task.status, TaskResultStatus.RUNNING)
        call_mock.assert_not_called()

    def test_db_worker_robust_fails_orphans_then_starts_safe_worker(self):
        task = self.create_task(
            status=TaskResultStatus.RUNNING,
            started_at=timezone.now() - timedelta(minutes=1),
            worker_ids=['legacy-worker-id'],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            pidfile = Path(temp_dir) / 'worker.pid'
            with (
                patch.object(db_worker_robust, 'iter_running_worker_processes', return_value=[]),
                patch.object(db_worker_robust, 'call_command') as call_mock,
            ):
                db_worker_robust.Command().handle(**self.robust_command_options(pidfile))

        task.refresh_from_db()
        self.assertEqual(task.status, TaskResultStatus.FAILED)
        self.assertEqual(task.exception_class_path, 'builtins.RuntimeError')
        self.assertIn('db_worker_robust', task.traceback)
        call_mock.assert_called_once()
        self.assertEqual(call_mock.call_args.args, ('db_worker',))
        self.assertFalse(call_mock.call_args.kwargs['reload'])
        self.assertTrue(call_mock.call_args.kwargs['skip_checks'])
        self.assertEqual(call_mock.call_args.kwargs['worker_id'], 'testhost-12345-1700000000')


class VideoUploadRankingIntegrationTest(TestCase):
    def setUp(self):
        pb = PBRankingCache()
        pb.flush()
        self.addCleanup(pb.flush)
        for ranking_name in ('saolei', 'saolei_nf'):
            ranking = SpeedRankingCache(ranking_name, stats=RANK_STATS)
            ranking.flush()
            self.addCleanup(ranking.flush)
        for level in CUSTOM_PLUCK_LEVELS:
            PLuckRankingCache(level).flush()
        self.media_dir = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media_dir.name,
            RATELIMIT_ENABLE=False,
        )
        self.settings_override.enable()
        self.userms = UserMS.objects.create()
        self.user = UserProfile.objects.create_user(
            username='video_upload_rank_user',
            email='video_upload_rank@example.com',
            password='password',
            realname='测试用户',
            userms=self.userms,
        )
        self.client.force_login(self.user)

    def tearDown(self):
        cache = get_redis_connection('saolei_website')
        cache.delete('newest_queue', 'freeze_queue')
        for level in CUSTOM_PLUCK_LEVELS:
            PLuckRankingCache(level).flush()
        self.settings_override.disable()
        self.media_dir.cleanup()

    def fixture_path(self, filename: str) -> Path:
        path = FIXTURE_DIR / filename
        if not path.exists():
            self.skipTest(f'缺少测试录像 fixture: {path}')
        return path

    def parse_fixture(self, path: Path) -> MSVideoParser:
        with path.open('rb') as file:
            return MSVideoParser(File(file, name=path.name))

    def bind_identifier(self, identifier: str):
        Identifier.objects.update_or_create(
            identifier=identifier,
            defaults={
                'userms': self.userms,
                'safe': True,
            },
        )

    def add_identifier_by_request(self, identifier: str):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/identifier/add/', {'identifier': identifier})
        self.assertEqual(response.status_code, 200, response.content)
        return json.loads(response.content)

    def delete_identifier_by_request(self, identifier: str):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/identifier/del/', {'identifier': identifier})
        self.assertEqual(response.status_code, 200, response.content)
        return json.loads(response.content)

    def get_pluck_rank_by_request(self, level: str):
        response = self.client.get(
            '/api/customranking/pluck',
            {'level': level, 'start': 0, 'end': 20},
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def assert_pluck_task_not_enqueued(self, video: VideoModel):
        self.assertFalse(
            DBTaskResult.objects.filter(
                task_path='videomanager.tasks.task_video_pluck',
                args_kwargs={'args': [video.id], 'kwargs': {}},
            ).exists(),
        )

    def upload_fixture(self, filename: str, *, bind_identifier=True):
        path = self.fixture_path(filename)
        parser = self.parse_fixture(path)
        if bind_identifier:
            self.bind_identifier(parser.identifier)

        with path.open('rb') as file:
            uploaded_file = SimpleUploadedFile(path.name, file.read())

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/common/uploadvideo/', {'file': uploaded_file})
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)
        video = VideoModel.objects.select_related('video', 'player__userms').get(pk=data['data']['id'])
        return video, parser

    def test_upload_tournament_video_checks_in(self):
        parser = self.parse_fixture(self.fixture_path('standard_gsc.evf'))
        token = next((identifier for identifier in parser.tournament_identifier if identifier), None)
        if token is None:
            self.skipTest('standard_gsc.evf 需要包含非空 GSC token')

        now = timezone.now()
        tournament = GSCTournament.objects.create(
            order=1,
            token=token,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            state=Tournament_TextChoices.State.NORMAL,
        )
        participant = GSCParticipant.objects.create(
            tournament=tournament,
            user=self.user,
            token=token,
            start_time=tournament.start_time,
            end_time=tournament.end_time,
        )
        tournament_cache = TournamentCache()
        tournament_cache.update_tournament(tournament)
        tournament_cache.update_participant(participant)

        video, _ = self.upload_fixture('standard_gsc.evf')

        video.refresh_from_db()
        self.assertTrue(video.ongoing_tournament)
        self.assertTrue(tournament.videos.filter(pk=video.pk).exists())

    def test_upload_incomplete_video_does_not_create_records_or_store_files(self):
        path = self.fixture_path('incomplete.evf')
        uploaded_file = SimpleUploadedFile(path.name, path.read_bytes())

        response = self.client.post('/common/uploadvideo/', {'file': uploaded_file})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'type': 'error', 'object': 'file', 'category': 'incomplete'})
        self.assertFalse(VideoModel.objects.exists())
        self.assertFalse(ExpandVideoModel.objects.exists())
        self.assertEqual(list(Path(self.media_dir.name).rglob('*')), [])
        self.userms.refresh_from_db()
        self.assertEqual(self.userms.video_num_total, 0)

    def test_identifier_bind_and_unbind_updates_video_state(self):
        parser = self.parse_fixture(self.fixture_path('beginner_personal.evf'))
        identifier = Identifier.objects.create(identifier=parser.identifier, safe=True)

        video, parser = self.upload_fixture('beginner_personal.evf', bind_identifier=False)

        video.refresh_from_db()
        self.assertEqual(video.state, MS_TextChoices.State.IDENTIFIER)
        self.assertEqual(self.client.get('/api/speedranking/rank', {'stat': 'bt'}).json()['count'], 0)

        self.add_identifier_by_request(identifier.identifier)

        video.refresh_from_db()
        self.assertEqual(video.state, MS_TextChoices.State.OFFICIAL)
        rank = self.client.get('/api/speedranking/rank', {'stat': 'bt'}).json()
        self.assertEqual(video.bv, 1)
        self.assertEqual(rank['count'], 0)

        self.delete_identifier_by_request(identifier.identifier)

        video.refresh_from_db()
        self.assertEqual(video.state, MS_TextChoices.State.IDENTIFIER)
        self.assertEqual(self.client.get('/api/speedranking/rank', {'stat': 'bt'}).json()['count'], 0)

    def test_identifier_bind_refreshes_video_num_limit_for_expert_standard_video(self):
        parser = self.parse_fixture(self.fixture_path('expert_personal.evf'))
        if parser.level != MS_TextChoices.Level.EXPERT or parser.mode != MS_TextChoices.Mode.STD:
            self.skipTest('expert_personal.evf 需要是高级标准录像')
        identifier = Identifier.objects.create(identifier=parser.identifier, safe=True)

        video, _ = self.upload_fixture('expert_personal.evf', bind_identifier=False)

        video.refresh_from_db()
        self.userms.refresh_from_db()
        self.assertEqual(video.state, MS_TextChoices.State.IDENTIFIER)
        self.assertAlmostEqual(video.pluck, EXPERT_PERSONAL_PLUCK, places=12)
        self.assert_pluck_task_not_enqueued(video)
        self.assertEqual(self.userms.video_num_limit, 100)

        self.add_identifier_by_request(identifier.identifier)

        video.refresh_from_db()
        self.userms.refresh_from_db()
        self.assertEqual(video.state, MS_TextChoices.State.OFFICIAL)
        self.assertEqual(self.userms.video_num_limit, get_video_num_limit(parser.timems))
        rank = self.client.get('/api/speedranking/rank', {'stat': 'et'}).json()
        self.assertEqual(rank['count'], 1)
        self.assertEqual(rank['players'][0]['et_id'], video.id)
        self.delete_identifier_by_request(identifier.identifier)
        self.assertEqual(self.client.get('/api/speedranking/rank', {'stat': 'et'}).json()['count'], 0)

    def test_upload_custom_video_calculates_pluck_and_refreshes_custom_pluck_record(self):
        video, parser = self.upload_fixture('custom_pluck.evf')
        if parser.level not in CUSTOM_PLUCK_LEVELS or parser.mode not in CUSTOM_PLUCK_MODES:
            self.skipTest('custom_pluck.evf 需要是 Density 排行支持的自定义级别和模式')

        video.refresh_from_db()
        self.assertAlmostEqual(video.pluck, CUSTOM_PLUCK_FIXTURE_PLUCK, places=12)
        self.assert_pluck_task_not_enqueued(video)
        rank = self.get_pluck_rank_by_request(parser.level)
        self.assertEqual(rank['count'], 1)
        self.assertEqual(rank['players'][0]['video_id'], video.id)
        self.assertAlmostEqual(rank['players'][0]['pluck'], CUSTOM_PLUCK_FIXTURE_PLUCK, places=12)
        response = self.client.get('/api/video/staticdetailbatch', {'ids': rank['players'][0]['video_id']})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()[0]['timems'], video.timems)

    def test_identifier_bind_and_unbind_refreshes_custom_pluck_record(self):
        parser = self.parse_fixture(self.fixture_path('custom_pluck.evf'))
        if parser.level not in CUSTOM_PLUCK_LEVELS or parser.mode not in CUSTOM_PLUCK_MODES:
            self.skipTest('custom_pluck.evf 需要是 Density 排行支持的自定义级别和模式')
        identifier = Identifier.objects.create(identifier=parser.identifier, safe=True)

        video, parser = self.upload_fixture('custom_pluck.evf', bind_identifier=False)

        video.refresh_from_db()
        self.assertEqual(video.state, MS_TextChoices.State.IDENTIFIER)
        self.assertAlmostEqual(video.pluck, CUSTOM_PLUCK_FIXTURE_PLUCK, places=12)
        self.assert_pluck_task_not_enqueued(video)
        rank = self.get_pluck_rank_by_request(parser.level)
        self.assertEqual(rank['count'], 0)

        self.add_identifier_by_request(identifier.identifier)

        video.refresh_from_db()
        self.assertEqual(video.state, MS_TextChoices.State.OFFICIAL)
        rank = self.get_pluck_rank_by_request(parser.level)
        self.assertEqual(rank['count'], 1)
        self.assertEqual(rank['players'][0]['video_id'], video.id)
        self.assertAlmostEqual(rank['players'][0]['pluck'], CUSTOM_PLUCK_FIXTURE_PLUCK, places=12)

        self.delete_identifier_by_request(identifier.identifier)

        video.refresh_from_db()
        self.assertEqual(video.state, MS_TextChoices.State.IDENTIFIER)
        rank = self.get_pluck_rank_by_request(parser.level)
        self.assertEqual(rank['count'], 0)
