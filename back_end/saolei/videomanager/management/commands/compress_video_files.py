from django.core.management.base import BaseCommand, CommandError

from videomanager.config import TARGET_COMPRESSION_FORMAT
from videomanager.models import VideoModel
from videomanager.services import compress_video_file
from videomanager.utils import pack_compression_format


class Command(BaseCommand):
    help = '按当前目标格式压缩录像文件；不重新解析录像、不刷新排行'

    def add_arguments(self, parser):
        parser.add_argument('--start', type=int, default=0, help='包含的起始录像 ID')
        parser.add_argument('--end', type=int, help='不包含的结束录像 ID')
        parser.add_argument('--batch-size', type=int, default=100)
        parser.add_argument('--retry-failed', action='store_true', help='仅重试失败录像，每条最多尝试一次')
        parser.add_argument('--dry-run', action='store_true', help='仅列出候选，不读写录像文件')

    def handle(self, *args, **options):
        start, end, batch_size = options['start'], options['end'], options['batch_size']
        if start < 0 or (end is not None and end < start) or batch_size <= 0:
            raise CommandError('start 必须非负，end 不能小于 start，batch-size 必须为正整数')
        target = TARGET_COMPRESSION_FORMAT
        candidates = VideoModel.objects.filter(pk__gte=start, compression_failed=options['retry_failed'])
        if end is not None:
            candidates = candidates.filter(pk__lt=end)
        if not options['retry_failed']:
            candidates = candidates.exclude(compression_format=pack_compression_format(*target))
        # Snapshot IDs once: failed files must not be retried forever in the same invocation.
        ids = list(candidates.values_list('pk', flat=True))
        counts = dict.fromkeys(('converted', 'failed', 'skipped'), 0)
        self.stdout.write(f'目标格式 {target}，候选 {len(ids)} 条')
        for offset in range(0, len(ids), batch_size):
            batch = ids[offset:offset + batch_size]
            videos = VideoModel.objects.filter(pk__in=batch).only('file', 'file_size', 'original_hash', 'original_filename', 'compression_format', 'compression_failed')
            for video in videos:
                if options['dry_run']:
                    self.stdout.write(f'录像#{video.pk}：{video.file.name}')
                    continue
                try:
                    status = compress_video_file(video, target=target, retry_failed=options['retry_failed'])
                except Exception as error:
                    raise CommandError(f'录像#{video.pk}转换中止；此前已完成的转换保留：{error}') from error
                counts[status] += 1
                processed = sum(counts.values())
                self.stdout.write(f'进度 {processed}/{len(ids)}，成功 {counts["converted"]}，失败 {counts["failed"]}，跳过 {counts["skipped"]}，当前 ID：{video.pk}')
                self.stdout.flush()
        self.stdout.write(self.style.SUCCESS(f'完成：{counts}'))
