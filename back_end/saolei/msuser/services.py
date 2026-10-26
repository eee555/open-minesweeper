from django.db import transaction
from django.db.models import BigIntegerField, Case, Count, Exists, F, Min, OuterRef, Q, QuerySet, Sum, Value, When

from config.text_choices import MS_TextChoices
from msuser.models import UserMS
from videomanager.models import VideoModel
from .utils import get_video_num_limit


def update_video_statistics(userms_id: int | None, *, tournament: bool, count: int, size: int, limit: int | None = None, using='default'):
    """一次 UPDATE 写入分类统计及需要提升的上传额度，不写入生成字段。"""
    if userms_id is None:
        return
    users = UserMS.objects.using(using).filter(pk=userms_id)
    if count == 0 and size == 0:
        if limit is not None:
            users.filter(video_num_limit__lt=limit).update(video_num_limit=limit)
        return
    if limit is None:
        limit_update = F('video_num_limit')
    else:
        limit_update = Case(When(video_num_limit__lt=limit, then=Value(limit)), default=F('video_num_limit'))
    if tournament:
        users.update(
            video_num_tournament=F('video_num_tournament') + count,
            video_size_tournament=F('video_size_tournament') + size,
            video_num_limit=limit_update,
        )
    else:
        users.update(
            video_num_total=F('video_num_total') + count,
            video_size_total=F('video_size_total') + size,
            video_num_limit=limit_update,
        )


def transfer_video_statistics(old_userms_id: int | None, userms_id: int | None, *, tournament: bool, old_size: int, size: int, limit: int | None = None, using='default'):
    """录像归属变化时，一次条件 UPDATE 同时更新原玩家和新玩家。"""
    users = UserMS.objects.using(using).filter(pk__in=[old_userms_id, userms_id])
    if limit is None:
        limit_update = F('video_num_limit')
    else:
        limit_update = Case(When(pk=userms_id, video_num_limit__lt=limit, then=Value(limit)), default=F('video_num_limit'))
    if tournament:
        users.update(
            video_num_tournament=Case(
                When(pk=old_userms_id, then=F('video_num_tournament') - 1),
                When(pk=userms_id, then=F('video_num_tournament') + 1),
                default=F('video_num_tournament'),
            ),
            video_size_tournament=Case(
                When(pk=old_userms_id, then=F('video_size_tournament') - old_size),
                When(pk=userms_id, then=F('video_size_tournament') + size),
                default=F('video_size_tournament'),
                output_field=BigIntegerField(),
            ),
            video_num_limit=limit_update,
        )
    else:
        users.update(
            video_num_total=Case(
                When(pk=old_userms_id, then=F('video_num_total') - 1),
                When(pk=userms_id, then=F('video_num_total') + 1),
                default=F('video_num_total'),
            ),
            video_size_total=Case(
                When(pk=old_userms_id, then=F('video_size_total') - old_size),
                When(pk=userms_id, then=F('video_size_total') + size),
                default=F('video_size_total'),
                output_field=BigIntegerField(),
            ),
            video_num_limit=limit_update,
        )


@transaction.atomic
def refresh_video_statistics(users: list[UserMS], *, batch_size=None):
    """按比赛标记及关联重算，使用 EXISTS 避免多场比赛重复累计同一录像。"""
    if not users:
        return
    fields = ['video_num_total', 'video_num_tournament', 'video_size_total', 'video_size_tournament']
    normal = Q(ongoing_tournament=False, has_tournament=False)
    videos = (
        VideoModel.objects
        .filter(player__userms_id__in=[user.pk for user in users])
        .alias(has_tournament=Exists(VideoModel.tournaments.through.objects.filter(videomodel_id=OuterRef('pk'))))
    )
    rows = (
        videos
        .order_by()
        .values('player__userms_id')
        .annotate(
            video_num_total=Count('id', filter=normal),
            video_num_tournament=Count('id', filter=~normal),
            video_size_total=Sum('file_size', filter=normal, default=0, output_field=BigIntegerField()),
            video_size_tournament=Sum('file_size', filter=~normal, default=0, output_field=BigIntegerField()),
        )
    )
    counts_by_user = {row['player__userms_id']: row for row in rows}
    for user in users:
        counts = counts_by_user.get(user.pk, {})
        user.video_num_total = counts.get('video_num_total', 0)
        user.video_num_tournament = counts.get('video_num_tournament', 0)
        user.video_size_total = counts.get('video_size_total', 0)
        user.video_size_tournament = counts.get('video_size_tournament', 0)
    UserMS.objects.bulk_update(users, fields, batch_size=batch_size)


def update_video_count_limit_from_videos(userms: UserMS, videos: QuerySet[VideoModel]):
    """根据一批新转为官方的录像刷新用户录像数量上限。"""
    min_timems = (
        videos
        .filter(
            level=MS_TextChoices.Level.EXPERT,
            mode=MS_TextChoices.Mode.STD,
            state=MS_TextChoices.State.OFFICIAL,
        )
        .aggregate(min_timems=Min('timems'))['min_timems']
    )
    if min_timems is None:
        return

    video_num_limit = get_video_num_limit(min_timems)
    if video_num_limit > userms.video_num_limit:
        userms.video_num_limit = video_num_limit
        userms.save(update_fields=['video_num_limit'])
