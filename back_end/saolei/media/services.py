"""作品页业务逻辑：投稿、投喂、审核、驳回、恢复、硬删除与月度刷新；见 MEDIA_PLAN.md 第 5、6 节。"""

import logging
from math import floor

from django.db import IntegrityError, transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.utils import timezone

from . import cache
from .models import Media, MediaLikes, UserMedia
from .tasks import enqueue_media_score_sync
from .utils import decay, MEDIA_DAILY_LIKE_LIMIT, MediaStatus

logger = logging.getLogger('media')


class MediaServiceError(Exception):
    """业务状态错误；API 层据此转 HttpError，service 层不处理权限。"""

    def __init__(self, message, status_code=400):
        super().__init__(message, status_code)
        self.message = message
        self.status_code = status_code


def _balance(profile, user):
    earned = floor((timezone.now() - user.date_joined).total_seconds() / 86400)
    return max(earned - profile.likes_sent, 0)


def get_balance(user):
    profile = UserMedia.objects.filter(pk=user.pk).first()
    likes_sent = profile.likes_sent if profile else 0
    earned = floor((timezone.now() - user.date_joined).total_seconds() / 86400)
    return max(earned - likes_sent, 0)


def create_media(user, *, media_format, suffix, language, title='', created_at=None, metadata_pending=False):
    """投稿落库：唯一约束防重复外链；外站元数据拉取与归属校验由 API 层完成。

    metadata_pending=True 表示外站不可用时的降级投稿，标题由管理员审核时补录；
    外站作者 id 只用于 API 层一次性归属核验，不传给 service、不入库。
    """
    try:
        with transaction.atomic():
            # 请求路径不持有缓存锁：读 anchor 只是 Redis GET，基准收敛交给持久化的
            # 后台任务（同事务入队），因此月度换算再慢也不会占用 2s / 10s 请求预算。
            base = cache.get_hot_reference()
            media = Media.objects.create(
                user=user, title=title, language=language, created_at=created_at or timezone.now(),
                format=media_format, suffix=suffix, metadata_pending=metadata_pending,
                status=MediaStatus.PENDING, likes=0, hot_value=0,
                hot_value_updated_at=base,
            )
            # 创建完成后校验基准：锚点若已推进，立刻把这一行换算到新基准。
            current = cache.get_hot_reference()
            if current != base:
                Media.objects.filter(pk=media.pk).update(
                    hot_value=F('hot_value') * decay(base, current), hot_value_updated_at=current,
                )
                media.hot_value_updated_at = current
            enqueue_media_score_sync(media.pk, user.pk)
            return media
    except IntegrityError:
        raise MediaServiceError('该作品已投稿过，不可重复投稿', 409) from None


def like_media(user, media_id):
    """投喂 1 个红宝石：先锁作品再锁用户（与驳回/硬删除一致），按 UTC 自然日限 10 次成功投喂。

    热度增量按作品行自己的 hot_value_updated_at 折算，不依赖 Redis anchor；Redis 写入
    在 on_commit 回调里按提交后的 DB 绝对值覆盖，迟到回调不会重建已删除作品。
    daily_date / daily_likes 与 likes_sent 在同一事务内更新，事务回滚即不计数。
    驳回与硬删除只退还 likes_sent，不回退当日已用次数（16.1 第 17 条）。
    """
    with transaction.atomic():
        now = timezone.now()
        today = now.date()  # timezone.now() 返回 UTC aware datetime，date() 即 UTC 自然日
        media = Media.objects.select_for_update().filter(pk=media_id).first()
        if media is None:
            raise MediaServiceError('Media not found', 404)
        if media.status == MediaStatus.REJECTED:
            raise MediaServiceError('Rejected media cannot be liked', 409)
        profile, _ = UserMedia.objects.select_for_update().get_or_create(user=user)
        daily_likes = 0 if profile.daily_date != today else profile.daily_likes
        if daily_likes >= MEDIA_DAILY_LIKE_LIMIT:
            raise MediaServiceError('Daily like limit reached', 429)
        balance = _balance(profile, user)
        if balance < 1:
            raise MediaServiceError('Insufficient rubies', 400)
        base = media.hot_value_updated_at
        factor = decay(base, now)
        delta_hot = 1 / factor
        media.hot_value += delta_hot
        media.likes += 1
        media.save(update_fields=['hot_value', 'likes'])
        record, _ = MediaLikes.objects.get_or_create(user=user, media=media)
        MediaLikes.objects.filter(pk=record.pk).update(likes=F('likes') + 1)
        UserMedia.objects.filter(pk=profile.pk).update(
            likes_sent=F('likes_sent') + 1, daily_likes=daily_likes + 1, daily_date=today,
        )
        if media.status == MediaStatus.VERIFIED:
            enqueue_media_score_sync(media_id, media.user_id)
        hot_now = media.hot_value * factor
        result = {'likes': media.likes, 'hot_now': hot_now, 'balance': balance - 1, 'status': media.status}
    return result


def verify_media(media_id, actor_id, *, title=None, created_at=None):
    """管理员审核通过：pending → verified，按当前累计值一次性补齐四个 zset。

    降级投稿必须补录标题；外站作者 id 由 API 层通过 AccountLinkQueue 一次性核验，
    不传进 service、不落库，service 层不处理权限。
    """
    with transaction.atomic():
        media = Media.objects.select_for_update().filter(pk=media_id).first()
        if media is None:
            raise MediaServiceError('Media not found', 404)
        if media.status != MediaStatus.PENDING:
            raise MediaServiceError('Only pending media can be verified', 409)
        fields = ['status']
        media.status = MediaStatus.VERIFIED
        if media.metadata_pending:
            normalized_title = str(title or '').strip()
            if not normalized_title:
                raise MediaServiceError('待补全投稿必须由管理员填写标题', 400)
            media.title = normalized_title[:200]
            media.metadata_pending = False
            fields += ['title', 'metadata_pending']
            if created_at is not None:
                media.created_at = created_at
                fields.append('created_at')
        media.save(update_fields=fields)
        hot, likes = media.hot_value, media.likes
        enqueue_media_score_sync(media_id, media.user_id)
    logger.info('Staff #%s verified media #%s: likes=%s hot_value=%s', actor_id, media_id, likes, hot)
    return media


def _refund_like_records(media):
    """按投喂记录逐条退还 likes_sent（下限 0），返回退还总数。"""
    total = 0
    for user_id, likes in media.like_records.values_list('user_id', 'likes'):
        if likes <= 0:
            continue
        UserMedia.objects.filter(pk=user_id).update(likes_sent=Greatest(F('likes_sent') - likes, Value(0)))
        total += likes
    return total


def reject_media(media_id, actor_id, reason=''):
    """管理员驳回：pending → rejected，退还红宝石并同事务清零 likes/hot 与投喂记录（P1 / Q12）。"""
    with transaction.atomic():
        media = Media.objects.select_for_update().filter(pk=media_id).first()
        if media is None:
            raise MediaServiceError('Media not found', 404)
        if media.status != MediaStatus.PENDING:
            raise MediaServiceError('Only pending media can be rejected', 409)
        refunded = _refund_like_records(media)
        media.like_records.all().delete()
        media.status = MediaStatus.REJECTED
        media.rejected_at = timezone.now()
        media.rejected_by_id = actor_id
        media.reject_reason = (reason or '')[:200]
        media.refunded_likes = refunded
        media.likes = 0
        media.hot_value = 0
        media.save(update_fields=['status', 'rejected_at', 'rejected_by', 'reject_reason', 'refunded_likes', 'likes', 'hot_value'])
        logger.info(
            'Staff #%s rejected media #%s: reason=%s refunded_likes=%s',
            actor_id, media_id, media.reject_reason, refunded,
        )
    return media


def reopen_media(media_id, actor_id):
    """改回待审核：rejected → pending，复用同一行；驳回时已退还并清零，无需再处理红宝石。"""
    with transaction.atomic():
        media = Media.objects.select_for_update().filter(pk=media_id).first()
        if media is None:
            raise MediaServiceError('Media not found', 404)
        if media.status != MediaStatus.REJECTED:
            raise MediaServiceError('Only rejected media can be reopened', 409)
        media.status = MediaStatus.PENDING
        media.rejected_at = None
        media.save(update_fields=['status', 'rejected_at'])
        logger.info('Staff #%s reopened media #%s', actor_id, media_id)
    return media


def hard_delete_media(media_id, actor_id):
    """站长硬删除：仅 verified，退还红宝石、写快照日志、回退四个 zset；删除后外链可重投。"""
    with transaction.atomic():
        media = Media.objects.select_for_update().filter(pk=media_id).first()
        if media is None:
            return False
        if media.status != MediaStatus.VERIFIED:
            raise MediaServiceError('Only verified media can be hard-deleted', 409)
        refunded = _refund_like_records(media)
        hot, likes, author_id = media.hot_value, media.likes, media.user_id
        logger.info(
            'Superuser #%s hard-deleted media #%s: format=%s suffix=%s title=%s user_id=%s '
            'likes=%s hot_value=%s refunded_likes=%s',
            actor_id, media_id, media.format, media.suffix, media.title, author_id, likes, hot, refunded,
        )
        media.delete()
        enqueue_media_score_sync(media_id, author_id)
    return True


def set_media_banned(user_id, banned):
    profile, _ = UserMedia.objects.get_or_create(user_id=user_id)
    profile.banned = banned
    profile.save(update_fields=['banned'])
    return profile


def _fold_db_hot_reference(target):
    """按不同行基准分组，用 SQL 端乘算换算 DB 热度；F() 避免 Python 快照覆盖已提交的增量。

    与投稿共用缓存锁，保证「读到旧 anchor 后暂停的投稿」不会在两次换算之间插入旧基准行。
    """
    with cache.media_cache_lock():
        with transaction.atomic():
            references = list(
                Media.objects.filter(hot_value_updated_at__lt=target)
                .values_list('hot_value_updated_at', flat=True).distinct(),
            )
            for reference in references:
                Media.objects.filter(hot_value_updated_at=reference).update(
                    hot_value=F('hot_value') * decay(reference, target), hot_value_updated_at=target,
                )


def refresh_hot_reference(at_time=None):
    """月度刷新：DB 先按行基准换算并提交，再发布 Redis anchor，最后补齐窗口内新建的行。

    三步各自持有缓存锁：投稿不可能「读到旧 anchor 后等到两次换算都结束才插入」，
    Redis 写入回调也只会在锁释放后按提交后的 DB 绝对值重算。二次换算幂等，用于
    收敛刷新窗口内以旧 anchor 为基准新建的作品，避免用户主页按 hot_value 排序混用基准。
    """
    target = cache.media_hot_reference_time(at_time)
    _fold_db_hot_reference(target)
    changed = cache.refresh_hot_reference(target)
    _fold_db_hot_reference(target)
    logger.info('Media hot reference refreshed: redis_changed=%s target=%s', changed, target.isoformat())
    return changed
