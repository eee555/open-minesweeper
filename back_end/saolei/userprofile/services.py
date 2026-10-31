
from datetime import datetime, timezone
import logging
from typing import Literal
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction

from msuser.models import UserMS
from speedranking.saolei.cache import SpeedRankingCache
from utils import generate_code, verify_text
from utils.exceptions import ExceptionToResponse
from videomanager.models import VideoModel
from .forms import UserRegisterForm
from .models import EmailVerifyRecord, UserProfile
from .utils import count_new_avatar_chance, count_new_signature_chance, NAME_FIELDS, validate_name

logger = logging.getLogger('userprofile')


NAME_DEFAULT = {
    'realname': '匿名',
    'firstname': '',
    'lastname': '',
}


@transaction.atomic
def clear_profile_info(user: UserProfile):
    user.realname = ''
    user.signature = ''
    user.avatar = None
    user.save(update_fields=['_realname', 'signature', 'avatar', 'date_updated'])


def register_user(data: dict[str, str], user_ip: str) -> UserProfile:
    form = UserRegisterForm(data=data)
    if not form.is_valid():
        raise ExceptionToResponse('register', 'validation')
    if not judge_email_verification(form.cleaned_data['email'], data['email_captcha'], data['email_key']):
        raise ExceptionToResponse('emailcode', 'invalid')

    user = form.save(commit=False)
    try:
        is_valid = verify_text(user.username, 0, user_ip)
    except Exception:
        raise ExceptionToResponse('censorship', 'unknown')
    if not is_valid:
        raise ExceptionToResponse('censorship', 'illegal')

    user.set_password(form.cleaned_data['password'])
    user.is_active = True
    with transaction.atomic():
        user.userms = UserMS.objects.create()
        user.save()  # noqa: DJM100 - creating a new user
        EmailVerifyRecord.objects.filter(hashkey=data['email_key']).delete()
    logger.info('User %s#%s registered', user.username, user.pk)
    return user


def try_update_user_name_fields(user: UserProfile, field_name: Literal['realname', 'firstname', 'lastname'], field_value: str, user_ip: str):
    model_field = NAME_FIELDS[field_name]
    field_value = clean_user_name(user, field_name, field_value)
    old_value = getattr(user, model_field)
    if old_value == field_value:
        return

    if old_value != NAME_DEFAULT[field_name] and not (field_name == 'realname' and not user.has_realname()):
        raise ExceptionToResponse('name', 'exist')

    try:
        is_valid = verify_text(field_value, user.id, user_ip)
    except Exception:
        raise ExceptionToResponse('censorship', 'unknown')

    if not is_valid:
        raise ExceptionToResponse('censorship', 'illegal')

    setattr(user, model_field, field_value)
    try:
        user.save(update_fields=[model_field, 'date_updated'])
    except ValidationError:
        raise ExceptionToResponse('database', 'validation')

    logger.info(f'用户 {user.username}#{user.id} 设置 {field_name} 为 "{field_value}"')
    return


def clean_user_name(user: UserProfile, field_name: str, value: str) -> str:
    value = value.strip()
    try:
        validate_name(value)
    except ValidationError:
        raise ExceptionToResponse('name', 'reserved', status_code=400)
    try:
        return user._meta.get_field(NAME_FIELDS[field_name]).clean(value, user)
    except ValidationError:
        raise ExceptionToResponse('database', 'validation', status_code=400)


def apply_privacy(user: UserProfile, hide: bool):
    if hide and not user.has_realname():
        raise ExceptionToResponse('privacy', 'realname_required', status_code=403)
    if hide and not user.can_hide_realname:
        raise ExceptionToResponse('privacy', 'not_authorized', status_code=403)
    user.hide_realname = hide


@transaction.atomic
def update_user_names(user_id: int, names: dict, user_ip: str, hide: bool | None = None) -> UserProfile:
    user = UserProfile.objects.select_for_update().get(pk=user_id)
    old_hide = user.hide_realname
    # Validate the whole name group before any write, including reserved values.
    names = {field: clean_user_name(user, field, value) for field, value in names.items()}
    for field, value in names.items():
        try_update_user_name_fields(user, field, value, user_ip)
    if hide is not None:
        apply_privacy(user, hide)
    elif not user.has_realname():
        user.hide_realname = False
    user.save(update_fields=['hide_realname', 'date_updated'])
    logger.info('User #%s updated name privacy: %s -> %s', user.pk, old_hide, user.hide_realname)
    return user


def grant_name_privacy(user: UserProfile, actor: str):
    """The caller holds the user row lock and commits the binding in its transaction."""
    old = user.can_hide_realname
    user.can_hide_realname = True
    user.save(update_fields=['can_hide_realname', 'date_updated'])
    logger.info('%s granted name privacy to user #%s: %s -> True', actor, user.pk, old)


@transaction.atomic
def update_admin_profile(user_id: int, updates: dict, actor: UserProfile) -> UserProfile:
    user = UserProfile.objects.select_for_update().get(pk=user_id)
    if user.is_memorial and 'email' in updates and updates['email'] != user.email:
        raise ExceptionToResponse('memorial', 'email_readonly', status_code=400)
    old_privacy = (user.can_hide_realname, user.hide_realname)
    fields = []
    for field, value in updates.items():
        if field in NAME_FIELDS:
            value = clean_user_name(user, field, value)
        model_field = NAME_FIELDS.get(field, field)
        setattr(user, model_field, value)
        fields.append(model_field)
    if not user.can_hide_realname or not user.has_realname():
        user.hide_realname = False
        fields.append('hide_realname')
    if updates:
        user.save(update_fields=[*set(fields), 'date_updated'])
        logger.warning('Staff #%s updated user #%s fields %s; privacy %s -> %s', actor.pk, user.pk, list(updates), old_privacy, (user.can_hide_realname, user.hide_realname))
    return user


def has_sub200_expert_video(user: UserProfile) -> bool:
    """头像和签名资格跟随 Saolei.wang 的 et 纪录（包括 3BV 门槛）。"""
    record = SpeedRankingCache('saolei').get_record(user.id)
    et = record['et'] if record else None
    return et is not None and et < 200000


def try_update_user_signature(user: UserProfile, signature: str, user_ip: str):
    if user.signature == signature:
        return

    if not has_sub200_expert_video(user):
        raise ExceptionToResponse('signature', 'expTime')

    refresh_signature_chance(user)
    if user.left_signature_n <= 0:
        raise ExceptionToResponse('signature', 'cooldown')

    try:
        is_valid = verify_text(signature, user.id, user_ip)
    except Exception:
        raise ExceptionToResponse('censorship', 'unknown')

    if not is_valid:
        raise ExceptionToResponse('censorship', 'illegal')

    user.signature = signature
    user.left_signature_n -= 1
    try:
        user.save(update_fields=['signature', 'left_signature_n', 'date_updated'])
    except ValidationError:
        raise ExceptionToResponse('database', 'validation')

    return


# 发送邮件，根据send_type不同发送不同的邮件内容
def send_email(email: str, send_type='register'):
    if email.lower().endswith('@accounts.invalid'):
        return None
    email_record = EmailVerifyRecord()
    if settings.E2E_TEST:
        code = 'abcdef'
    else:
        code = generate_code(6)
    email_record.code = code
    # email_record.email = email
    hashkey = uuid.uuid4()
    email_record.hashkey = hashkey
    email_record.email = email
    # email_record.send_type = send_type
    email_record.save()  # noqa: DJM100

    # 验证码保存之后，我们就要把带有验证码的链接发送到注册时的邮箱！
    if settings.E2E_TEST:
        return hashkey
    if settings.EMAIL_SKIP:
        return code, hashkey
    if send_type == 'register':
        email_title = '开源扫雷网邮箱注册验证码'
        email_body = f'欢迎您注册开源扫雷网，您的邮箱验证码为：{code}（一小时内有效）。'
    elif send_type == 'retrieve':
        email_title = '开源扫雷网找回密码验证码'
        email_body = f'您正在找回密码。您的邮箱验证码为：{code}（一小时内有效）。请勿与任何人分享此代码，我们的管理员永远不会向您索要此代码。'
    else:
        return None
    send_status = send_mail(email_title, email_body, 'wangjianing@88.com', [email])
    if send_status:
        return hashkey
    else:
        return None


def judge_email_verification(email, email_captcha, emailHashkey):
    if not emailHashkey or not email or not email_captcha:
        return False
    get_email_captcha = EmailVerifyRecord.objects.filter(hashkey=emailHashkey).first()
    if not get_email_captcha:
        return False
    if (datetime.now(timezone.utc) - get_email_captcha.send_time).seconds > 3600:
        EmailVerifyRecord.objects.filter(hashkey=emailHashkey).delete()
        return False
    return get_email_captcha.code == email_captcha and get_email_captcha.email == email


def user_metadata(user: UserProfile, client):
    queryset = VideoModel.objects.filter(player=user)
    if client != user:
        queryset = queryset.filter(ongoing_tournament=False)
    videos = queryset.values('id', 'upload_time', 'level', 'mode', 'timems', 'bv', 'state', 'software', 'cl', 'ce', 'right_ce', 'file_size', 'end_time', 'ongoing_tournament', 'path')
    return {
        'id': user.id,
        'username': user.username,
        'realname': user._realname,
        'firstname': user._firstname,
        'lastname': user._lastname,
        'can_hide_realname': user.can_hide_realname,
        'hide_realname': user.hide_realname,
        'signature': user.signature,
        'popularity': user.popularity,
        'identifiers': user.userms.identifiers,
        'is_banned': user.is_banned,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser if client == user else False,
        'is_memorial': user.is_memorial,
        'country': user.country,
        'videos': list(videos),
    }


def refresh_avatar_chance(user: UserProfile):
    now = datetime.now(timezone.utc)
    new_avatar = count_new_avatar_chance(user.last_change_avatar, now)

    if new_avatar > 0:
        user.left_avatar_n += new_avatar
        user.last_change_avatar = now
        user.save(update_fields=['left_avatar_n', 'last_change_avatar', 'date_updated'])

    return


def refresh_signature_chance(user: UserProfile):
    now = datetime.now(timezone.utc)
    new_signature = count_new_signature_chance(user.last_change_signature, now)

    if new_signature > 0:
        user.left_signature_n += new_signature
        user.last_change_signature = now
        user.save(update_fields=['left_signature_n', 'last_change_signature', 'date_updated'])

    return
