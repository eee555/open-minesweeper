from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError

from utils.exceptions import ExceptionToResponse
from utils.parser import MSVideoParser
from videomanager.files import original_file
from videomanager.models import VideoModel


class Command(BaseCommand):
    help = '读取原始录像文件，分批回填尚未设置的雷分布位图'

    def add_arguments(self, parser):
        parser.add_argument('--start', type=int, default=0, help='起始录像 ID，包含此 ID，默认 0')
        parser.add_argument('--end', type=int, help='结束录像 ID，不包含此 ID，默认不限制')
        parser.add_argument('--batch-size', type=int, default=1000, help='每批读取的录像记录数，默认 1000')
        parser.add_argument('--step', type=int, default=100, help='每处理多少条录像输出一次进度，默认 100')

    def handle(self, *args, **options):
        start, end = options['start'], options['end']
        batch_size, step = options['batch_size'], options['step']
        if start < 0 or (end is not None and end < start):
            raise CommandError('start 必须非负，end 必须大于或等于 start')
        if batch_size <= 0 or step <= 0:
            raise CommandError('batch-size 和 step 必须为正整数')

        videos = VideoModel.objects.filter(board__isnull=True, pk__gte=start)
        if end is not None:
            videos = videos.filter(pk__lt=end)
        videos = videos.order_by('pk')
        processed = updated = failed = 0
        last_id = start - 1

        def report_progress():
            current_id = last_id if processed else '-'
            self.stdout.write(f'进度 {processed}，已回填 {updated}，失败 {failed}，当前录像 ID：{current_id}')
            self.stdout.flush()

        report_progress()
        while batch := list(videos.filter(pk__gt=last_id).values_list('pk', 'file', 'compression_format', 'original_filename')[:batch_size]):
            for video_id, file_name, compression_format, original_filename in batch:
                try:
                    if not file_name:
                        raise FileNotFoundError
                    replay = original_file(file_name, compression_format, original_filename) if compression_format else default_storage.open(file_name, 'rb')
                    with replay:
                        parser = MSVideoParser(replay, isolate=True)
                except (FileNotFoundError, ExceptionToResponse) as exc:
                    failed += 1
                    self.stderr.write(self.style.WARNING(f'录像#{video_id}解析失败，已跳过，board 保持为空：{exc}'))
                except OSError as exc:
                    raise CommandError(f'录像#{video_id}读取失败，已回填 {updated} 条：{exc.strerror or type(exc).__name__}') from exc
                else:
                    updated += VideoModel.objects.filter(pk=video_id, board__isnull=True).update(board=parser.board)
                processed += 1
                last_id = video_id
                if processed % step == 0:
                    report_progress()

        if processed % step:
            report_progress()
        style = self.style.WARNING if failed else self.style.SUCCESS
        self.stdout.write(style(f'回填完成：处理 {processed} 条，已回填 {updated} 条，失败 {failed} 条'))
