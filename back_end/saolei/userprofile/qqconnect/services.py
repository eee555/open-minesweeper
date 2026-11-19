import re
import secrets

from django.db import IntegrityError, transaction

from msuser.models import UserMS
from utils import verify_text
from .utils import qq_error
from ..forms import account_email
from ..models import EmailVerifyRecord, QQConnectIdentity, UserProfile
from ..services import judge_email_verification


def update_profile(identity, data):
    fields = ['date_updated']
    for field in ('nickname', 'avatar_url', 'unionid'):
        if data.get(field):
            setattr(identity, field, data[field])
            fields.append(field)
    identity.save(update_fields=fields)


def bind_identity(user, data):
    try:
        with transaction.atomic():
            identity, _ = QQConnectIdentity.objects.get_or_create(parent=user, defaults=data)
            if (identity.appid, identity.openid) != (data['appid'], data['openid']):
                raise qq_error('already_linked', 409)
            update_profile(identity, data)
            return identity
    except IntegrityError:
        raise qq_error('conflict', 409) from None


def register_identity(data):
    try:
        with transaction.atomic():
            user = UserProfile.objects.create_user(
                username=f'qq_{secrets.token_hex(10)}', email=f'qq-{secrets.token_hex(16)}@accounts.invalid',
                password=None, userms=UserMS.objects.create(), is_active=True,
            )
            QQConnectIdentity.objects.create(parent=user, **data)
            return user
    except IntegrityError:
        raise qq_error('conflict', 409) from None


def has_recovery(user):
    return user.has_usable_password() or not user.email.lower().endswith('@accounts.invalid')


def can_set_username(user):
    return bool(re.fullmatch(r'qq_[0-9a-f]{20}', user.username))


def prepare_username(user, value, user_ip):
    value = user._meta.get_field('username').clean(value.strip().strip('ㅤ'), user)
    if re.fullmatch(r'qq_[0-9a-f]{20}', value):
        raise qq_error('invalid_username')
    try:
        allowed = verify_text(value, user.pk, user_ip)
    except Exception:
        raise qq_error('username_unavailable', 503) from None
    if not allowed:
        raise qq_error('username_rejected')
    return value


def set_username(user, value):
    if not can_set_username(user):
        raise qq_error('username_readonly', 409)
    try:
        with transaction.atomic():
            user.username = value
            user.save(update_fields=['username', 'date_updated'])
    except IntegrityError:
        raise qq_error('username_used', 409) from None


def unlink_identity(user):
    if not has_recovery(user):
        raise qq_error('last_login_method', 409)
    QQConnectIdentity.objects.filter(parent=user).delete()


@transaction.atomic
def bind_recovery_email(user, email, email_key, email_captcha):
    email = account_email(email)
    if not judge_email_verification(email, email_captcha, email_key):
        raise qq_error('email_code', 400)
    try:
        with transaction.atomic():
            user.email = email
            user.save(update_fields=['email', 'date_updated'])
    except IntegrityError:
        raise qq_error('email_used', 409) from None
    EmailVerifyRecord.objects.filter(hashkey=email_key).delete()
