from django.core.management.base import BaseCommand, CommandError

from videomanager.tasks import task_cleanup_share_previews


class Command(BaseCommand):
    help = '入队录像分享图片清理任务；由现有单 worker 扫描文件并回写 Redis 参考计数'

    def add_arguments(self, parser):
        parser.add_argument('--count-only', action='store_true', help='只校准 Redis 计数，不删除图片')

    def handle(self, *args, **options):
        try:
            result = task_cleanup_share_previews.enqueue(count_only=options['count_only'])
        except Exception as exc:
            raise CommandError(f'Failed to enqueue share preview cleanup: {exc}') from exc
        self.stdout.write(self.style.SUCCESS(f'Queued share preview task: {result.id}'))
