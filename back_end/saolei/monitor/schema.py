from datetime import datetime
from typing import Literal

from ninja import Schema
from pydantic import NonNegativeInt


class VideoSummaryOut(Schema):
    sampled_at: datetime
    total: int
    software: dict[str, int]
    level: dict[str, int]
    mode: dict[str, int]
    state: dict[str, int]


class TaskCountsOut(Schema):
    total: int
    status: dict[str, int]


class TaskSummaryOut(TaskCountsOut):
    sampled_at: datetime


class DiskUsageOut(Schema):
    sampled_at: datetime
    total: int
    used: int
    free: int
    video: int | None
    db: int | None


class MemorySectionOut(Schema):
    status: Literal['ready', 'unavailable']
    sampled_at: datetime | None
    reason: Literal['permission_denied', 'unsupported_metric', 'unsupported_scope', 'budget_exceeded', 'metadata_unavailable', 'inconsistent_snapshot', 'redis_unavailable', 'database_unavailable', 'collection_failed'] | None
    total_bytes: NonNegativeInt | None


class ProcessGroupsOut(Schema):
    uwsgi: NonNegativeInt
    apscheduler: NonNegativeInt
    redis: NonNegativeInt
    mysql: NonNegativeInt
    db_worker: NonNegativeInt
    other: NonNegativeInt


class HostMemoryOut(Schema):
    total_bytes: NonNegativeInt
    available_bytes: NonNegativeInt


class ProcessMemoryOut(MemorySectionOut):
    metric: Literal['pss', 'rss']
    groups: ProcessGroupsOut | None
    host: HostMemoryOut | None
    unreadable_processes: NonNegativeInt


class RedisGroupsOut(Schema):
    pb_rankings: NonNegativeInt
    other_rankings: NonNegativeInt
    latest_videos: NonNegativeInt
    other: NonNegativeInt


class RedisMemoryOut(MemorySectionOut):
    metric: Literal['redis_allocated']
    groups: RedisGroupsOut | None
    estimated: Literal[True]
    samples: Literal[5]


class MemoryUsageOut(Schema):
    memory: ProcessMemoryOut
    redis: RedisMemoryOut


class MonitorSnapshotOut(Schema):
    videosummary: VideoSummaryOut | None = None
    tasksummary: TaskSummaryOut | None = None
    diskusage: DiskUsageOut | None = None
    memoryusage: MemoryUsageOut | None = None
