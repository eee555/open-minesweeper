from datetime import datetime
from enum import StrEnum

from captcha.models import CaptchaStore
from django.core.exceptions import ValidationError
from django.utils import timezone


HIDDEN_NAME = 'hidden'
NAME_FIELDS = {'realname': '_realname', 'firstname': '_firstname', 'lastname': '_lastname'}


class UserLanguage(StrEnum):
    ZH_CN = 'zh-cn'
    EN = 'en'
    ES = 'es'


class EmailNotificationType(StrEnum):
    STAFF_MEDIA_REVIEW = 'staff_media_review'
    STAFF_VIDEO_FROZEN = 'staff_video_frozen'
    STAFF_VIDEO_PLAIN = 'staff_video_plain'
    STAFF_ACCOUNT_LINK_REVIEW = 'staff_account_link_review'
    STAFF_IDENTIFIER_UNSAFE = 'staff_identifier_unsafe'


EMAIL_NOTIFICATION_FLAGS = {
    EmailNotificationType.STAFF_MEDIA_REVIEW: 1,
    EmailNotificationType.STAFF_VIDEO_FROZEN: 2,
    EmailNotificationType.STAFF_VIDEO_PLAIN: 4,
    EmailNotificationType.STAFF_ACCOUNT_LINK_REVIEW: 8,
    EmailNotificationType.STAFF_IDENTIFIER_UNSAFE: 16,
}


def has_identity_access(user) -> bool:
    """实名或玩家认证满足其一即具备身份准入，管理身份本身不算准入。"""
    return user.has_realname() or user.verified


def validate_name(value):
    if value.strip() == HIDDEN_NAME:
        raise ValidationError('The name cannot be the reserved value hidden.', code='reserved')


# 验证验证码
def judge_captcha(captchaStr: str, captchaHashkey):
    if captchaStr and captchaHashkey:
        get_captcha = CaptchaStore.objects.filter(
            hashkey=captchaHashkey).first()
        if get_captcha and get_captcha.response == captchaStr.lower():
            # 图形验证码15分钟有效，get_captcha.expiration是过期时间
            if (get_captcha.expiration - timezone.now()).seconds >= 0:
                CaptchaStore.objects.filter(hashkey=captchaHashkey).delete()
                return True
    CaptchaStore.objects.filter(hashkey=captchaHashkey).delete()
    return False


def count_new_avatar_chance(old: datetime, new: datetime):
    return new.year - old.year


def count_new_signature_chance(old: datetime, new: datetime):
    return 12 * (new.year - old.year) + (new.month - old.month)
