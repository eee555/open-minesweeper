from io import StringIO
from unittest.mock import call, MagicMock, patch

from django.core.management import call_command, CommandError
from django.db import OperationalError
from django.test import SimpleTestCase

from utils.exceptions import ExceptionToResponse
from .models import VideoModel
from .utils import VideoParseError
from .view_utils import refresh_video


class RefreshVideosCommandTests(SimpleTestCase):
    def setUp(self):
        manager_patch = patch('videomanager.management.commands.refresh_videos.VideoModel.objects')
        self.manager = manager_patch.start()
        self.addCleanup(manager_patch.stop)
        refresh_patch = patch('videomanager.management.commands.refresh_videos.refresh_video')
        self.refresh = refresh_patch.start()
        self.addCleanup(refresh_patch.stop)
        atomic_patch = patch('videomanager.management.commands.refresh_videos.transaction.atomic')
        self.atomic = atomic_patch.start()
        self.addCleanup(atomic_patch.stop)
        self.videos = [
            VideoModel(pk=1, state='c', level='e', mode='00'),
            VideoModel(pk=2, state='b', level='c8_8_40', mode='10', ongoing_tournament=True),
        ]
        self.queryset = self.manager.order_by.return_value
        self.queryset.values_list.return_value.iterator.return_value = iter(video.pk for video in self.videos)
        self.manager.select_for_update.return_value.get.side_effect = lambda pk: next(video for video in self.videos if video.pk == pk)

    def test_id_range_filters_are_optional_and_end_is_exclusive(self):
        queryset = self.queryset
        for options, bounds, selected in (
            ({'start': 2}, {'pk__gte': 2}, self.videos[1:]),
            ({'end': 2}, {'pk__lt': 2}, self.videos[:1]),
            ({'start': 2, 'end': 3}, {'pk__gte': 2, 'pk__lt': 3}, self.videos[1:]),
            ({'start': 2, 'end': 2}, {'pk__gte': 2, 'pk__lt': 2}, []),
        ):
            with self.subTest(options=options):
                queryset.filter.reset_mock()
                queryset.filter.return_value.values_list.return_value.iterator.return_value = iter(video.pk for video in selected)
                self.refresh.reset_mock()

                call_command('refresh_videos', stdout=StringIO(), **options)

                queryset.filter.assert_called_once_with(**bounds)
                self.assertEqual(self.refresh.call_args_list, [call(video, skip_pluck=False) for video in selected])

    def test_skip_pluck_is_forwarded_to_refresh_video(self):
        call_command('refresh_videos', skip_pluck=True, stdout=StringIO())

        self.assertEqual(self.refresh.call_args_list, [call(video, skip_pluck=True) for video in self.videos])

    def test_progress_counts_parse_failures_and_reports_current_id(self):
        self.videos.append(VideoModel(pk=5))
        self.queryset.values_list.return_value.iterator.return_value = iter(video.pk for video in self.videos)
        self.refresh.side_effect = [VideoParseError('parse failed'), None, None]
        output = StringIO()

        call_command('refresh_videos', step=2, stdout=output, stderr=StringIO())

        self.assertEqual(output.getvalue().splitlines(), [
            '已处理 2 条录像，已刷新 1 条，跳过 1 条，当前录像 ID：2',
            '已刷新 2 条录像，跳过 1 条解析失败的录像',
        ])

    def test_rejects_invalid_ranges_and_progress_intervals_before_refresh(self):
        for options in ({'start': -1}, {'end': -1}, {'start': 2, 'end': 1}, {'step': 0}, {'step': -1}):
            with self.subTest(options=options), self.assertRaises(CommandError):
                call_command('refresh_videos', stdout=StringIO(), **options)
        self.manager.order_by.assert_not_called()
        self.atomic.assert_not_called()
        self.refresh.assert_not_called()

    def test_refreshes_each_instance_without_filtering_or_bulk_updates(self):
        output = StringIO()

        call_command('refresh_videos', stdout=output)

        self.manager.order_by.assert_called_once_with('pk')
        self.queryset.values_list.assert_called_once_with('pk', flat=True)
        self.assertEqual(self.manager.select_for_update.call_count, len(self.videos))
        self.assertEqual(self.manager.select_for_update.return_value.get.call_args_list, [call(pk=video.pk) for video in self.videos])
        self.assertEqual(self.atomic.call_count, len(self.videos))
        self.assertEqual(self.refresh.call_args_list, [call(video, skip_pluck=False) for video in self.videos])
        self.manager.filter.assert_not_called()
        self.manager.update.assert_not_called()
        self.manager.bulk_update.assert_not_called()
        self.assertIn('2', output.getvalue())

    def test_parse_failure_is_skipped_and_later_videos_are_refreshed(self):
        self.refresh.side_effect = [VideoParseError('parse failed'), None]
        output = StringIO()
        errors = StringIO()

        call_command('refresh_videos', stdout=output, stderr=errors)

        self.assertEqual(self.refresh.call_args_list, [call(video, skip_pluck=False) for video in self.videos])
        self.assertIn('录像#1解析失败，已跳过：parse failed', errors.getvalue())
        self.assertIn('已刷新 1 条录像，跳过 1 条', output.getvalue())

    def test_database_and_unclassified_errors_stop_refresh(self):
        for error in (OperationalError('connection lost'), ValueError('save failed')):
            with self.subTest(error=error):
                self.queryset.values_list.return_value.iterator.return_value = iter(video.pk for video in self.videos)
                self.refresh.reset_mock()
                self.refresh.side_effect = error

                with self.assertRaisesMessage(CommandError, f'录像#1刷新失败，已完成 0 条：{error}'):
                    call_command('refresh_videos', stdout=StringIO())
                self.refresh.assert_called_once_with(self.videos[0], skip_pluck=False)

    def test_locks_and_refreshes_inside_each_independent_transaction(self):
        events = []
        self.atomic.return_value.__enter__.side_effect = lambda: events.append('enter')
        self.atomic.return_value.__exit__.side_effect = lambda *args: events.append('exit') or False

        def get_locked_video(pk):
            events.append(('lock', pk))
            return VideoModel(pk=pk, state='b')

        self.manager.select_for_update.return_value.get.side_effect = get_locked_video
        self.refresh.side_effect = lambda video, **kwargs: events.append(('refresh', video.pk, video.state))

        call_command('refresh_videos', stdout=StringIO())

        self.assertEqual(events, [
            'enter', ('lock', 1), ('refresh', 1, 'b'), 'exit',
            'enter', ('lock', 2), ('refresh', 2, 'b'), 'exit',
        ])

    def test_parse_failure_exits_transaction_before_continuing(self):
        error = VideoParseError('parse failed')
        self.refresh.side_effect = [error, None]

        call_command('refresh_videos', stdout=StringIO(), stderr=StringIO())

        self.assertEqual(self.atomic.return_value.__exit__.call_args_list, [
            call(VideoParseError, error, error.__traceback__),
            call(None, None, None),
        ])


class RefreshVideoSkipPluckTests(SimpleTestCase):
    def test_skip_pluck_keeps_existing_value_and_skips_expensive_analysis(self):
        from types import SimpleNamespace

        video = MagicMock()
        video.pluck = 3.5
        video.file.name = 'a.evf'
        video.file.size = 0
        video.compression_format = 0
        video.video.identifier = ''
        video.video.tournament_identifier = []
        video.player.userms.identifiers = []

        fields = [
            'level', 'mode', 'software', 'version', 'end_time', 'timems', 'bv',
            'left', 'right', 'double', 'left_ce', 'right_ce', 'double_ce',
            'path', 'cpath', 'epath', 'flag', 'op', 'isl', 'board',
            'cell0', 'cell1', 'cell2', 'cell3', 'cell4',
            'cell5', 'cell6', 'cell7', 'cell8',
        ]
        values = {field: getattr(video, field) for field in fields}
        parser = SimpleNamespace(**values, pluck=None, identifier='', tournament_identifier=[])

        with patch('videomanager.view_utils.MSVideoParser', return_value=parser) as parser_class:
            refresh_video(video, skip_pluck=True)

        parser_class.assert_called_once_with(video.file, skip_pluck=True)
        video.save.assert_called_once()
        self.assertNotIn('pluck', video.save.call_args.kwargs['update_fields'])
        self.assertEqual(video.pluck, 3.5)


class RefreshVideoParseErrorTests(SimpleTestCase):
    def test_wraps_only_known_parser_errors_before_saving(self):
        for error in (ValueError('invalid data'), RuntimeError('analysis failed'), EOFError('truncated'), OverflowError('invalid timestamp'), ExceptionToResponse('file', 'type')):
            with self.subTest(error=error), patch('videomanager.view_utils.MSVideoParser', side_effect=error), patch.object(VideoModel, 'save') as save:
                with self.assertRaises(VideoParseError) as raised:
                    refresh_video(VideoModel(pk=1))
                self.assertIs(raised.exception.__cause__, error)
                save.assert_not_called()

    def test_serious_parser_stage_errors_are_not_wrapped(self):
        for error in (OperationalError('connection lost'), OSError('disk error'), MemoryError(), KeyboardInterrupt()):
            with self.subTest(error=error), patch('videomanager.view_utils.MSVideoParser', side_effect=error):
                with self.assertRaises(type(error)) as raised:
                    refresh_video(VideoModel(pk=1))
                self.assertIs(raised.exception, error)
