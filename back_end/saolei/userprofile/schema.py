from typing import Literal, Self

from ninja import Field, Schema
from ninja.orm import create_schema
from pydantic import model_validator

from msuser.models import UserMS
from .models import UserProfile


USER_INFO_FIELDS = [
    'id', 'username',
    'signature', 'country',
    'is_banned', 'is_staff',
    'last_change_avatar', 'last_change_signature',
    'left_avatar_n', 'left_signature_n',
]
PUBLIC_NAME_FIELDS = [('realname', str, ...), ('firstname', str, ...), ('lastname', str, ...)]


class RawUserNames(Schema):
    @staticmethod
    def resolve_realname(user):
        return user._realname

    @staticmethod
    def resolve_firstname(user):
        return user._firstname

    @staticmethod
    def resolve_lastname(user):
        return user._lastname


UserInfoOut = create_schema(
    UserProfile, name='UserInfoOut', fields=USER_INFO_FIELDS, custom_fields=PUBLIC_NAME_FIELDS,
)
SelfUserInfoOut = create_schema(
    UserProfile, name='SelfUserInfoOut', fields=[*USER_INFO_FIELDS, 'can_hide_realname', 'hide_realname'],
    custom_fields=PUBLIC_NAME_FIELDS, base_class=RawUserNames,
)


UserVideoStatisticsOut = create_schema(
    UserMS, name='UserVideoStatisticsOut',
    fields=['video_num_total', 'video_num_tournament', 'video_num_all', 'video_size_total', 'video_size_tournament', 'video_size_all'],
)


class UserDirectoryOutBase(Schema):
    @staticmethod
    def resolve_statistics(user: UserProfile):
        if user.userms is not None:
            return user.userms
        return {
            'video_num_total': 0, 'video_num_tournament': 0, 'video_num_all': 0,
            'video_size_total': 0, 'video_size_tournament': 0, 'video_size_all': 0,
        }


UserDirectoryOut = create_schema(
    UserProfile, name='UserDirectoryOut', fields=['id', 'date_joined'],
    custom_fields=[('statistics', UserVideoStatisticsOut, ...), ('accounts', dict[Literal['c', 'a', 'w', 'm'], str], ...)],
    base_class=UserDirectoryOutBase,
)


class UserDirectoryPageOut(Schema):
    count: int
    users: list[UserDirectoryOut]


class UserDirectoryQuery(Schema):
    page: int = Field(1, ge=1, le=2147483647)
    page_size: int = Field(20, ge=1, le=100)
    sort: Literal['id', 'video_num_total', 'video_num_tournament', 'video_num_all', 'video_size_total', 'video_size_tournament', 'video_size_all'] = 'id'
    reverse: bool = False
    platform: Literal['', 'c', 'a', 'w', 'm'] = ''
    id: str = Field('', max_length=128)

    @model_validator(mode='after')
    def validate_id(self) -> Self:
        if not self.id:
            return self
        if self.platform == 'm':
            if len(self.id) > 64:
                raise ValueError('Mineracer ID must be at most 64 characters.')
        else:
            if not self.id.isascii() or not self.id.isdigit():
                raise ValueError('ID must contain only digits.')
            if not self.platform and not 1 <= int(self.id) <= 9223372036854775807:
                raise ValueError('Site ID must be a positive 64-bit integer.')
        return self
