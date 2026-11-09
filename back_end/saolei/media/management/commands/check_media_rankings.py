"""只读核对四个作品榜 zset 与 DB 是否一致；发现漂移以非零退出码告警。

见 MEDIA_PLAN.md 第 6、10 节。缓存同步任务失败、worker 停摆或 Redis 被清空时，
数据库仍然正确，只有榜单滞后。本命令供定时巡检与部署后自检，修复手段是
`rebuild_media_rankings` 或在管理页重启失败的同步任务。
"""

from math import isclose

from django.core.management.base import BaseCommand, CommandError
from django.tasks import TaskResultStatus
from django_tasks_db.models import DBTaskResult

from media import cache, tasks
from media.models import Media
from media.utils import decay, MediaStatus

SCORE_REL_TOLERANCE = 1e-6
SCORE_ABS_TOLERANCE = 1e-6


def _expected_scores(anchor):
    media_hot, media_likes, user_hot, user_likes = {}, {}, {}, {}
    rows = Media.objects.filter(status=MediaStatus.VERIFIED).values_list(
        'pk', 'user_id', 'hot_value', 'likes', 'hot_value_updated_at',
    )
    for pk, user_id, hot_value, likes, base in rows.iterator(chunk_size=1000):
        hot = hot_value * decay(base, anchor)
        media_hot[pk] = hot
        media_likes[pk] = likes
        user_hot[user_id] = user_hot.get(user_id, 0.0) + hot
        user_likes[user_id] = user_likes.get(user_id, 0) + likes
    return {
        cache.MEDIA_RANK_HOT: media_hot,
        cache.MEDIA_RANK_LIKES: media_likes,
        cache.MEDIA_RANK_USER_HOT: user_hot,
        cache.MEDIA_RANK_USER_LIKES: user_likes,
    }


def _actual_scores(key):
    return {int(member): float(score) for member, score in cache.cache.zrange(key, 0, -1, withscores=True)}


def _diff(key, expected, actual, limit):
    problems = []
    for member in sorted(set(expected) | set(actual)):
        want, got = expected.get(member), actual.get(member)
        if want is None:
            problems.append(f'{key}: unexpected member {member} (score={got})')
        elif got is None:
            problems.append(f'{key}: missing member {member} (expected={want})')
        elif not isclose(want, got, rel_tol=SCORE_REL_TOLERANCE, abs_tol=SCORE_ABS_TOLERANCE):
            problems.append(f'{key}: member {member} score {got} != expected {want}')
        if len(problems) >= limit:
            break
    return problems


class Command(BaseCommand):
    help = 'Check media ranking zsets against verified Media rows (read-only).'

    def add_arguments(self, parser):
        parser.add_argument('--max-examples', type=int, default=10)

    def handle(self, *args, **options):
        limit = options['max_examples']
        if limit <= 0:
            raise CommandError('--max-examples must be positive')
        anchor = cache.read_hot_reference()
        if anchor is None:
            raise CommandError('media:hot:anchor is missing; run rebuild_media_rankings')

        problems = []
        for key, expected in _expected_scores(anchor).items():
            problems.extend(_diff(key, expected, _actual_scores(key), limit))

        path = tasks.task_sync_media_scores.module_path
        failed = DBTaskResult.objects.filter(task_path=path, status=TaskResultStatus.FAILED).count()
        pending = DBTaskResult.objects.filter(
            task_path=path, status__in=[TaskResultStatus.READY, TaskResultStatus.RUNNING],
        ).count()
        self.stdout.write(f'anchor={anchor.isoformat()} failed_sync_tasks={failed} pending_sync_tasks={pending}')
        if failed:
            self.stdout.write(self.style.WARNING(
                f'{failed} failed media cache sync task(s) can be restarted from the staff task page.',
            ))

        if problems:
            raise CommandError(
                'Media ranking cache drift detected (DB is authoritative): '
                + '; '.join(problems[:limit])
                + '; run "python manage.py rebuild_media_rankings" or restart the failed sync task',
            )
        self.stdout.write(self.style.SUCCESS('Media ranking cache matches the database.'))
