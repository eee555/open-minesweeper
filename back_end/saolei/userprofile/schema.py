from datetime import datetime
from typing import Literal, Self

from ninja import Field, Schema
from ninja.orm import create_schema
from pydantic import model_validator

from msuser.models import UserMS
from .models import UserProfile
from .utils import has_identity_access


USER_INFO_FIELDS = [
    'id', 'username',
    'signature', 'country',
    'is_banned', 'is_staff', 'is_memorial', 'verified',
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


class SelfUserInfoOutBase(RawUserNames):
    @staticmethod
    def resolve_can_submit_replays(user: UserProfile) -> bool:
        return has_identity_access(user)


SelfUserInfoOut = create_schema(
    UserProfile, name='SelfUserInfoOut', fields=[*USER_INFO_FIELDS, 'can_hide_realname', 'hide_realname', 'is_superuser'],
    custom_fields=[*PUBLIC_NAME_FIELDS, ('can_submit_replays', bool, False)], base_class=SelfUserInfoOutBase,
)


class VerificationStatusOut(Schema):
    verified: bool
    can_submit_replays: bool
    can_verify: bool
    maintenance_active: bool


class VerificationActionOut(Schema):
    target_id: int
    verified: bool
    edge_created: bool
    nodes_updated: int


class SetVerifiedOut(Schema):
    user_id: int
    verified: bool
    nodes_updated: int


class VerificationEdgeOut(Schema):
    from_user_id: int
    to_user_id: int
    created_at: datetime


class MaintenanceStateOut(Schema):
    active: bool
    owner_id: int | None
    expires_at: datetime | None
    owned_by_requester: bool


class GraphSnapshotOut(Schema):
    edges: list[VerificationEdgeOut]
    verified_user_ids: list[int]
    maintenance: MaintenanceStateOut


class GraphNodeOut(Schema):
    user_id: int
    verified: bool
    in_edges: list[int]
    out_edges: list[int]


class GraphUpdateResultOut(Schema):
    added_edges: int
    removed_edges: int
    updated_nodes: int


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
    UserProfile, name='UserDirectoryOut', fields=['id', 'date_joined', 'is_memorial'],
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
