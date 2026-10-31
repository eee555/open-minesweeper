from django.core.management.base import BaseCommand, CommandError
from django.db import connections, DEFAULT_DB_ALIAS

from msuser.models import UserMS
from msuser.services import cleanup_orphan_userms


class Command(BaseCommand):
    help = '清理没有关联 UserProfile 的孤立 UserMS 及其标识'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='只统计，不删除')
        parser.add_argument('--batch-size', type=int, default=1000)
        parser.add_argument('--database', default=DEFAULT_DB_ALIAS, choices=tuple(connections))

    def handle(self, *args, **options):
        if options['batch_size'] <= 0:
            raise CommandError('--batch-size must be positive')
        database = options['database']
        if options['dry_run']:
            count = UserMS.objects.using(database).filter(parent__isnull=True).count()
            self.stdout.write(f'Would delete {count} orphan UserMS records')
            return
        count = cleanup_orphan_userms(batch_size=options['batch_size'], using=database)
        self.stdout.write(self.style.SUCCESS(f'Deleted {count} orphan UserMS records'))
