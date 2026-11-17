from datetime import datetime

from captcha.models import CaptchaStore
from django.core.exceptions import ValidationError
from django.utils import timezone


HIDDEN_NAME = 'hidden'
NAME_FIELDS = {'realname': '_realname', 'firstname': '_firstname', 'lastname': '_lastname'}


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
