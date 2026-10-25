from collections import Counter
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import override_settings, SimpleTestCase
import psutil
from redis.exceptions import ConnectionError as RedisConnectionError

from minigame.utils import RANKINGS
from . import cache as monitor_cache, server_metrics, services


def ready_process():
    return {
        'status': 'ready', 'reason': None, 'sampled_at': datetime(2026, 10, 15, tzinfo=timezone.utc),
        'metric': 'pss', 'total_bytes': 60,
        'groups': dict.fromkeys(server_metrics.PROCESS_GROUPS, 10),
        'host': {'total_bytes': 1000, 'available_bytes': 500}, 'unreadable_processes': 0,
    }


def ready_redis():
    return {
        'status': 'ready', 'reason': None, 'sampled_at': datetime(2026, 10, 15, tzinfo=timezone.utc),
        'metric': 'redis_allocated', 'total_bytes': 100,
        'groups': {'pb_rankings': 10, 'other_rankings': 20, 'latest_videos': 30, 'other': 40},
        'estimated': True, 'samples': 5,
    }


class ProcessMemoryTests(SimpleTestCase):
    def process(self, pid, name, command=None, cwd=None, pss=10, rss=100):
        return SimpleNamespace(
            pid=pid, info={'name': name, 'exe': name, 'cmdline': command or []},
            cwd=MagicMock(return_value=str(cwd or settings.BASE_DIR)),
            memory_full_info=MagicMock(return_value=SimpleNamespace(pss=pss, rss=rss)),
            memory_info=MagicMock(return_value=SimpleNamespace(rss=rss)),
        )

    def collect(self, processes, platform='linux', deadline=float('inf')):
        with (
            patch.object(server_metrics.sys, 'platform', platform),
            patch.object(server_metrics, '_is_containerized', return_value=False),
            patch.object(server_metrics.psutil, 'process_iter', return_value=processes),
            patch.object(server_metrics.psutil, 'virtual_memory', return_value=SimpleNamespace(total=10000, available=5000)),
        ):
            return server_metrics.collect_process_memory(settings.BASE_DIR, deadline)

    def test_pss_groups_uwsgi_master_and_workers_without_double_counting_pids(self):
        master = self.process(1, 'uwsgi')
        processes = [
            master, master, self.process(2, 'uwsgi'),
            self.process(3, 'python3', ['python3', '-u', 'manage.py', 'runapscheduler']),
            self.process(4, 'redis-server'), self.process(5, 'mysqld'),
            self.process(6, 'python3', ['python3', 'manage.py', 'db_worker_robust']),
            self.process(7, 'bash', ['bash', 'run_background.sh', 'apscheduler']),
        ]
        result = self.collect(processes)
        self.assertEqual(result['groups'], {'uwsgi': 20, 'apscheduler': 10, 'redis': 10, 'mysql': 10, 'db_worker': 10, 'other': 10})
        self.assertEqual(result['total_bytes'], 70)
        self.assertEqual(result['metric'], 'pss')

    def test_other_project_management_process_is_not_counted_as_this_scheduler(self):
        process = self.process(1, 'python3', ['python3', 'manage.py', 'runapscheduler'], cwd=Path(settings.BASE_DIR) / 'other')
        self.assertEqual(self.collect([process])['groups']['other'], 10)

    def test_rss_fallback_applies_to_the_entire_sample(self):
        processes = [self.process(1, 'uwsgi'), self.process(2, 'mysqld')]
        result = self.collect(processes, platform='win32')
        self.assertEqual(result['metric'], 'rss')
        self.assertEqual(result['total_bytes'], 200)
        for process in processes:
            process.memory_full_info.assert_not_called()

    def test_exited_process_is_skipped(self):
        gone = self.process(1, 'uwsgi')
        gone.memory_full_info.side_effect = psutil.NoSuchProcess(1)
        self.assertEqual(self.collect([gone, self.process(2, 'uwsgi')])['total_bytes'], 10)

    def test_permission_denied_never_publishes_a_partial_total(self):
        denied = self.process(1, 'mysqld')
        denied.memory_full_info.side_effect = psutil.AccessDenied(1)
        with self.assertRaises(server_metrics.CollectionError) as caught:
            self.collect([denied, self.process(2, 'uwsgi')])
        self.assertEqual(caught.exception.reason, 'permission_denied')
        self.assertEqual(caught.exception.unreadable_processes, 1)

    def test_linux_does_not_mix_rss_into_pss(self):
        process = self.process(1, 'uwsgi')
        process.memory_full_info.return_value = SimpleNamespace(rss=100)
        with self.assertRaises(server_metrics.CollectionError) as caught:
            self.collect([process])
        self.assertEqual(caught.exception.reason, 'unsupported_metric')

    def test_process_count_and_time_budgets(self):
        with patch.object(server_metrics, 'MAX_PROCESSES', 1), self.assertRaises(server_metrics.CollectionError) as caught:
            self.collect([self.process(1, 'uwsgi'), self.process(2, 'uwsgi')])
        self.assertEqual(caught.exception.reason, 'budget_exceeded')
        with self.assertRaises(server_metrics.CollectionError) as caught:
            self.collect([self.process(1, 'uwsgi')], deadline=0)
        self.assertEqual(caught.exception.reason, 'budget_exceeded')

    def test_container_scope_is_not_reported_as_complete_host_memory(self):
        with patch.object(server_metrics, '_is_containerized', return_value=True), self.assertRaises(server_metrics.CollectionError) as caught:
            server_metrics.collect_process_memory(settings.BASE_DIR, float('inf'))
        self.assertEqual(caught.exception.reason, 'unsupported_scope')


class RedisMemoryTests(SimpleTestCase):
    NON_MINIGAME_RANKING_KEYS = 69

    def redis_client(self, fields=None, sizes=None, total=1000):
        client = MagicMock()
        client.hkeys.return_value = [b'std:b:4', b'nf:e:381'] if fields is None else fields
        client.info.return_value = {'used_memory': total}
        sizes = sizes or {}
        pending = []
        pipe = client.pipeline.return_value.__enter__.return_value
        pipe.memory_usage.side_effect = lambda key, samples: pending.append(key)

        def execute():
            values = [sizes.get(key) for key in pending]
            pending.clear()
            return values

        pipe.execute.side_effect = execute
        return client, pipe

    def collect(self, client, players=(7, 8), deadline=float('inf')):
        with patch.object(monitor_cache, 'get_redis_connection', return_value=client):
            return monitor_cache.collect_redis_memory(iter(players), deadline)

    def test_only_known_keys_are_measured_and_categories_reconcile(self):
        sizes = {
            'speedranking:pb:counts': 10, 'speedranking:pb:std:b:4': 20, 'speedranking:pb:nf:e:381': 30,
            'speedranking:pb:player:7': 40, 'speedranking:saolei:records': 50,
            'customranking:pluck:c8_8_40:detail': 60, 'tournament:user:score_current': 70, 'newest_queue': 80,
            'speedranking:top:records': 90, 'speedranking:top:anchors': 10,
            'effranking:thrp:records': 10, 'effranking:thrp:b': 20, 'effranking:thrp:i': 30,
            'effranking:thrp:e': 40, 'effranking:thrp:sum': 50,
            'minigame:rank:v1:left-click-b-50-v1': 11, 'minigame:detail:v1:left-click-b-50-v1': 12,
            'minigame:ready:v1:left-click-b-50-v1': 1,
            'minigame:rank:v1:multi-touch-e-87.5-v1': 13, 'minigame:detail:v1:multi-touch-e-87.5-v1': 14,
            'minigame:ready:v1:multi-touch-e-87.5-v1': 1,
        }
        client, pipe = self.redis_client(sizes=sizes)
        result = self.collect(client, players=(7, 8, 7))
        measured = Counter(call.args[0] for call in pipe.memory_usage.call_args_list)
        self.assertTrue(all(count == 1 for count in measured.values()))
        self.assertEqual(len([key for key in measured if not key.startswith('speedranking:pb:') and key != 'newest_queue']), self.NON_MINIGAME_RANKING_KEYS + 3 * len(RANKINGS))
        self.assertEqual(result['groups']['pb_rankings'], 100)
        self.assertEqual(result['groups']['other_rankings'], 482)
        self.assertEqual(len([key for key in measured if key.startswith('minigame:')]), 3 * len(RANKINGS))
        self.assertEqual(result['groups']['latest_videos'], 80)
        self.assertEqual(sum(result['groups'].values()), result['total_bytes'])
        self.assertNotIn('freeze_queue', measured)
        self.assertNotIn('review_queue', measured)
        for call in pipe.memory_usage.call_args_list:
            self.assertEqual(call.kwargs, {'samples': 5})
        client.pipeline.assert_called_with(transaction=False)
        for method in ('scan', 'scan_iter', 'keys', 'zrange', 'zscan_iter'):
            getattr(client, method).assert_not_called()

    def test_missing_keys_are_zero_and_all_other_memory_is_a_residual(self):
        client, _ = self.redis_client()
        result = self.collect(client)
        self.assertEqual(result['groups'], {'pb_rankings': 0, 'other_rankings': 0, 'latest_videos': 0, 'other': 1000})

    def test_missing_or_invalid_metadata_is_unavailable(self):
        for fields in ([], [b'bad:b:1'], [b'std:b:01'], [b'nf:unknown:1'], [b'\xff']):
            with self.subTest(fields=fields), self.assertRaises(server_metrics.CollectionError) as caught:
                client, _ = self.redis_client(fields=fields)
                self.collect(client)
            self.assertEqual(caught.exception.reason, 'metadata_unavailable')

    def test_sampling_inconsistency_is_not_clamped_into_a_chart(self):
        client, _ = self.redis_client(sizes={'newest_queue': 1001})
        with self.assertRaises(server_metrics.CollectionError) as caught:
            self.collect(client)
        self.assertEqual(caught.exception.reason, 'inconsistent_snapshot')

    def test_known_key_and_time_budgets_do_not_publish_partial_results(self):
        client, _ = self.redis_client()
        with patch.object(monitor_cache, 'MAX_MEMORY_KEYS', 3), self.assertRaises(server_metrics.CollectionError) as caught:
            self.collect(client)
        self.assertEqual(caught.exception.reason, 'budget_exceeded')
        with self.assertRaises(server_metrics.CollectionError) as caught:
            self.collect(client, deadline=0)
        self.assertEqual(caught.exception.reason, 'budget_exceeded')

    def test_large_user_list_uses_bounded_pipelines(self):
        client, pipe = self.redis_client()
        players = range(1, 251)
        self.collect(client, players=players)
        pb_keys = 1 + len(client.hkeys.return_value) + len(players)
        other_ranking_keys = self.NON_MINIGAME_RANKING_KEYS + 3 * len(RANKINGS)
        expected_keys = pb_keys + other_ranking_keys + 1  # Latest-video queue.
        self.assertEqual(pipe.memory_usage.call_count, expected_keys)
        self.assertEqual(pipe.execute.call_count, ceil(expected_keys / monitor_cache.MEMORY_BATCH_SIZE))


class MemoryCollectionTests(SimpleTestCase):
    def setUp(self):
        scope = patch.object(services, '_check_local_services')
        scope.start()
        self.addCleanup(scope.stop)

    def test_permission_failure_does_not_hide_redis(self):
        with (
            patch.object(services, 'collect_process_memory', side_effect=server_metrics.CollectionError('permission_denied', 2)),
            patch.object(services, 'collect_redis_memory', return_value=ready_redis()),
        ):
            data = services.get_memory_usage()
        self.assertEqual(data['memory']['status'], 'unavailable')
        self.assertEqual(data['memory']['reason'], 'permission_denied')
        self.assertIsNone(data['memory']['groups'])
        self.assertEqual(data['memory']['unreadable_processes'], 2)
        self.assertEqual(data['redis']['status'], 'ready')

    def test_redis_failure_does_not_hide_process_memory_or_leak_exceptions(self):
        with (
            patch.object(services, 'collect_process_memory', return_value=ready_process()),
            patch.object(services, 'collect_redis_memory', side_effect=RedisConnectionError('secret connection details')),
        ):
            data = services.get_memory_usage()
        self.assertEqual(data['memory']['status'], 'ready')
        self.assertEqual(data['redis']['reason'], 'redis_unavailable')
        self.assertNotIn('secret', str(data))

    def test_player_ids_are_read_in_bounded_primary_key_batches(self):
        with patch.object(services.UserProfile, 'objects') as objects:
            query = objects.filter.return_value.order_by.return_value.values_list.return_value
            query.__getitem__.side_effect = [[1, 3], [9], []]
            self.assertEqual(list(services._player_ids(float('inf'))), [1, 3, 9])
        self.assertEqual([call.kwargs for call in objects.filter.call_args_list], [{'pk__gt': 0}, {'pk__gt': 3}, {'pk__gt': 9}])


class LocalServicesTests(SimpleTestCase):
    def test_remote_service_configuration_is_not_reported_as_local_memory(self):
        with override_settings(CACHES={**settings.CACHES, 'saolei_website': {'LOCATION': 'redis://remote.example:6379/0'}}):
            with self.assertRaises(server_metrics.CollectionError) as caught:
                services._check_local_services()
        self.assertEqual(caught.exception.reason, 'unsupported_scope')
