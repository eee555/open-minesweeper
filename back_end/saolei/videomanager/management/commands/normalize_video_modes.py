from django.core.management.base import BaseCommand
from django.db import transaction

from config.text_choices import MS_TextChoices
from utils.ranking_lock import ranking_access
from videomanager.models import VideoModel


class Command(BaseCommand):
    help = '将已有非 EVF 录像归为标准模式，并触发排行榜和勋章刷新。'

    def handle(self, *args, **options):
        candidates = VideoModel.objects.exclude(software=MS_TextChoices.Software.EVF).exclude(mode=MS_TextChoices.Mode.STD)
        updated = 0
        for video_id in candidates.values_list('pk', flat=True).iterator():
            with ranking_access(operation='normalize_video_modes'), transaction.atomic():
                video = VideoModel.objects.select_for_update().get(pk=video_id)
                if video.software == MS_TextChoices.Software.EVF or video.mode == MS_TextChoices.Mode.STD:
                    continue
                video.mode = MS_TextChoices.Mode.STD
                video.save(update_fields=['mode'])
                updated += 1
        self.stdout.write(self.style.SUCCESS(f'Normalized {updated} replay modes.'))
