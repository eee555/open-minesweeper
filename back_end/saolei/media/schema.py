"""作品页输入/输出 Schema；见 MEDIA_PLAN.md 第 7、8 节。"""

from datetime import datetime

from django.utils import timezone
from ninja import Field, Schema
from ninja.orm import create_schema

from .models import Media
from .utils import build_embed_url, build_external_url, real_hot

MEDIA_QUERY_LIMIT = 1000


class MediaResolvers(Schema):
    @staticmethod
    def resolve_user_id(media):
        return media.user_id

    @staticmethod
    def resolve_rejected_by(media):
        return media.rejected_by_id

    @staticmethod
    def resolve_url(media):
        return build_external_url(media.format, media.suffix)

    @staticmethod
    def resolve_embed_url(media):
        return build_embed_url(media.format, media.suffix)

    @staticmethod
    def resolve_hot_now(media):
        return real_hot(media, getattr(media, '_hot_now_at', None) or timezone.now())


MEDIA_OUT_FIELDS = [
    'id', 'title', 'language', 'created_at', 'submitted_at', 'format', 'status',
    'rejected_at', 'reject_reason', 'refunded_likes', 'likes', 'hot_value',
    'hot_value_updated_at', 'metadata_pending',
]

MediaOut = create_schema(
    Media,
    name='MediaOut',
    fields=MEDIA_OUT_FIELDS,
    custom_fields=[
        ('user_id', int, ...),
        ('rejected_by', int | None, None),
        ('url', str, ...),
        ('embed_url', str | None, None),
        ('hot_now', float, ...),
    ],
    base_class=MediaResolvers,
)


class MediaPageOut(Schema):
    items: list[MediaOut]
    total: int
    start: int
    anchor: datetime


class MediaQueryOut(Schema):
    items: list[MediaOut]
    total: int


class MediaQueryError(Schema):
    code: str
    detail: str


class UserRankRowOut(Schema):
    user_id: int
    hot: float
    likes: float


class UserRankingPageOut(Schema):
    items: list[UserRankRowOut]
    total: int
    start: int
    anchor: datetime


class MeOut(Schema):
    balance: int
    likes_sent: int
    banned: bool


class LikeOut(Schema):
    likes: int
    hot_now: float
    balance: int
    status: str


class DeletedOut(Schema):
    deleted: bool


class SubmitIn(Schema):
    url: str
    language: str = ''


class LikeIn(Schema):
    media_id: int
    count: int = Field(..., ge=1, le=100)


class IdIn(Schema):
    id: int


class VerifyIn(Schema):
    id: int
    title: str | None = None
    external_author_id: str | None = None
    created_at: datetime | None = None


class RejectIn(Schema):
    id: int
    reason: str = ''


class BanIn(Schema):
    user_id: int


class EditIn(Schema):
    id: int
    title: str | None = None
    language: str | None = None
    created_at: datetime | None = None
    url: str | None = None
