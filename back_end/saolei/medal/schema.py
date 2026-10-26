from datetime import date, datetime
from typing import Literal

from ninja import Schema
from ninja.orm import create_schema
from pydantic import Field, StrictInt

from .models import MedalDefinition, MedalGrant, MedalOverride, MedalOverrideLog


class RefreshStatusOut(Schema):
    user_id: int
    pending: bool


class CatalogItemOut(Schema):
    code: str
    series: str
    subseries: str
    kind: str
    metric: str
    direction: str
    level: str
    style: str
    thresholds: list[int]
    hidden: bool
    annotation: str


class MedalItemOut(Schema):
    code: str
    series: str
    subseries: str
    kind: str
    stage: int | None
    stage_count: int
    direction: str
    current_value: int | None
    next_threshold: int | None
    granted_at: datetime | None
    video_id: int | None
    tournament_id: int | None
    rank: int | None
    hidden: bool
    annotation: str
    score: int
    grant_id: int | None
    scope_key: str
    thresholds: list[int]


class SeriesOut(Schema):
    series: str
    items: list[MedalItemOut]


class PlayerMedalOut(Schema):
    scan_pending: bool
    score: int
    max_pins: int
    pin_ids: list[int]
    pins: list[MedalItemOut]
    series: list[SeriesOut]


class PlayerStateGrantOut(Schema):
    code: str
    stage: int
    timestamp: int | None
    scope: str
    tournament: int | None
    rank: int | None


class PlayerStateOut(Schema):
    user_id: int
    grants: list[PlayerStateGrantOut]


class GrantPageOut(Schema):
    count: int
    page: int
    page_size: int
    items: list[MedalItemOut]


class PinsIn(Schema):
    grant_ids: list[int]


class PinsOut(Schema):
    pin_ids: list[int]


class StaffGrantIn(Schema):
    code: str = Field(min_length=1, max_length=64)
    user_id: int
    reason: str = Field(min_length=1, max_length=255)
    granted_on: date
    stage: StrictInt | None = Field(default=None, ge=1)
    scope_key: str = Field(default='', max_length=128)


class GrantIdOut(Schema):
    id: int


class RevokeIn(Schema):
    reason: str = Field(min_length=1, max_length=255)


class RebuildIn(Schema):
    user_id: int


class EnqueuedOut(Schema):
    enqueued: bool


StaffCatalogItemOut = create_schema(
    MedalDefinition, name='StaffCatalogItemOut',
    fields=['code', 'series', 'subseries', 'kind', 'metric', 'direction', 'level', 'style', 'thresholds', 'active', 'hidden'],
    custom_fields=[('thresholds', list[int], ...)],
)
StaffMedalGrantOut = create_schema(
    MedalGrant, name='StaffMedalGrantOut',
    fields=['id', 'definition_code', 'scope_key', 'stage', 'granted_at', 'revoked_at', 'revoke_reason'],
)
StaffMedalOverrideOut = create_schema(
    MedalOverride, name='StaffMedalOverrideOut',
    fields=['id', 'definition_code', 'scope_key', 'mode', 'stage', 'reason', 'updated_at'],
    custom_fields=[('actor_id', int | None, None)],
)
StaffMedalHistoryOut = create_schema(
    MedalOverrideLog, name='StaffMedalHistoryOut',
    fields=['id', 'definition_code', 'scope_key', 'action', 'stage', 'reason', 'created_at'],
    custom_fields=[('actor_id', int | None, None)],
)


class StaffPlayerMedalsOut(Schema):
    user_id: int
    username: str
    grants: list[StaffMedalGrantOut]
    overrides: list[StaffMedalOverrideOut]
    history: list[StaffMedalHistoryOut]


class StaffOverrideIn(Schema):
    user_id: int
    code: str = Field(min_length=1, max_length=64)
    scope_key: str = Field(default='', max_length=128)
    mode: Literal['grant', 'revoke', 'auto']
    reason: str = Field(min_length=1, max_length=255)
    stage: StrictInt | None = Field(default=None, ge=1)
    granted_on: date | None = None


class StaffOverrideOut(Schema):
    grant_id: int | None
    mode: Literal['grant', 'revoke', 'auto']
    enqueued: bool
