from django.core.management.base import BaseCommand

from monitor.services import publish_monitor_snapshot


class Command(BaseCommand):
    help = 'Sample server statistics and atomically publish runtime/monitor.json.'

    def handle(self, *args, **options):
        publish_monitor_snapshot()
        self.stdout.write(self.style.SUCCESS('Monitor snapshot published.'))
