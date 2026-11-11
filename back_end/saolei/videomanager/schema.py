from ninja import Schema
from ninja.orm import create_schema

from .models import VideoModel

VIDEO_INFO_BATCH_LIMIT = 100
PARSED_VIDEO_FIELDS = [
    'software', 'level', 'mode', 'end_time', 'file_size', 'timems', 'bv',
    'left', 'right', 'double', 'left_ce', 'right_ce', 'double_ce',
    'path', 'pluck', 'flag', 'op', 'isl',
    'cell0', 'cell1', 'cell2', 'cell3', 'cell4', 'cell5', 'cell6', 'cell7', 'cell8',
]
PUBLIC_VIDEO_METADATA_FIELDS = ['id', 'player', 'upload_time', 'state']
VIDEO_METADATA_FIELDS = [*PUBLIC_VIDEO_METADATA_FIELDS, 'ongoing_tournament']


class ParsedVideoResolvers(Schema):
    @staticmethod
    def resolve_identifier(video):
        return video.video.identifier

    @staticmethod
    def resolve_tournament_identifier(video):
        return video.video.tournament_identifier


ParsedVideoOut = create_schema(
    VideoModel,
    name='ParsedVideoOut',
    fields=['id', 'ongoing_tournament', *PARSED_VIDEO_FIELDS],
    custom_fields=[('identifier', str, ''), ('tournament_identifier', list[str], [])],
    base_class=ParsedVideoResolvers,
)
VideoMetadataOut = create_schema(VideoModel, name='VideoMetadataOut', fields=VIDEO_METADATA_FIELDS)
PublicVideoMetadataOut = create_schema(VideoModel, name='PublicVideoMetadataOut', fields=PUBLIC_VIDEO_METADATA_FIELDS)


VideoBaseOut = create_schema(
    VideoModel,
    fields=[
        'id', 'player',
        'software', 'level', 'mode', 'state',
        'cl', 'ce', 'right_ce', 'timems', 'bv',
        'upload_time', 'end_time',
    ],
    custom_fields=[('cl', int | None, None), ('ce', int | None, None)],
)

VideoQueryItemOut = create_schema(
    VideoModel,
    name='VideoQueryItemOut',
    fields=['id', 'upload_time', 'state', 'ongoing_tournament'],
    custom_fields=[('player_id', int, ...), ('player__realname', str, ...)],
)


class VideoQueryOut(Schema):
    videos: list[VideoQueryItemOut]
