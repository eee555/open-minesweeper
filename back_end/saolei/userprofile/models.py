import os

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_cleanup import cleanup

from config.global_settings import DefaultChances, MaxSizes
from msuser.models import UserMS
from .fields import RestrictedImageField
from .utils import HIDDEN_NAME

username_validator = UnicodeUsernameValidator()


# 自定义用户
# 头像修改后，自动删除服务器上原来的图片
@cleanup.select
class UserProfile(AbstractUser):
    userms = models.OneToOneField(
        UserMS, on_delete=models.CASCADE, related_name='parent', null=True)

    date_updated = models.DateTimeField(auto_now=True)
    is_memorial = models.BooleanField(default=False)

    username = models.CharField(
        _('username'),
        max_length=MaxSizes.USERNAME,
        unique=True,
        help_text=_(
            f'Required. {MaxSizes.USERNAME} characters or fewer. Letters, digits and @/./+/-/_ only.',
        ),
        validators=[username_validator],
        error_messages={
            'max_length': _(f'用户名的长度不超过{MaxSizes.USERNAME}，支持各国语言！'),
            'unique': _('该用户名已存在！'),
        }, db_collation='utf8mb4_0900_as_cs',
    )
    _firstname = models.CharField(_('first name'), db_column='firstname', max_length=MaxSizes.FIRSTNAME, blank=True)
    _lastname = models.CharField(_('last name'), db_column='lastname', max_length=MaxSizes.LASTNAME, blank=True)
    email = models.EmailField(
        _('email address'),
        max_length=MaxSizes.EMAIL,
        unique=True,
        blank=False,
        null=False,
        error_messages={
            'blank': _('必须填写邮箱！'),
            'invalid': _('邮箱格式不正确！'),
            'unique': _('该邮箱已被注册！'),
            'max_length': _(f'邮箱的长度不能超过{MaxSizes.EMAIL}！'),
        },
    )
    # 考虑了中英文、俄罗斯用户名字，长度需要达到100（虽然还不够）
    _realname = models.CharField(
        db_column='realname', max_length=MaxSizes.REALNAME, unique=False, blank=True, default='匿名', null=False)
    can_hide_realname = models.BooleanField(default=False)
    hide_realname = models.BooleanField(default=False)
    # 头像
    avatar = RestrictedImageField(upload_to='avatar/%Y%m%d/', max_length=100,
                                  max_upload_size=MaxSizes.AVATAR, blank=True, null=True)
    # 签名
    signature = models.TextField(max_length=MaxSizes.SIGNATURE, blank=True, default='')  # 签名
    country = models.CharField(max_length=MaxSizes.COUNTRY, blank=True, default='')
    # 封禁用户，禁止上传录像、头像、签名
    is_banned = models.BooleanField(default=False, blank=False)
    # 剩余修改真实姓名的次数，0~32767
    left_realname_n = models.PositiveSmallIntegerField(null=False, default=DefaultChances.NAME)
    # 剩余修改头像次数，0~32767
    left_avatar_n = models.PositiveSmallIntegerField(null=False, default=DefaultChances.AVATAR)
    # 最近修改头像时间
    last_change_avatar = models.DateTimeField(auto_now_add=True)
    # 剩余修改签名次数，0~32767
    left_signature_n = models.PositiveSmallIntegerField(null=False, default=DefaultChances.SIGNATURE)
    # 最近修改签名时间
    last_change_signature = models.DateTimeField(auto_now_add=True)
    # 人气
    popularity = models.BigIntegerField(null=False, default=0)
    # vip，0为非vip，理论0~32767。类似于权限
    vip = models.PositiveSmallIntegerField(null=False, default=0)

    def delete(self, *args, **kwargs):
        # 删除关联的文件
        if self.avatar:
            # 使用os库删除文件
            if os.path.isfile(self.avatar.path):
                os.remove(self.avatar.path)

        # 调用父类的delete方法删除数据库记录
        super(UserProfile, self).delete(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(is_memorial=False) | models.Q(is_active=False, is_staff=False, is_superuser=False, password__startswith='!', email__endswith='@accounts.invalid'),
                name='memorial_auth_disabled',
            ),
        ]
        indexes = [
            models.Index(fields=['date_updated'], name='date_updated_idx'),
            models.Index(fields=['country'], name='country_idx'),
            models.Index(fields=['vip'], name='vip_idx'),
        ]

    def clean(self):
        super().clean()
        if self.is_memorial and (self.is_active or self.is_staff or self.is_superuser or self.has_usable_password() or not self.email.endswith('@accounts.invalid')):
            raise ValidationError('Memorial accounts must remain inactive, without credentials or administrative permissions.')

    def save(self, *args, update_fields=None, **kwargs):
        if self.is_memorial:
            self.clean()
        return super().save(*args, update_fields=update_fields, **kwargs)

    def has_realname(self) -> bool:
        return bool(self._realname.strip()) and self._realname.strip() != '匿名'

    @property
    def is_name_hidden(self) -> bool:
        return self.has_realname() and self.can_hide_realname and self.hide_realname

    @property
    def realname(self):
        return HIDDEN_NAME if self.is_name_hidden else self._realname

    @realname.setter
    def realname(self, value):
        self._realname = value

    @property
    def firstname(self):
        return HIDDEN_NAME if self.is_name_hidden else self._firstname

    @firstname.setter
    def firstname(self, value):
        self._firstname = value

    @property
    def lastname(self):
        return HIDDEN_NAME if self.is_name_hidden else self._lastname

    @lastname.setter
    def lastname(self, value):
        self._lastname = value


# 邮箱验证
class EmailVerifyRecord(models.Model):
    # 验证码
    code = models.CharField(max_length=MaxSizes.EMAILCODE, verbose_name='验证码')
    email = models.EmailField(max_length=MaxSizes.EMAIL, verbose_name='邮箱')
    # 包含注册验证和找回验证
    # send_type = models.CharField(verbose_name="验证码类型", max_length=10,
    #                              choices=(("register", "注册"), ("forget", "找回密码")))
    send_time = models.DateTimeField(verbose_name='发送时间', auto_now_add=True)
    hashkey = models.CharField(max_length=40, unique=True, default='???')

    class Meta:
        verbose_name = u'2. 邮箱验证码'
        verbose_name_plural = verbose_name

    def __unicode__(self):
        return '{0}({1})'.format(self.code, self.email)
