"""作品页业务逻辑：投稿、投喂、审核、驳回、恢复、硬删除与月度刷新；见 MEDIA_PLAN.md 第 5、6 节。"""

import logging
from math import floor

from django.db import IntegrityError, transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.utils import timezone

from . import cache
from .models import Media, MediaLikes, UserMedia
from .utils import decay, MediaStatus

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
        return Media.objects.create(
            user=user, title=title, language=language, created_at=created_at or timezone.now(),
            format=media_format, suffix=suffix, metadata_pending=metadata_pending,
            status=MediaStatus.PENDING, likes=0, hot_value=0,
            hot_value_updated_at=cache.get_hot_reference(),
        )
    except IntegrityError:
        raise MediaServiceError('该作品已投稿过，不可重复投稿', 409) from None


def like_media(user, media_id, count):
    """投喂：锁用户与作品行，按 anchor 折算热度；审核中只写 DB，已审核才同步四个 zset。"""
    if count <= 0:
        raise MediaServiceError('count must be positive', 400)
    with transaction.atomic():
        profile, _ = UserMedia.objects.select_for_update().get_or_create(user=user)
        media = Media.objects.select_for_update().filter(pk=media_id).first()
        if media is None:
            raise MediaServiceError('Media not found', 404)
        if media.status == MediaStatus.REJECTED:
            raise MediaServiceError('Rejected media cannot be liked', 409)
        balance = _balance(profile, user)
        if balance < count:
            raise MediaServiceError('Insufficient rubies', 400)
        reference = cache.get_hot_reference()
        now = timezone.now()
        factor = decay(reference, now)
        delta_hot = count / factor
        media.hot_value += delta_hot
        media.likes += count
        media.save(update_fields=['hot_value', 'likes'])
        record, _ = MediaLikes.objects.get_or_create(user=user, media=media)
        MediaLikes.objects.filter(pk=record.pk).update(likes=F('likes') + count)
        UserMedia.objects.filter(pk=profile.pk).update(likes_sent=F('likes_sent') + count)
        if media.status == MediaStatus.VERIFIED:
            author_id = media.user_id
            transaction.on_commit(lambda: cache.add_media_scores(media_id, author_id, delta_hot, count))
        hot_now = media.hot_value * factor
        result = {'likes': media.likes, 'hot_now': hot_now, 'balance': balance - count, 'status': media.status}
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
        hot, likes, author_id = media.hot_value, media.likes, media.user_id
        transaction.on_commit(lambda: cache.add_media_scores(media_id, author_id, hot, likes))
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
        transaction.on_commit(lambda: cache.remove_media_scores(media_id, author_id, hot, likes))
    return True


def set_media_banned(user_id, banned):
    profile, _ = UserMedia.objects.get_or_create(user_id=user_id)
    profile.banned = banned
    profile.save(update_fields=['banned'])
    return profile


def refresh_hot_reference(at_time=None, batch_size=1000):
    """月度刷新：Redis 整体缩放 + DB 分批折算；每行按自己的基准折算，可中断续跑且幂等。"""
    target = cache.media_hot_reference_time(at_time)
    changed = cache.refresh_hot_reference(target)
    batch = []
    queryset = Media.objects.filter(hot_value_updated_at__lt=target).only('id', 'hot_value', 'hot_value_updated_at')
    for media in queryset.iterator(chunk_size=batch_size):
        media.hot_value *= decay(media.hot_value_updated_at, target)
        media.hot_value_updated_at = target
        batch.append(media)
        if len(batch) >= batch_size:
            Media.objects.bulk_update(batch, ['hot_value', 'hot_value_updated_at'])
            batch = []
    if batch:
        Media.objects.bulk_update(batch, ['hot_value', 'hot_value_updated_at'])
    logger.info('Media hot reference refreshed: redis_changed=%s target=%s', changed, target.isoformat())
    return changed
