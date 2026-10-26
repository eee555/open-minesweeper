from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from msuser.models import UserMS
from videomanager.models import VideoModel


class Command(BaseCommand):
    help = '刷新所有用户的录像总数，排除比赛录像'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=1000)

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        if batch_size <= 0:
            raise CommandError('--batch-size must be positive')

        last_pk = 0
        updated = 0
        while users := list(UserMS.objects.filter(pk__gt=last_pk).order_by('pk').only('pk')[:batch_size]):
            # The reverse relation includes videos from ended tournaments too.
            rows = (
                VideoModel.objects
                .filter(player__userms_id__in=[user.pk for user in users], ongoing_tournament=False, tournaments__isnull=True)
                .order_by()
                .values('player__userms_id')
                .annotate(video_num_total=Count('id'))
            )
            counts_by_user = {row['player__userms_id']: row['video_num_total'] for row in rows}
            for user in users:
                user.video_num_total = counts_by_user.get(user.pk, 0)
            UserMS.objects.bulk_update(users, ['video_num_total'], batch_size=batch_size)
            last_pk = users[-1].pk
            updated += len(users)

        self.stdout.write(self.style.SUCCESS(f'refreshed video counts for {updated} users'))
