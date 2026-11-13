"""作品页业务逻辑：投稿、投喂、审核、驳回、恢复与硬删除；见 MEDIA_PLAN.md 附录 A。"""

import logging
from math import floor

from django.db import IntegrityError, transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.utils import timezone

from . import cache
from .models import Media, MediaLikes, UserMedia
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


def sync_media_scores(media_id, author_id):
    """请求路径：DB 事务提交后按 DB 绝对值覆盖四个 zset；失败只记日志。

    DB 用 T_db、zset 用 T_r，折算因子是 decay(T_db, T_r)。业务已提交，任何同步失败
    都不能让请求失败：不回滚、不入队后台任务、不补偿，残留漂移由低频管理命令纠正。
    """
    try:
        factor = cache.reference_factor()
        user_hot = 0.0
        user_likes = 0
        has_works = False
        media_hot = None
        media_likes = 0
        rows = Media.objects.filter(user_id=author_id, status=MediaStatus.VERIFIED).values_list(
            'pk', 'hot_value', 'likes',
        )
        for pk, hot_value, likes in rows:
            has_works = True
            score = hot_value * factor
            user_hot += score
            user_likes += likes
            if pk == media_id:
                media_hot, media_likes = score, likes
        cache.set_media_scores(media_id, author_id, media_hot, media_likes, user_hot, user_likes, has_works)
    except Exception:
        logger.exception(
            'media ranking cache sync failed: media_id=%s author_id=%s; DB is authoritative, '
            'run refresh_media_rankings to reconcile',
            media_id, author_id,
        )


def create_media(user, *, media_format, suffix, language, title='', created_at=None, metadata_pending=False):
    """投稿落库：唯一约束防重复外链；外站元数据拉取与归属校验由 API 层完成。

    metadata_pending=True 表示外站不可用时的降级投稿，标题由管理员审核时补录；
    外站作者 id 只用于 API 层一次性归属核验，不传给 service、不入库。
    """
    try:
        with transaction.atomic():
            media = Media.objects.create(
                user=user, title=title, language=language, created_at=created_at or timezone.now(),
                format=media_format, suffix=suffix, metadata_pending=metadata_pending,
                status=MediaStatus.PENDING, likes=0, hot_value=0,
                hot_value_updated_at=cache.read_db_hot_reference(),
            )
    except IntegrityError:
        raise MediaServiceError('该作品已投稿过，不可重复投稿', 409) from None
    sync_media_scores(media.pk, user.pk)
    return media


def like_media(user, media_id):
    """投喂 1 个红宝石：先锁作品再锁用户（与驳回/硬删除一致），按 UTC 自然日限 10 次成功投喂。

    热度增量按全局 T_db 折算 delta_hot = 1 / decay(T_db, now)，不固定加 1；缓存由请求
    路径在事务提交后按 DB 绝对值覆盖。daily_date / daily_likes 与 likes_sent 在同一事务
    内更新，事务回滚即不计数。驳回与硬删除只退还 likes_sent，不回退当日已用次数（16.1 第 17 条）。
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
        status, author_id = media.status, media.user_id
        hot_now = media.hot_value * factor
        result = {'likes': media.likes, 'hot_now': hot_now, 'balance': balance - 1, 'status': status}
    if status == MediaStatus.VERIFIED:
        sync_media_scores(media_id, author_id)
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
    logger.info('Staff #%s verified media #%s: likes=%s hot_value=%s', actor_id, media_id, likes, hot)
    sync_media_scores(media_id, author_id)
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
    """站长硬删除：仅 verified，退还红宝石、写快照日志并按剩余作品绝对值覆盖四个 zset。"""
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
    sync_media_scores(media_id, author_id)
    return True


def set_media_banned(user_id, banned):
    profile, _ = UserMedia.objects.get_or_create(user_id=user_id)
    profile.banned = banned
    profile.save(update_fields=['banned'])
    return profile
