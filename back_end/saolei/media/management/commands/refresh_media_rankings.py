"""低频管理命令：推进 T_db / T_r 并从 DB 全量重建四个 zset；含只读巡检。

见 MEDIA_PLAN.md 附录 A.4。不加入部署流程，不阻塞请求写；执行期间正式 key 上的
增量可能被 rename 覆盖，接受短暂漂移，DB 始终正确，重跑即可收敛。
"""

from datetime import datetime, timezone as datetime_timezone
from math import isclose

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from media import cache
from media.models import Media
from media.utils import decay, MediaStatus

SCORE_REL_TOLERANCE = 1e-6
SCORE_ABS_TOLERANCE = 1e-6


def _expected_scores(factor):
    """按 T_r 基准算四个 zset 的期望分数；T_db != T_r 时必须乘 decay(T_db, T_r)。"""
    media_hot, media_likes, user_hot, user_likes = {}, {}, {}, {}
    rows = Media.objects.filter(status=MediaStatus.VERIFIED).values_list('pk', 'user_id', 'hot_value', 'likes')
    for pk, user_id, hot_value, likes in rows.iterator(chunk_size=1000):
        hot = hot_value * factor
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
    help = 'Advance the media hot reference and rebuild the four ranking zsets from the database.'

    def add_arguments(self, parser):
        parser.add_argument('--check', action='store_true', help='只读巡检四个 zset，不写 DB 与 Redis')
        parser.add_argument('--rebuild-only', action='store_true', help='不推进 T，只按当前 T_r 全量重建')
        parser.add_argument('--reference', type=datetime.fromisoformat, default=None,
                            help='目标基准 ISO 8601 UTC，默认当前时刻；不得早于 T_db')
        parser.add_argument('--batch-size', type=int, default=1000)
        parser.add_argument('--max-examples', type=int, default=10)

    def handle(self, *args, **options):
        limit = options['max_examples']
        if limit <= 0:
            raise CommandError('--max-examples must be positive')
        if options['check']:
            return self._check(limit)
        batch_size = options['batch_size']
        if batch_size <= 0:
            raise CommandError('--batch-size must be positive')

        old_t_db = cache.read_db_hot_reference()
        advanced = False
        if options['rebuild_only']:
            reference = None
        else:
            reference = options['reference'] or timezone.now()
            if reference.tzinfo is None:
                reference = reference.replace(tzinfo=datetime_timezone.utc)
            if reference < old_t_db:
                raise CommandError(f'--reference {reference.isoformat()} is earlier than T_db {old_t_db.isoformat()}')
            advanced = reference != old_t_db
            if advanced:
                with transaction.atomic():
                    Media.objects.update(
                        hot_value=F('hot_value') * decay(old_t_db, reference),
                        hot_value_updated_at=reference,
                    )

        try:
            count = cache.rebuild_rankings(batch_size=batch_size, reference=reference)
        except Exception as exc:
            new_t_db = cache.read_db_hot_reference().isoformat()
            raise CommandError(
                f'Redis publish failed ({exc}); T_db={new_t_db} is authoritative and T_r may be stale, '
                'rerun refresh_media_rankings to reconcile',
            ) from exc
        self.stdout.write(self.style.SUCCESS(
            f'Media rankings rebuilt: {count} verified rows, T_db={cache.read_db_hot_reference().isoformat()}, '
            f'T_r={cache.read_hot_reference().isoformat()}, reference_advanced={advanced}.',
        ))

    def _check(self, limit):
        t_db = cache.read_db_hot_reference()
        t_r = cache.read_hot_reference()
        if t_r is None:
            raise CommandError('media:hot:anchor (T_r) is missing; run refresh_media_rankings without --check')
        problems = []
        for key, expected in _expected_scores(decay(t_db, t_r)).items():
            problems.extend(_diff(key, expected, _actual_scores(key), limit))
        self.stdout.write(f'T_db={t_db.isoformat()} T_r={t_r.isoformat()}')
        if problems:
            raise CommandError(
                'Media ranking cache drift detected (DB is authoritative): ' + '; '.join(problems[:limit])
                + '; run "python manage.py refresh_media_rankings"',
            )
        self.stdout.write(self.style.SUCCESS('Media ranking cache matches the database.'))
