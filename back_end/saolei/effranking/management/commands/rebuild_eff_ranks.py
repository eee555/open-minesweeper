from django.core.management.base import BaseCommand, CommandError

from effranking.nf_ioe.services import rebuild_nf_ioe_ranks
from effranking.path.services import rebuild_path_ranks
from effranking.thrp.services import rebuild_thrp_ranks
from effranking.tpe.services import rebuild_tpe_ranks


class Command(BaseCommand):
    help = '从录像库重建效率榜，完成后原子替换 Redis 榜单；执行期间暂停相关写入'

    def add_arguments(self, parser):
        parser.add_argument('--ranking-name', choices=['thrp', 'nf_ioe', 'tpe', 'path'], default='thrp')
        parser.add_argument('--batch-size', type=int, default=1000)

    def handle(self, *args, **options):
        if options['batch_size'] <= 0:
            raise CommandError('--batch-size must be positive')
        name = options['ranking_name']
        rebuild = {'thrp': rebuild_thrp_ranks, 'nf_ioe': rebuild_nf_ioe_ranks, 'tpe': rebuild_tpe_ranks, 'path': rebuild_path_ranks}[name]
        count = rebuild(options['batch_size'])
        self.stdout.write(self.style.SUCCESS(f'{name}: {count} players'))
