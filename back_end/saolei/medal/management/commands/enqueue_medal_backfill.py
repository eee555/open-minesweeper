from django.core.management.base import BaseCommand, CommandError

from medal.tasks import enqueue_player_backfill
from userprofile.models import UserProfile


class Command(BaseCommand):
    help = '为玩家入队低优先级勋章全量评估；默认只补发未扫描玩家，--all 包含已经扫描的玩家。'

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help='包含已有 MedalScan 的玩家，用于规则更新后的重算。')
        parser.add_argument('--batch-size', type=int, default=200)
        parser.add_argument('--after-id', type=int, default=0, help='只处理大于此 ID 的玩家，用于断点续跑。')
        parser.add_argument('--through-id', type=int, help='只处理不大于此 ID 的玩家；默认固定为启动时的最大玩家 ID。')
        parser.add_argument('--limit', type=int, help='本次最多处理多少名玩家；可用于分次入队。')
        parser.add_argument('--dry-run', action='store_true', help='只显示候选数量和范围，不创建任务。')

    def handle(self, *args, **options):
        batch_size, after_id, limit = options['batch_size'], options['after_id'], options['limit']
        through_id = options['through_id']
        if batch_size <= 0 or after_id < 0 or (limit is not None and limit <= 0) or (through_id is not None and through_id < 0):
            raise CommandError('batch-size/limit must be positive; after-id/through-id must be nonnegative.')
        if through_id is None:
            through_id = UserProfile.objects.order_by('-pk').values_list('pk', flat=True).first() or 0
        users = UserProfile.objects.filter(pk__gt=after_id, pk__lte=through_id)
        if not options['all']:
            users = users.filter(medal_scan__isnull=True)
        if options['dry_run']:
            candidates = users.count()
            self.stdout.write(f'Dry run: {min(candidates, limit) if limit is not None else candidates} players; after_id={after_id}; through_id={through_id}')
            return
        queued, processed = 0, 0
        cursor = after_id
        self.stdout.write(f'Starting after_id={cursor}; through_id={through_id}')
        while limit is None or processed < limit:
            size = batch_size if limit is None else min(batch_size, limit - processed)
            user_ids = list(users.filter(pk__gt=cursor).order_by('pk').values_list('pk', flat=True)[:size])
            if not user_ids:
                break
            for user_id in user_ids:
                try:
                    result = enqueue_player_backfill(user_id)
                except Exception as exc:
                    raise CommandError(f'Enqueue failed for user {user_id}; retry with --after-id {cursor} --through-id {through_id} and the same selection options.') from exc
                queued += result is not None
                processed += 1
                cursor = user_id
            self.stdout.write(f'Processed {processed}; enqueued {queued}; last_user_id={cursor}; through_id={through_id}')
        self.stdout.write(self.style.SUCCESS(f'Enqueued {queued}; processed {processed}; last_user_id={cursor}; through_id={through_id}'))
