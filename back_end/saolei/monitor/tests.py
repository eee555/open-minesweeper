from datetime import datetime, timezone
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.tasks import TaskResultStatus
from django.test import override_settings, SimpleTestCase, TestCase
from django.urls import resolve, Resolver404
from django_tasks_db.models import DBTaskResult, get_date_max

from . import services
from .test_server_metrics import ready_process, ready_redis


@override_settings(RATELIMIT_ENABLE=False)
class MonitorSnapshotTests(SimpleTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'runtime' / 'monitor.json'
        setting = override_settings(MONITOR_SNAPSHOT_PATH=self.path)
        setting.enable()
        self.addCleanup(setting.disable)
        self.collectors = {}
        for name, result in (
            ('get_video_summary', {'total': 0, 'software': {}, 'level': {}, 'mode': {}, 'state': {}}),
            ('get_task_summary', {'total': 0, 'status': {'READY': 0}}),
            ('get_disk_usage', {'total': 100, 'used': 60, 'free': 40, 'video': 20, 'db': 10}),
            ('get_memory_usage', {'memory': ready_process(), 'redis': ready_redis()}),
        ):
            collector = patch.object(services, name, return_value=result)
            self.collectors[name] = collector.start()
            self.addCleanup(collector.stop)

    def read(self):
        return json.loads(self.path.read_text(encoding='utf-8'))

    def test_requests_only_read_published_file_and_missing_file_returns_503(self):
        self.assertEqual(self.client.get('/api/monitor/summary').status_code, 503)
        for collector in self.collectors.values():
            collector.assert_not_called()
        services.publish_monitor_snapshot()
        expected = self.read()
        self.assertEqual(set(expected), {'videosummary', 'tasksummary', 'diskusage', 'memoryusage'})
        for _ in range(2):
            response = self.client.get('/api/monitor/summary')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Cache-Control'], 'no-cache')
            self.assertEqual(json.loads(b''.join(response.streaming_content)), expected)
            response.close()
        for collector in self.collectors.values():
            collector.assert_called_once_with()

    def test_failed_sections_keep_their_previous_sample_while_others_update(self):
        services.publish_monitor_snapshot()
        previous = self.read()
        self.collectors['get_task_summary'].side_effect = RuntimeError('database unavailable')
        self.collectors['get_disk_usage'].return_value = {'invalid': 'disk sample'}
        self.collectors['get_video_summary'].return_value = {'total': 1, 'software': {'a': 1}, 'level': {}, 'mode': {}, 'state': {}}
        memory = self.collectors['get_memory_usage'].return_value
        memory['memory'] = {**memory['memory'], 'status': 'unavailable', 'reason': 'permission_denied', 'sampled_at': None, 'total_bytes': None, 'groups': None}
        memory['redis'] = {**memory['redis'], 'sampled_at': datetime(2026, 10, 25, tzinfo=timezone.utc)}
        with self.assertLogs('monitor.services', level='ERROR'):
            services.publish_monitor_snapshot()
        current = self.read()
        self.assertEqual(current['tasksummary'], previous['tasksummary'])
        self.assertEqual(current['diskusage'], previous['diskusage'])
        self.assertEqual(current['memoryusage']['memory'], previous['memoryusage']['memory'])
        self.assertNotEqual(current['memoryusage']['redis']['sampled_at'], previous['memoryusage']['redis']['sampled_at'])
        self.assertEqual(current['videosummary']['total'], 1)

    def test_initial_partial_failure_leaves_only_that_section_null(self):
        self.collectors['get_task_summary'].side_effect = RuntimeError('database unavailable')
        with self.assertLogs('monitor.services', level='ERROR'):
            services.publish_monitor_snapshot()
        current = self.read()
        self.assertIsNone(current['tasksummary'])
        self.assertIsNotNone(current['diskusage']['sampled_at'])

    def test_atomic_publication_keeps_old_file_until_replacement_and_cleans_failed_write(self):
        services.publish_monitor_snapshot()
        previous = self.path.read_bytes()
        replace = os.replace

        def check_replacement(source, destination):
            self.assertEqual(self.path.read_bytes(), previous)
            self.assertEqual(Path(source).parent, self.path.parent)
            self.assertEqual(json.loads(Path(source).read_text(encoding='utf-8'))['tasksummary']['total'], 2)
            replace(source, destination)

        self.collectors['get_task_summary'].return_value = {'total': 2, 'status': {'READY': 2}}
        with patch.object(services.os, 'replace', side_effect=check_replacement):
            services.publish_monitor_snapshot()
        self.assertEqual(self.read()['tasksummary']['total'], 2)
        previous = self.path.read_bytes()
        with patch.object(services.os, 'replace', side_effect=OSError('disk error')), self.assertRaises(OSError):
            services.publish_monitor_snapshot()
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_manual_command_publishes_snapshot(self):
        call_command('refresh_monitor_snapshot', stdout=StringIO())
        self.assertEqual(self.read()['tasksummary']['total'], 0)

    def test_invalid_previous_file_is_rebuilt(self):
        self.path.parent.mkdir()
        self.path.write_text('{incomplete', encoding='utf-8')
        with self.assertLogs('monitor.services', level='WARNING'):
            services.publish_monitor_snapshot()
        self.assertEqual(self.read()['tasksummary']['total'], 0)

    def test_old_statistics_and_world_monitor_routes_are_absent(self):
        for path in ('/api/monitor/diskusage', '/api/monitor/tasksummary', '/api/monitor/videosummary', '/api/monitor/memoryusage', '/api/common/diskusage', '/api/common/tasksummary', '/api/common/videosummary', '/monitor/io_cpus/', '/monitor/capacity/'):
            with self.subTest(path=path), self.assertRaises(Resolver404):
                resolve(path)


class MonitorStatisticsTests(TestCase):
    def test_task_summary_includes_empty_statuses(self):
        DBTaskResult.objects.create(status=TaskResultStatus.READY, args_kwargs={'args': [], 'kwargs': {}}, run_after=get_date_max())
        self.assertEqual(services.get_task_summary(), {
            'total': 1,
            'status': {str(status): int(status == TaskResultStatus.READY) for status in TaskResultStatus},
        })

    def test_empty_video_summary_retains_all_choice_groups(self):
        result = services.get_video_summary()
        self.assertEqual(result['total'], 0)
        for name in ('software', 'level', 'mode', 'state'):
            self.assertTrue(result[name])
            self.assertTrue(all(count == 0 for count in result[name].values()))

    def test_disk_usage_preserves_response_fields(self):
        with (
            patch.object(services.psutil, 'disk_usage', return_value=SimpleNamespace(total=100, used=60, free=40)),
            patch.object(services, 'get_db_size', return_value=10),
        ):
            result = services.get_disk_usage()
        self.assertEqual(result, {'total': 100, 'used': 60, 'free': 40, 'video': None, 'db': 10})
