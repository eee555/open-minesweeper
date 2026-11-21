from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from utils.ranking_lock import ranking_access
from videomanager.models import VideoModel
from videomanager.utils import VideoParseError
from videomanager.view_utils import refresh_video


class Command(BaseCommand):
    help = '按录像 ID 范围逐条重新解析录像，通过实例保存触发信号接收器'

    def add_arguments(self, parser):
        parser.add_argument('--start', type=int, default=0, help='起始录像 ID，包含此 ID，默认 0')
        parser.add_argument('--end', type=int, help='结束录像 ID，不包含此 ID，默认不限制')
        parser.add_argument('--step', type=int, default=100, help='每处理多少条录像输出一次进度，默认 100')
        parser.add_argument('--skip-pluck', action='store_true', help='跳过 pluck 计算，保留原有 pluck 值')

    def handle(self, *args, **options):
        start, end, step = options['start'], options['end'], options['step']
        skip_pluck = options['skip_pluck']
        if start < 0 or (end is not None and end < start):
            raise CommandError('start 必须非负，end 必须大于或等于 start')
        if step <= 0:
            raise CommandError('step 必须为正整数')
        refreshed = 0
        skipped = 0
        videos = VideoModel.objects.order_by('pk')
        bounds = {}
        if start:
            bounds['pk__gte'] = start
        if end is not None:
            bounds['pk__lt'] = end
        if bounds:
            videos = videos.filter(**bounds)
        for processed, video_id in enumerate(videos.values_list('pk', flat=True).iterator(), start=1):
            try:
                with ranking_access(operation='refresh_videos'), transaction.atomic():
                    video = VideoModel.objects.select_for_update().get(pk=video_id)
                    refresh_video(video, skip_pluck=skip_pluck)
            except VideoParseError as exc:
                skipped += 1
                self.stderr.write(self.style.WARNING(f'录像#{video_id}解析失败，已跳过：{exc}'))
            except Exception as exc:
                raise CommandError(f'录像#{video_id}刷新失败，已完成 {refreshed} 条：{exc}') from exc
            else:
                refreshed += 1
            if processed % step == 0:
                self.stdout.write(f'已处理 {processed} 条录像，已刷新 {refreshed} 条，跳过 {skipped} 条，当前录像 ID：{video_id}')
                self.stdout.flush()
        self.stdout.write(self.style.SUCCESS(f'已刷新 {refreshed} 条录像，跳过 {skipped} 条解析失败的录像'))
