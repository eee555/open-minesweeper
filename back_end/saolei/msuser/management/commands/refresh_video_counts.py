from django.core.management.base import BaseCommand, CommandError

from msuser.models import UserMS
from msuser.services import refresh_video_statistics


class Command(BaseCommand):
    help = '刷新所有用户的比赛、非比赛录像数量及文件空间'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=1000)

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        if batch_size <= 0:
            raise CommandError('--batch-size must be positive')

        last_pk = 0
        updated = 0
        while users := list(UserMS.objects.filter(pk__gt=last_pk).order_by('pk').only('pk')[:batch_size]):
            refresh_video_statistics(users, batch_size=batch_size)
            last_pk = users[-1].pk
            updated += len(users)

        self.stdout.write(self.style.SUCCESS(f'refreshed video counts for {updated} users'))
