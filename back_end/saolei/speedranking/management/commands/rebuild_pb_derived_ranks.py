from django.core.management.base import BaseCommand, CommandError

from speedranking.pb_derived.services import rebuild_all


class Command(BaseCommand):
    help = '清空并从现有 PB 用户 hash 全量重建衍生榜；频率表或分段变更后使用，执行前暂停相关读写'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=100)

    def handle(self, *args, **options):
        if options['batch_size'] <= 0:
            raise CommandError('--batch-size must be positive')
        self.stdout.write('Rebuilding PB derived rankings from existing PB hashes; make sure rebuild_pb_ranks ran first.')
        try:
            count = rebuild_all(options['batch_size'], progress=self.progress)
        except Exception as error:
            raise CommandError(f'PB derived rebuild failed; the derived cache may be partially complete. Rerun this command after fixing the error: {error}') from error
        self.stdout.write(self.style.SUCCESS(f'PB derived: {count} players; 3 record hashes and 132 ranking indices refreshed'))
        return None

    def progress(self, count):
        self.stdout.write(f'PB derived: {count} players')
