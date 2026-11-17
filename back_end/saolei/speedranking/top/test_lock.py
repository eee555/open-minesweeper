from contextvars import Context
from multiprocessing import get_context
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
from time import monotonic, sleep
from unittest import expectedFailure

from django.http import HttpResponse
from django.test import override_settings, RequestFactory, SimpleTestCase
from filelock import ReadWriteLock, Timeout

from utils.ranking_lock import ranking_access, TopRankingWriteMiddleware


def hold_lock(path, exclusive, entered, release):
    lock = ReadWriteLock(path, is_singleton=False)
    try:
        with lock.write_lock() if exclusive else lock.read_lock():
            entered.set()
            release.wait(15)
    finally:
        lock.close()


class TopLockTests(SimpleTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = str(Path(directory.name) / 'top.sqlite3')
        override = override_settings(TOP_RANKING_LOCK_PATH=self.path)
        override.enable()
        self.addCleanup(override.disable)
        self.context = get_context('spawn')

    def start_holder(self, exclusive):
        entered, release = self.context.Event(), self.context.Event()
        process = self.context.Process(target=hold_lock, args=(self.path, exclusive, entered, release))
        process.start()

        def finish():
            if process.is_alive():
                release.set()
                process.join(5)
                if process.is_alive():
                    process.terminate()
                    process.join(5)
        self.addCleanup(finish)
        return process, entered, release

    def test_parallel_shared_access_and_crashed_writer_releases_http_gate(self):
        with ranking_access():
            process, entered, release = self.start_holder(False)
            self.assertTrue(entered.wait(5), 'Another process must be allowed shared access')
            release.set()
            process.join(5)
            self.assertEqual(process.exitcode, 0)
        process, entered, release = self.start_holder(True)
        self.assertTrue(entered.wait(5))
        middleware = TopRankingWriteMiddleware(lambda request: HttpResponse('allowed'))
        request = RequestFactory().post('/api/common/uploadvideo')
        with self.assertLogs('speedranking', level='WARNING'):
            response = middleware(request)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response['Retry-After'], '1')
        self.assertJSONEqual(response.content, {'type': 'error', 'object': 'top', 'category': 'refreshing'})
        for path in ('/api/tournament/gsc/history/prepare', '/api/tournament/gsc/history/participants/123/identifier', '/api/tournament/gsc/history/participants/123/videos'):
            with self.subTest(path=path), self.assertLogs('speedranking', level='WARNING'):
                self.assertEqual(middleware(RequestFactory().post(path)).status_code, 503)
        self.assertEqual(middleware(RequestFactory().get('/api/speedranking/top/rank')).status_code, 200)
        process.terminate()
        process.join(5)
        self.assertEqual(middleware(request).status_code, 200)

    # Linux SQLite can reuse this process's shared lock despite a pending writer.
    @expectedFailure if sys.platform == 'linux' else (lambda test: test)
    def test_pending_writer_drains_shared_operations_and_background_waits(self):
        with ranking_access():
            process, entered, release = self.start_holder(True)
            probe = ReadWriteLock(self.path, is_singleton=False)
            deadline = monotonic() + 5
            blocked = False
            while monotonic() < deadline:
                try:
                    probe.acquire_read(blocking=False)
                except Timeout:
                    blocked = True
                    break
                else:
                    probe.release()
                sleep(0.02)
            probe.close()
            self.assertTrue(blocked, 'Pending exclusive acquisition must stop new readers')
            self.assertFalse(entered.is_set(), 'The existing shared operation must finish first')
            middleware = TopRankingWriteMiddleware(lambda request: HttpResponse('allowed'))
            with self.assertLogs('speedranking', level='WARNING'):
                response = Context().run(middleware, RequestFactory().post('/identifier/add/'))
            self.assertEqual(response.status_code, 503)
        self.assertTrue(entered.wait(5))
        resumed = Event()

        def background_operation():
            with ranking_access(operation='test.background'):
                resumed.set()
        thread = Thread(target=background_operation)
        thread.start()
        self.assertFalse(resumed.wait(0.1))
        release.set()
        self.assertTrue(resumed.wait(5))
        thread.join(5)
        process.join(5)
        self.assertEqual(process.exitcode, 0)
