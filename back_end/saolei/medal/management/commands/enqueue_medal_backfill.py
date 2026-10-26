from django.core.management.base import BaseCommand

from medal.tasks import enqueue_player_backfill
from userprofile.models import UserProfile


class Command(BaseCommand):
    help = '为还没有 MedalScan 的玩家入队勋章历史补发。优先级与 task_backfill_player_medals 相同。'

    def handle(self, *args, **options):
        queued = 0
        user_ids = UserProfile.objects.filter(medal_scan__isnull=True).values_list('pk', flat=True).iterator()
        for user_id in user_ids:
            if enqueue_player_backfill(user_id) is not None:
                queued += 1
        self.stdout.write(self.style.SUCCESS(f'Enqueued {queued}'))
