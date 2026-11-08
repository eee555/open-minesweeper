"""作品页数据模型：Media / MediaLikes / UserMedia；见 MEDIA_PLAN.md 第 4、16 节。"""

from django.db import models
from django.utils import timezone

from userprofile.models import UserProfile
from .utils import MediaFormat, MediaStatus


class Media(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='media_works')
    title = models.CharField(max_length=200)
    language = models.CharField(max_length=32, blank=True, default='')
    created_at = models.DateTimeField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    format = models.CharField(max_length=3, choices=MediaFormat.choices)
    suffix = models.CharField(max_length=128)
    status = models.CharField(max_length=8, choices=MediaStatus.choices, default=MediaStatus.PENDING)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='media_rejections')
    reject_reason = models.CharField(max_length=200, blank=True)
    refunded_likes = models.PositiveBigIntegerField(default=0)
    likes = models.PositiveBigIntegerField(default=0)
    hot_value = models.FloatField(default=0)
    hot_value_updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['format', 'suffix'], name='media_format_suffix_unique'),
        ]
        indexes = [
            models.Index(fields=['status', '-submitted_at'], name='media_pending_idx'),
            models.Index(fields=['user', '-hot_value'], name='media_user_hot_idx'),
            models.Index(fields=['user', '-likes'], name='media_user_likes_idx'),
            models.Index(fields=['user', '-created_at'], name='media_user_created_idx'),
            models.Index(fields=['title'], name='media_title_idx'),
            models.Index(fields=['status', '-created_at', '-id'], name='media_latest_idx'),
        ]


class MediaLikes(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='media_likes')
    media = models.ForeignKey(Media, on_delete=models.CASCADE, related_name='like_records')
    likes = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'media'], name='media_likes_user_media_unique'),
        ]


class UserMedia(models.Model):
    user = models.OneToOneField(UserProfile, primary_key=True, on_delete=models.CASCADE, related_name='media_profile')
    likes_sent = models.PositiveBigIntegerField(default=0)
    banned = models.BooleanField(default=False)
