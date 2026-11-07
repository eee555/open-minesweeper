from typing import Literal

from ninja import Field, Schema

from userprofile.schema import SelfUserInfoOut
from videomanager.schema import VideoMetadataOut


class AutoLoginOut(Schema):
    user: SelfUserInfoOut | None
    top_anchors: dict


class TaskQuery(Schema):
    page: int = Field(1, ge=1, le=2147483647)
    page_size: int = Field(20, ge=1, le=100)
    status: Literal['', 'READY', 'RUNNING', 'SUCCESSFUL', 'FAILED'] = ''
    task_path: str = Field('', max_length=255)
    sort: Literal['enqueued_at', 'started_at', 'finished_at', 'priority', 'run_after'] = 'enqueued_at'
    reverse: bool = True


class AnalyzerRankOut(Schema):
    ranking: str
    stat: str
    nf: bool
    rank: int


class AnalyzerWebsiteInfoOut(Schema):
    video: VideoMetadataOut
    tournament_ids: list[int]
    filename: str
    rankings: list[AnalyzerRankOut]
