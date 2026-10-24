from django.core.management.base import BaseCommand, CommandError
from py7zr.exceptions import ArchiveError

from minigame.archive import pack_replay, unpack_replay
from minigame.models import MiniGameBestScore
from minigame.replay import migrate_replay, replay_version
from minigame.utils import RANKINGS


class Command(BaseCommand):
    help = '将小游戏 JSON 回放转换为 v1 并保存为 7z 二进制，不修改成绩或 Redis'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        pending = migrated = skipped = invalid = 0
        records = MiniGameBestScore.objects.only('id', 'ranking_key', 'score', 'achieved_at', 'replay_archive', 'replay').order_by('id')
        for record in records.iterator(chunk_size=200):
            try:
                ranking = RANKINGS.get(record.ranking_key)
                if ranking is None:
                    raise ValueError(f'Unknown ranking: {record.ranking_key}')
                source = unpack_replay(record.replay_archive) if record.replay_archive is not None else record.replay
                converted = migrate_replay(ranking, source)
                if record.replay_archive is not None and replay_version(source) == 1:
                    skipped += 1
                    continue
            except (ValueError, ArchiveError, EOFError, OSError) as error:
                invalid += 1
                self.stderr.write(f'{record.id} ({record.ranking_key}): {error}')
                continue
            pending += 1
            if options['dry_run']:
                continue
            updated = MiniGameBestScore.objects.filter(pk=record.pk, score=record.score, achieved_at=record.achieved_at).update(replay_archive=pack_replay(converted), replay=None)
            migrated += updated
            skipped += 1 - updated
        self.stdout.write(f'pending={pending}, migrated={migrated}, skipped={skipped}, invalid={invalid}')
        if invalid:
            raise CommandError(f'{invalid} replay record(s) could not be migrated; their original values were preserved.')
