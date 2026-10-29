from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Max, Q

from videomanager.models import VideoModel
from videomanager.utils import calculate_original_hash


class Command(BaseCommand):
    help = '读取原始录像文件，回填尚未设置的 96 位内容哈希并显示进度'

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

        missing_hash = Q(original_hash__isnull=True) | Q(original_hash='')
        videos = VideoModel.objects.filter(missing_hash, pk__gte=start)
        if end is not None:
            videos = videos.filter(pk__lt=end)
        scope = videos.aggregate(total=Count('pk'), last_id=Max('pk'))
        total = scope['total']
        if not total:
            self.stdout.write(self.style.SUCCESS('没有需要回填哈希的录像（0/0，100.0%）'))
            return
        videos = videos.filter(pk__lte=scope['last_id']).order_by('pk')
        processed = updated = failed = skipped = 0
        last_id = start - 1

        def report_progress():
            current_id = last_id if processed else '-'
            self.stdout.write(f'进度 {processed}/{total}（{processed / total:.1%}），已回填 {updated}，失败 {failed}，跳过 {skipped}，当前录像 ID：{current_id}')
            self.stdout.flush()

        report_progress()
        while batch := list(videos.filter(pk__gt=last_id).values_list('pk', 'file')[:batch_size]):
            for video_id, file_name in batch:
                try:
                    if not file_name:
                        raise FileNotFoundError
                    with default_storage.open(file_name, 'rb') as replay_file:
                        original_hash = calculate_original_hash(replay_file)
                except FileNotFoundError:
                    failed += 1
                    self.stderr.write(self.style.WARNING(f'录像#{video_id}文件不存在，已跳过，哈希保持为空'))
                except OSError as exc:
                    raise CommandError(f'录像#{video_id}读取失败，已回填 {updated} 条：{exc.strerror or type(exc).__name__}') from exc
                else:
                    changed = VideoModel.objects.filter(missing_hash, pk=video_id, file=file_name).update(original_hash=original_hash)
                    updated += changed
                    skipped += int(not changed)
                processed += 1
                last_id = video_id
                if processed % step == 0:
                    report_progress()

        if processed % step:
            report_progress()
        style = self.style.WARNING if failed else self.style.SUCCESS
        self.stdout.write(style(f'回填完成：处理 {processed} 条，已回填 {updated} 条，失败 {failed} 条，跳过 {skipped} 条'))
