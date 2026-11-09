"""从 DB 只取 verified 全量重建四个 zset 与 anchor；见 MEDIA_PLAN.md 第 6、10 节。"""

from django.core.management.base import BaseCommand

from media.cache import clear_rankings, MEDIA_CACHE_KEYS, rebuild_rankings
from media.services import refresh_hot_reference


class Command(BaseCommand):
    help = 'Rebuild media rankings from verified Media rows.'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=1000)
        parser.add_argument('--clear', action='store_true', help='只清空五个固定 key 与缓存锁，不重建；需暂停写操作')

    def handle(self, *args, **options):
        if options['clear']:
            clear_rankings()
            self.stdout.write(self.style.SUCCESS(f'Cleared {len(MEDIA_CACHE_KEYS)} media cache keys.'))
            return
        batch_size = options['batch_size']
        if batch_size <= 0:
            self.stderr.write('--batch-size must be positive')
            return
        count = rebuild_rankings(batch_size=batch_size)
        changed = refresh_hot_reference()
        self.stdout.write(self.style.SUCCESS(f'Rebuilt media rankings: {count} verified rows, anchor_changed={changed}.'))
