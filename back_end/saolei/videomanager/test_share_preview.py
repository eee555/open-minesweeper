from concurrent.futures import ThreadPoolExecutor
from io import BytesIO, StringIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import ANY, Mock, patch

from django.conf import settings
from django.core.cache import caches
from django.core.management import call_command
from django.db import transaction
from django.test import override_settings, SimpleTestCase, TestCase
from PIL import Image
from redis.exceptions import ConnectionError as RedisConnectionError

from config.text_choices import MS_TextChoices
from msuser.models import UserMS
from userprofile.models import UserProfile
from utils.parser import pack_board_bitmap
from .cache import reserve_share_preview_cleanup, SHARE_PREVIEW_COUNT_KEY, SHARE_PREVIEW_PENDING_KEY
from .config import SHARE_PREVIEW_MAX_COLUMNS, SHARE_PREVIEW_MAX_ROWS
from .models import ExpandVideoModel, VideoModel
from .share_preview import completed_cells, ensure_preview, PLACEHOLDER_FILENAME, preview_board, preview_directory, prune_previews, render_preview, write_preview
from .tasks import enqueue_share_preview_cleanup, task_cleanup_share_previews


def bitmap_for(rows, columns, mines):
    return pack_board_bitmap([
        [-1 if row * columns + column < mines else 0 for column in range(columns)]
        for row in range(rows)
    ])


class PreviewFilesTests(SimpleTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        configuration = override_settings(MEDIA_ROOT=directory.name)
        configuration.enable()
        self.addCleanup(configuration.disable)

    def test_lsb_row_major_neighbor_counts_and_rendered_mines(self):
        board = preview_board('c2_5_2', bytes([1, 2]))
        self.assertEqual(completed_cells(board), [[-1, 1, 0, 1, 1], [1, 1, 0, 1, -1]])
        png = render_preview(board)
        self.assertTrue(png.startswith(b'\x89PNG\r\n\x1a\n'))
        with Image.open(BytesIO(png)) as image:
            self.assertEqual(image.size, (120, 48))
            self.assertEqual(image.mode, 'P')
            self.assertLessEqual(len(image.getcolors()), 16)
            rgb = image.convert('RGB')
            self.assertEqual(rgb.getpixel((13, 13)), (0, 0, 0))
            self.assertEqual(rgb.getpixel((109, 37)), (0, 0, 0))

    def test_size_limits_bitmap_length_padding_and_mine_count(self):
        supported = [preview_board(level, None) for level in MS_TextChoices.Level.values]
        self.assertEqual(max(board.rows for board in supported), SHARE_PREVIEW_MAX_ROWS)
        self.assertEqual(max(board.columns for board in supported), SHARE_PREVIEW_MAX_COLUMNS)
        board = preview_board('c24_30_200', bitmap_for(24, 30, 200))
        with Image.open(BytesIO(render_preview(board))) as image:
            self.assertEqual(image.size, (720, 576))
        for level, bitmap in (
            ('c25_30_200', bitmap_for(25, 30, 200)), ('c24_31_200', bitmap_for(24, 31, 200)),
            ('c0_3_1', None), ('c1_1_1', None), ('c2_3_0', None), ('c2_3_6', None), ('c999999_1_1', None),
            ('unknown', None), ('b', b''), ('b', bytes(8)), ('c1_3_1', b'\x81'),
        ):
            with self.subTest(level=level, bitmap=bitmap), self.assertRaises(ValueError):
                preview_board(level, bitmap)

    def test_cache_hit_touches_mtime_and_content_identity_changes(self):
        board = preview_board('b', bitmap_for(8, 8, 10))
        filename, created = ensure_preview(11, board)
        self.assertTrue(created)
        path = preview_directory() / filename
        original = path.read_bytes()
        os.utime(path, (1, 1))
        with patch('videomanager.share_preview.render_preview', side_effect=AssertionError('Cache hit rendered again')):
            self.assertEqual(ensure_preview(11, board), (filename, False))
        self.assertGreater(path.stat().st_mtime, 1)
        self.assertEqual(path.read_bytes(), original)
        changed = preview_board('b', bytes([0, 255, 3, 0, 0, 0, 0, 0]))
        self.assertNotEqual(board.filename(11), changed.filename(11))
        changed_filename, _ = ensure_preview(11, changed)
        write_preview(path, original)
        self.assertTrue((preview_directory() / changed_filename).exists())
        self.assertEqual(changed.filename(11), changed_filename)

    def test_atomic_write_failure_cleans_temporary_without_replacing_existing_file(self):
        path = preview_directory() / 'existing.png'
        path.parent.mkdir()
        path.write_bytes(b'original')
        with patch('videomanager.share_preview.os.replace', side_effect=PermissionError('denied')), self.assertRaises(PermissionError):
            write_preview(path, b'new')
        self.assertEqual(path.read_bytes(), b'original')
        self.assertEqual(list(path.parent.glob('*.tmp')), [])

    def test_concurrent_writers_publish_complete_images_with_unique_temporary_files(self):
        path = preview_directory() / 'shared.png'
        png = render_preview(preview_board('b', bitmap_for(8, 8, 10)))
        barrier = Barrier(2)
        temporary_names = []
        replace = os.replace

        def publish(source, destination):
            temporary_names.append(source)
            barrier.wait(timeout=5)
            replace(source, destination)

        with patch('videomanager.share_preview.os.replace', side_effect=publish), ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(write_preview, path, png) for _ in range(2)]
            successes = 0
            for future in futures:
                try:
                    future.result(timeout=10)
                    successes += 1
                except PermissionError:
                    # Windows can reject one racing replace; an occasional request failure is allowed.
                    pass
        self.assertGreater(successes, 0)
        self.assertEqual(len(set(temporary_names)), 2)
        self.assertEqual(path.read_bytes(), png)
        with Image.open(path) as image:
            image.verify()
        self.assertEqual(list(path.parent.glob('*.tmp')), [])

    def test_placeholder_preparation_and_missing_placeholder(self):
        board = preview_board('e', None)
        with self.assertRaises(FileNotFoundError):
            ensure_preview(1, board)
        call_command('prepare_share_preview', stdout=StringIO())
        self.assertEqual(ensure_preview(1, board), (PLACEHOLDER_FILENAME, False))
        self.assertEqual(ensure_preview(2, board), (PLACEHOLDER_FILENAME, False))
        with Image.open(preview_directory() / PLACEHOLDER_FILENAME) as image:
            self.assertEqual(image.size, board.image_size)

    def make_cached_files(self):
        directory = preview_directory()
        directory.mkdir()
        files = []
        for index in range(4):
            path = directory / f'{index + 1}-v{1 + index % 2}-aaaaaaaaaaaaaaaa.png'
            path.write_bytes(b'cached')
            os.utime(path, (index + 1, index + 1))
            files.append(path)
        for name in (PLACEHOLDER_FILENAME, 'unrelated.png', 'preview-test.tmp'):
            (directory / name).write_bytes(b'keep')
        (directory / '10-v1-aaaaaaaaaaaaaaaa.png').mkdir()
        return files

    @patch('videomanager.share_preview.SHARE_PREVIEW_CACHE_LIMIT', 4)
    @patch('videomanager.share_preview.SHARE_PREVIEW_CACHE_TARGET', 2)
    def test_background_prunes_oldest_images_across_versions_and_recounts(self):
        files = self.make_cached_files()
        with patch('videomanager.cache.cache') as redis:
            result = task_cleanup_share_previews.call()
        self.assertEqual(result, {'before': 4, 'deleted': 2, 'remaining': 2})
        redis.set.assert_called_once_with(SHARE_PREVIEW_COUNT_KEY, 2)
        self.assertEqual([path.exists() for path in files], [False, False, True, True])
        self.assertTrue((preview_directory() / PLACEHOLDER_FILENAME).is_file())
        self.assertTrue((preview_directory() / 'preview-test.tmp').is_file())
        self.assertTrue((preview_directory() / '10-v1-aaaaaaaaaaaaaaaa.png').is_dir())

    def test_count_only_and_management_command_never_prune_synchronously(self):
        files = self.make_cached_files()
        with patch('videomanager.cache.cache') as redis:
            self.assertEqual(task_cleanup_share_previews.call(count_only=True)['remaining'], 4)
        redis.set.assert_called_once_with(SHARE_PREVIEW_COUNT_KEY, 4)
        with patch('videomanager.management.commands.cleanup_share_previews.task_cleanup_share_previews') as task:
            task.enqueue.return_value = Mock(id='task-id')
            output = StringIO()
            call_command('cleanup_share_previews', count_only=True, stdout=output)
        task.enqueue.assert_called_once_with(count_only=True)
        self.assertIn('task-id', output.getvalue())
        self.assertTrue(all(path.exists() for path in files))

    @patch('videomanager.share_preview.SHARE_PREVIEW_CACHE_LIMIT', 4)
    @patch('videomanager.share_preview.SHARE_PREVIEW_CACHE_TARGET', 2)
    def test_cleanup_ignores_disappearing_and_inaccessible_entries(self):
        files = self.make_cached_files()
        unlink = Path.unlink

        def race(path, *args, **kwargs):
            if path == files[0]:
                raise PermissionError('denied')
            if path == files[1]:
                unlink(path)
                raise FileNotFoundError('already gone')
            return unlink(path, *args, **kwargs)

        with patch.object(Path, 'unlink', race), self.assertLogs('videomanager', level='ERROR'):
            result = prune_previews()
        self.assertEqual(result['remaining'], 1)
        self.assertTrue(files[0].exists())

    def test_cleanup_does_not_follow_symlinks(self):
        outside = Path(settings.MEDIA_ROOT) / 'outside.png'
        outside.write_bytes(b'keep')
        preview_directory().mkdir()
        link = preview_directory() / '1-v1-aaaaaaaaaaaaaaaa.png'
        try:
            link.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f'Symlinks unavailable: {exc}')
        self.assertEqual(prune_previews()['before'], 0)
        self.assertEqual(outside.read_bytes(), b'keep')


class PreviewQueueTests(SimpleTestCase):
    def test_count_threshold_missing_and_corrupt_counts_request_calibration(self):
        for count in (None, b'-2', b'broken', b'20000'):
            with self.subTest(count=count), patch('videomanager.cache.cache') as redis:
                redis.get.return_value = count
                redis.set.return_value = True
                self.assertIsInstance(reserve_share_preview_cleanup(), str)
                redis.set.assert_called_once_with(SHARE_PREVIEW_PENDING_KEY, ANY, nx=True, ex=300)
        with patch('videomanager.cache.cache') as redis:
            redis.get.return_value = b'19999'
            redis.incr.return_value = 20000
            redis.set.return_value = True
            self.assertIsInstance(reserve_share_preview_cleanup(created=True), str)
            redis.incr.assert_called_once_with(SHARE_PREVIEW_COUNT_KEY)

    def test_redis_failure_does_not_escape_into_image_response(self):
        with patch('videomanager.cache.cache') as redis, self.assertLogs('videomanager', level='ERROR'):
            redis.get.side_effect = RedisConnectionError('offline')
            self.assertIsNone(reserve_share_preview_cleanup(created=True))

    def test_enqueue_failure_releases_marker_and_task_failure_also_releases(self):
        with patch('videomanager.tasks.reserve_share_preview_cleanup', return_value='token'), patch('videomanager.tasks.release_share_preview_cleanup') as release, patch('videomanager.tasks.task_cleanup_share_previews') as task, self.assertLogs('videomanager', level='ERROR'):
            task.enqueue.side_effect = RuntimeError('database offline')
            enqueue_share_preview_cleanup(created=True)
        release.assert_called_once_with('token')
        with patch('videomanager.tasks.prune_previews', side_effect=PermissionError('denied')), patch('videomanager.tasks.release_share_preview_cleanup') as release, self.assertRaises(PermissionError):
            task_cleanup_share_previews.call(token='token')
        release.assert_called_once_with('token')


@override_settings(RATELIMIT_ENABLE=False)
class PreviewApiTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        configuration = override_settings(MEDIA_ROOT=directory.name)
        configuration.enable()
        self.addCleanup(configuration.disable)
        for target in ('speedranking.services._sync_video', 'effranking.services._sync_video'):
            replacement = patch(target)
            replacement.start()
            self.addCleanup(replacement.stop)
        replacement = patch('videomanager.cache.cache')
        self.redis = replacement.start()
        self.addCleanup(replacement.stop)
        self.redis.get.return_value = b'0'
        self.redis.incr.return_value = 1
        self.redis.set.return_value = True
        self.user = UserProfile.objects.create_user(username='share-preview', email='share-preview@example.com', userms=UserMS.objects.create())
        self.video = VideoModel.objects.create(
            player=self.user, video=ExpandVideoModel.objects.create(identifier='Fixture'), file='share.evf',
            state='c', software='e', level='b', mode='00', bv=12, timems=1234, board=bitmap_for(8, 8, 10),
        )
        self.page_url = f'/video/{self.video.pk}'
        self.image_url = f'/api/video/share/v1/{self.video.pk}.png'

    def test_image_is_always_empty_accel_response_even_in_debug_and_never_scans(self):
        with patch('videomanager.share_preview._cached_files', side_effect=AssertionError('Request scanned directory')):
            for debug in (True, False):
                with self.subTest(debug=debug), override_settings(DEBUG=debug):
                    response = self.client.get(self.image_url)
                    self.assertEqual(response.status_code, 200, response.content)
                    self.assertEqual(response.content, b'')
                    self.assertEqual(response['Content-Type'], 'image/png')
                    self.assertIn('no-cache', response['Cache-Control'])
                    filename = preview_board(self.video.level, self.video.board).filename(self.video.pk)
                    self.assertEqual(response['X-Accel-Redirect'], f'/internal-media/thumbnail/{filename}')
        self.assertTrue((preview_directory() / filename).exists())
        self.assertFalse((preview_directory() / '.locks').exists())
        self.assertEqual(self.client.get(f'/api/video/share/v2/{self.video.pk}.png').status_code, 404)

    def test_page_escapes_metadata_uses_public_name_and_dynamic_pixel_sizes(self):
        UserProfile.objects.filter(pk=self.user.pk).update(_realname='A"><script>alert(1)</script>')
        response = self.client.get(self.page_url, HTTP_HOST='attacker.invalid')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'A&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>')
        self.assertContains(response, 'https://openms.top' + self.image_url)
        self.assertNotContains(response, 'attacker.invalid')
        self.assertContains(response, '3BV 12')
        self.assertContains(response, '1.234s')
        self.assertContains(response, 'content="0;url=/#/video/')
        for level, rows, columns, mines in (('b', 8, 8, 10), ('i', 16, 16, 40), ('e', 16, 30, 99), ('c24_30_200', 24, 30, 200)):
            with self.subTest(level=level):
                VideoModel.objects.filter(pk=self.video.pk).update(level=level, board=bitmap_for(rows, columns, mines))
                response = self.client.get(self.page_url)
                self.assertContains(response, f'property="og:image:width" content="{columns * 24}"')
                self.assertContains(response, f'property="og:image:height" content="{rows * 24}"')
        UserProfile.objects.filter(pk=self.user.pk).update(_realname='Hidden legal name', verified=True, hide_realname=True)
        self.assertNotContains(self.client.get(self.page_url), 'Hidden legal name')

    def test_owners_and_staff_cannot_share_private_states_or_unrevealed_tournaments(self):
        self.assertEqual(self.client.get(self.image_url).status_code, 200)
        for login in (False, True):
            if login:
                UserProfile.objects.filter(pk=self.user.pk).update(is_staff=True)
                self.user.refresh_from_db()
                self.client.force_login(self.user)
            for state, ongoing in (('a', False), ('b', False), ('e', False), ('c', True), ('d', True)):
                VideoModel.objects.filter(pk=self.video.pk).update(state=state, ongoing_tournament=ongoing)
                for url in (self.page_url, self.image_url):
                    with self.subTest(login=login, state=state, ongoing=ongoing, url=url):
                        response = self.client.get(url)
                        self.assertEqual(response.status_code, 404)
                        self.assertNotContains(response, 'Fixture', status_code=404)
                        self.assertNotIn('X-Accel-Redirect', response)
        VideoModel.objects.filter(pk=self.video.pk).update(state='d', ongoing_tournament=False)
        self.assertEqual(self.client.get(self.image_url).status_code, 200)

    def test_missing_invalid_and_oversized_boards_are_not_rendered(self):
        self.assertEqual(self.client.get('/video/0').status_code, 404)
        self.assertEqual(self.client.get('/api/video/share/v1/99999999999999999999999999999.png').status_code, 404)
        for level, board in (('b', b'bad'), ('c25_30_200', bitmap_for(25, 30, 200)), ('c24_31_200', bitmap_for(24, 31, 200))):
            VideoModel.objects.filter(pk=self.video.pk).update(level=level, board=board)
            for url in (self.page_url, self.image_url):
                with self.subTest(level=level, url=url), patch('videomanager.api.ensure_preview', side_effect=AssertionError('Invalid board reached renderer')):
                    self.assertEqual(self.client.get(url).status_code, 404)

    def test_placeholder_and_cache_failures_never_return_png_bytes(self):
        VideoModel.objects.filter(pk=self.video.pk).update(board=None, level='e')
        with self.assertLogs('videomanager', level='ERROR'):
            self.assertEqual(self.client.get(self.image_url).status_code, 503)
        call_command('prepare_share_preview', stdout=StringIO())
        response = self.client.get(self.image_url)
        self.assertEqual(response.content, b'')
        self.assertTrue(response['X-Accel-Redirect'].endswith('/' + PLACEHOLDER_FILENAME))
        self.assertContains(self.client.get(self.page_url), 'property="og:image:width" content="192"')
        VideoModel.objects.filter(pk=self.video.pk).update(board=self.video.board, level='b')
        with patch('videomanager.share_preview.os.replace', side_effect=PermissionError('denied')), self.assertLogs('videomanager', level='ERROR'):
            response = self.client.get(self.image_url)
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.content.startswith(b'\x89PNG'))
        self.assertNotIn('X-Accel-Redirect', response)
        self.assertEqual(list(preview_directory().glob('*.tmp')), [])

    def test_failed_usage_tracking_does_not_change_accel_response(self):
        with patch('videomanager.share_preview.os.utime', side_effect=FileNotFoundError('raced')), self.assertLogs('videomanager', level='ERROR'):
            response = self.client.get(self.image_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'')
        self.redis.get.side_effect = RedisConnectionError('offline')
        with self.assertLogs('videomanager', level='ERROR'):
            self.assertEqual(self.client.get(self.image_url).status_code, 200)

    def test_delete_removes_known_cache_only_after_commit_and_rollback_keeps_it(self):
        self.client.get(self.image_url)
        path = preview_directory() / preview_board(self.video.level, self.video.board).filename(self.video.pk)
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError), transaction.atomic():
                self.video.delete()
                raise RuntimeError('rollback')
        self.assertTrue(path.exists())
        self.video = VideoModel.objects.get(pk=int(self.page_url.rsplit('/', 1)[1]))
        with self.captureOnCommitCallbacks(execute=True):
            self.video.delete()
            self.assertTrue(path.exists())
        self.assertFalse(path.exists())
        self.redis.decr.assert_called_with(SHARE_PREVIEW_COUNT_KEY)

    @override_settings(
        RATELIMIT_ENABLE=True, RATELIMIT_USE_CACHE='share-preview-rate-tests',
        CACHES={**settings.CACHES, 'share-preview-rate-tests': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'share-preview-rate-tests'}},
    )
    def test_page_and_image_ip_limits_are_independent_and_block_requests(self):
        rate_cache = caches['share-preview-rate-tests']
        rate_cache.clear()
        self.addCleanup(rate_cache.clear)
        for url, quota in ((self.page_url, 30), (self.image_url, 60)):
            with self.subTest(url=url), patch('django_ratelimit.core.time.time', return_value=1000000000):
                for _ in range(quota):
                    self.assertEqual(self.client.get(url, REMOTE_ADDR='192.0.2.1').status_code, 200)
                self.assertEqual(self.client.get(url, REMOTE_ADDR='192.0.2.1').status_code, 429)
                self.assertEqual(self.client.get(url, REMOTE_ADDR='192.0.2.2').status_code, 200)
        with patch('django_ratelimit.core.time.time', return_value=1000000061):
            self.assertEqual(self.client.get(self.image_url, REMOTE_ADDR='192.0.2.1').status_code, 200)
