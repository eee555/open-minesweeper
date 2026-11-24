from django.core.management.base import BaseCommand, CommandError

from videomanager.share_preview import PLACEHOLDER_FILENAME, preview_directory, render_placeholder, write_preview


class Command(BaseCommand):
    help = '准备录像分享预览的共用占位 PNG；图片仅由 Nginx 内部转发'

    def handle(self, *args, **options):
        path = preview_directory() / PLACEHOLDER_FILENAME
        try:
            write_preview(path, render_placeholder())
        except (OSError, ValueError) as exc:
            raise CommandError(f'Failed to prepare share preview placeholder: {exc}') from exc
        self.stdout.write(self.style.SUCCESS(f'Prepared {path}'))
