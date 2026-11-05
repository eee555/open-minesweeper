from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from django.core.files import File
import ms_toollib as ms

from config.customranking import CUSTOM_PLUCK_LEVELS, CUSTOM_PLUCK_MODES
from config.text_choices import MS_TextChoices
from .exceptions import ExceptionToResponse

logger = logging.getLogger(__name__)
PARSER_TIMEOUT_SECONDS = 60


def _parse_isolated(file: File) -> dict:
    """只在子进程中执行原生解析；不继承调用者的数据库连接或事务。"""
    file.seek(0)
    try:
        data = file.read()
    finally:
        file.seek(0)
    with TemporaryDirectory(prefix='replay-parser-') as directory:
        result_path = Path(directory) / 'result.json'
        try:
            result = subprocess.run(
                [sys.executable, '-X', 'faulthandler', '-m', 'utils.parser_process', Path(file.name).suffix, str(result_path)],
                cwd=Path(__file__).resolve().parents[1], input=data, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=PARSER_TIMEOUT_SECONDS, check=False,
            )
        except subprocess.TimeoutExpired:
            logger.error('Replay parser timed out: filename=%r timeout=%s', file.name, PARSER_TIMEOUT_SECONDS)
            raise ExceptionToResponse('rust', 'panic', 500) from None
        if result.returncode:
            logger.error('Replay parser exited: filename=%r exit_code=%s diagnostics=%s', file.name, result.returncode, result.stdout[-8192:].decode('utf-8', errors='replace'))
            raise ExceptionToResponse('rust', 'panic', 500)
        try:
            payload = json.loads(result_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            logger.exception('Replay parser returned an invalid result: filename=%r', file.name)
            raise ExceptionToResponse('rust', 'panic', 500) from None
    if 'error' in payload:
        raise ExceptionToResponse(**payload['error'])
    metadata = payload['metadata']
    metadata['end_time'] = datetime.fromisoformat(metadata['end_time'])
    return metadata


def pack_custom_level(rows, columns, mines) -> str:
    if rows is None or columns is None or mines is None:
        raise ExceptionToResponse(obj='file', category='level')
    return f'c{rows}_{columns}_{mines}'


def create_video_from_data(file_name: str, data: bytes):
    if file_name.endswith('.avf'):
        return ms.AvfVideo(raw_data=data), MS_TextChoices.Software.AVF
    elif file_name.endswith('.evf'):
        return ms.EvfVideo(raw_data=data), MS_TextChoices.Software.EVF
    elif file_name.endswith('.rmv'):
        return ms.RmvVideo(raw_data=data), MS_TextChoices.Software.RMV
    elif file_name.endswith('.mvf'):
        return ms.MvfVideo(raw_data=data), MS_TextChoices.Software.MVF
    else:
        raise ExceptionToResponse(obj='file', category='type')


def normalize_pluck(value) -> float | None:
    if value is None:
        return None
    value = float(value)
    if not math.isfinite(value) or value < 0:
        return None
    return value


def is_standard_level(level: str) -> bool:
    return level in [
        MS_TextChoices.Level.BEGINNER,
        MS_TextChoices.Level.INTERMEDIATE,
        MS_TextChoices.Level.EXPERT,
    ]


def supports_pluck(level: str, mode: str) -> bool:
    return (
        is_standard_level(level)
        or (level in CUSTOM_PLUCK_LEVELS and mode in CUSTOM_PLUCK_MODES)
    )


def calculate_pluck_from_video(v: ms.BaseVideo, level: str, mode: str) -> float | None:
    if not supports_pluck(level, mode):
        return None
    v.analyse_for_features(['pluck'])
    return normalize_pluck(v.pluck)


class MSVideoParser:
    file: File

    software: MS_TextChoices.Software
    level: MS_TextChoices.Level
    mode: MS_TextChoices.Mode

    state: MS_TextChoices.State
    identifier: str
    tournament_identifier: list[str]
    tournament_identifiers: list[str]
    end_time: datetime

    timems: int
    bv: int

    left: int
    right: int
    double: int

    left_ce: int
    right_ce: int
    double_ce: int

    path: float
    flag: int
    op: int
    isl: int

    cell0: int
    cell1: int
    cell2: int
    cell3: int
    cell4: int
    cell5: int
    cell6: int
    cell7: int
    cell8: int

    pluck: float | None

    def __init__(self, file: File, *, isolate=False):
        self.file = file
        if isolate:
            self.__dict__.update(_parse_isolated(file))
            self.tournament_identifiers = self.tournament_identifier
            return

        v, self.software = MSVideoParser.read_file(file)

        v.parse()
        v.analyse()
        if not v.is_completed:
            raise ExceptionToResponse(obj='file', category='incomplete')
        v.current_time = 1e8

        self.level = MSVideoParser.get_level_from_BaseVideo(v)
        self.mode = MSVideoParser.get_mode_from_BaseVideo(v, self.software)
        self.pluck = calculate_pluck_from_video(v, self.level, self.mode)

        try:
            self.state = MSVideoParser.get_state_from_review_code(v.is_valid())
        except BaseException as e:
            if e.__class__.__name__ == 'PanicException':
                raise ExceptionToResponse(obj='rust', category='panic')
            else:
                raise e
        self.identifier = v.player_identifier
        self.tournament_identifiers = [
            identifier
            for identifier in v.race_identifier.split(',')
            if identifier
        ]
        self.tournament_identifier = self.tournament_identifiers
        self.end_time = datetime.fromtimestamp(v.end_time / 1000000, tz=timezone.utc)

        self.timems = v.rtime_ms
        self.bv = v.bbbv

        self.left = v.left
        self.right = v.right
        self.double = v.double

        self.left_ce = v.lce
        self.right_ce = v.rce
        self.double_ce = v.dce

        self.path = v.path
        self.flag = v.flag
        self.op = v.op
        self.isl = v.isl

        self.cell0 = v.cell0
        self.cell1 = v.cell1
        self.cell2 = v.cell2
        self.cell3 = v.cell3
        self.cell4 = v.cell4
        self.cell5 = v.cell5
        self.cell6 = v.cell6
        self.cell7 = v.cell7
        self.cell8 = v.cell8

    @staticmethod
    def read_file(file: File):
        data = file.read()
        file.seek(0)
        return create_video_from_data(file.name, data)

    @staticmethod
    def get_level_from_BaseVideo(v: ms.BaseVideo):
        if v.level == 3:
            return MS_TextChoices.Level.BEGINNER
        elif v.level == 4:
            return MS_TextChoices.Level.INTERMEDIATE
        elif v.level == 5:
            return MS_TextChoices.Level.EXPERT
        elif v.level == 6:
            rows = getattr(v, 'row', None)
            columns = getattr(v, 'column', None)
            mines = getattr(v, 'mine_num', None)
            return pack_custom_level(rows, columns, mines)
        else:
            raise ExceptionToResponse(obj='file', category='level')

    @staticmethod
    def get_mode_from_BaseVideo(v: ms.BaseVideo, software: MS_TextChoices.Software):
        if software != MS_TextChoices.Software.EVF:
            return MS_TextChoices.Mode.STD
        return str(v.mode).rjust(2, '0')

    @staticmethod
    def get_state_from_review_code(review_code: int):
        if review_code == 0:
            return MS_TextChoices.State.OFFICIAL
        elif review_code == 1:
            return MS_TextChoices.State.FROZEN
        elif review_code == 3:
            return MS_TextChoices.State.PLAIN
        else:
            raise ExceptionToResponse(obj='file', category='review')

    @staticmethod
    def parse_video_metadata(file: File):
        data = file.read()
        v, software = create_video_from_data(file.name, data)

        v.parse()
        v.analyse()
        if not v.is_completed:
            raise ExceptionToResponse(obj='file', category='incomplete')
        v.current_time = 1e8

        level = MSVideoParser.get_level_from_BaseVideo(v)
        mode = MSVideoParser.get_mode_from_BaseVideo(v, software)
        pluck = calculate_pluck_from_video(v, level, mode)

        review_code = v.is_valid()
        state = MSVideoParser.get_state_from_review_code(review_code)
        identifier = v.player_identifier

        tournament_identifiers = [
            tournament_identifier
            for tournament_identifier in v.race_identifier.split(',')
            if tournament_identifier
        ]

        return {
            'identifier': identifier,
            'tournament_identifier': tournament_identifiers,
            'end_time': datetime.fromtimestamp(v.end_time / 1000000, tz=timezone.utc),
            'software': software,
            'level': level,
            'mode': mode,
            'state': state,
            'timems': v.rtime_ms,
            'bv': v.bbbv,
            'left': v.left,
            'right': v.right,
            'double': v.double,
            'left_ce': v.lce,
            'right_ce': v.rce,
            'double_ce': v.dce,
            'path': v.path,
            'pluck': pluck,
            'flag': v.flag,
            'op': v.op,
            'isl': v.isl,
            'cell0': v.cell0,
            'cell1': v.cell1,
            'cell2': v.cell2,
            'cell3': v.cell3,
            'cell4': v.cell4,
            'cell5': v.cell5,
            'cell6': v.cell6,
            'cell7': v.cell7,
            'cell8': v.cell8,
        }
