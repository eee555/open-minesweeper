from config.text_choices import MS_TextChoices
from utils.exceptions import ExceptionToResponse
from utils.parser import MSVideoParser
from utils.ranking_lock import ranking_access
from .files import original_file
from .models import ExpandVideoModel, VideoModel
from .utils import VideoParseError

video_all_fields = [
    'id', 'upload_time', 'player__id', 'player__realname', 'timems', 'bv', 'bvs', 'state', 'level', 'mode', 'software', 'flag', 'op', 'isl', 'path', 'pluck', 'left', 'right', 'double', 'left_ce', 'right_ce',
    'double_ce', 'cell0', 'cell1', 'cell2', 'cell3', 'cell4', 'cell5', 'cell6', 'cell7', 'cell8', 'left_s', 'right_s', 'double_s', 'left_ces', 'right_ces', 'double_ces', 'flag_s', 'ioe', 'thrp', 'cl_s', 'ce_s',
]
for name in [field.name for field in ExpandVideoModel._meta.get_fields()]:
    video_all_fields.append('video__' + name)


@ranking_access(operation='videomanager.refresh_video')
def refresh_video(video: VideoModel):
    try:
        replay = original_file(video.file.name, video.compression_format, video.original_filename) if video.compression_format else video.file
        try:
            parser = MSVideoParser(replay)
            new_size = replay.size
        finally:
            replay.close()
    except (ValueError, RuntimeError, EOFError, OverflowError, ExceptionToResponse) as exc:
        raise VideoParseError(str(exc)) from exc

    parser_fields = [
        'level', 'mode', 'software', 'end_time', 'timems', 'bv',
        'left', 'right', 'double',
        'left_ce', 'right_ce', 'double_ce',
        'path', 'pluck', 'flag', 'op', 'isl',
        'cell0', 'cell1', 'cell2', 'cell3', 'cell4',
        'cell5', 'cell6', 'cell7', 'cell8',
    ]

    updated_fields = []

    # 1. 处理 parser 字段
    for field in parser_fields:
        new_value = getattr(parser, field)
        old_value = getattr(video, field)
        if new_value != old_value:
            setattr(video, field, new_value)
            updated_fields.append(field)

    # 2. 处理 file_size（独立来源）
    if new_size != video.file_size:
        video.file_size = new_size
        updated_fields.append('file_size')

    # 3. 仅当有字段变更时才保存
    if updated_fields:
        video.save(update_fields=updated_fields)

    e_video = video.video
    e_updated_fields = []
    if e_video.identifier != parser.identifier:
        e_video.identifier = parser.identifier
        e_updated_fields.append('identifier')
    if e_video.tournament_identifier != parser.tournament_identifier:
        e_video.tournament_identifier = parser.tournament_identifier
        e_updated_fields.append('tournament_identifier')

    if e_updated_fields:
        e_video.save(update_fields=e_updated_fields)

    if video.state == MS_TextChoices.State.IDENTIFIER and (e_video.identifier in video.player.userms.identifiers):
        video.state = MS_TextChoices.State.OFFICIAL
        video.save(update_fields=['state'])
