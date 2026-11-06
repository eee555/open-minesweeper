from django.core.management.base import BaseCommand, CommandError

from speedranking.strict_ng.services import rebuild_strict_ng_ranks
from speedranking.strict_ng.utils import RANKING_NAMES


class Command(BaseCommand):
    help = '从 VideoModel 重建强无猜竞速榜，完成后原子替换 Redis 榜单'

    def add_arguments(self, parser):
        parser.add_argument('--ranking-name', choices=RANKING_NAMES)
        parser.add_argument('--batch-size', type=int, default=1000)

    def handle(self, *args, **options):
        if options['batch_size'] <= 0:
            raise CommandError('--batch-size must be positive')
        ranking_names = (options['ranking_name'],) if options['ranking_name'] else RANKING_NAMES
        for ranking_name, count in rebuild_strict_ng_ranks(ranking_names, options['batch_size']).items():
            self.stdout.write(self.style.SUCCESS(f'{ranking_name}: {count} players'))
