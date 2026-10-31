from typing import Annotated

from ninja import Field, Schema
from ninja.orm import create_schema

from userprofile.models import UserProfile
from userprofile.schema import PUBLIC_NAME_FIELDS
from videomanager.schema import VideoBaseOut


IdentifierText = Annotated[str, Field(max_length=128)]

MemorialUserOut = create_schema(
    UserProfile, name='MemorialUserOut', fields=['id', 'username', 'is_memorial'],
    custom_fields=[('userms_id', int, ...), *PUBLIC_NAME_FIELDS],
)


class UploadAccessOut(Schema):
    csrf_token: str
    user: MemorialUserOut


class IdentifierOut(Schema):
    identifier: str
    bound: bool
    error: str | None = None


class UploadResultOut(Schema):
    video: VideoBaseOut
    bindings: list[IdentifierOut]
