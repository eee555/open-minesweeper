from django.core.management.base import BaseCommand

from medal.maintenance import correct_modes


class Command(BaseCommand):
    help = '将走马观花旧的默认十项要求修正为四项；保留自定义要求，可重复执行。'

    def handle(self, *args, **options):
        correct_modes()
        self.stdout.write(self.style.SUCCESS('Medal mode requirements checked.'))
