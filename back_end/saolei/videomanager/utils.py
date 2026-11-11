import hashlib
import math
from pathlib import PurePosixPath

from timeout_decorator import timeout

from config.customranking import CUSTOM_PLUCK_LEVELS, CUSTOM_PLUCK_MODES
from utils.parser import create_video_from_data
from .config import PLUCK_TIMEOUT_SECONDS


def pack_compression_format(container_version, algorithm_id, algorithm_version):
    return (container_version << 24) | (algorithm_id << 16) | algorithm_version


def unpack_compression_format(format_code):
    return ((format_code >> 24) & 0xFF, (format_code >> 16) & 0xFF, format_code & 0xFFFF)


def replay_filename(file_name, original_filename=None):
    return original_filename or PurePosixPath(file_name.replace('\\', '/')).name


def calculate_original_hash(file) -> str:
    """计算完整原始文件的 96 位摘要，并复位文件流供解析和保存使用。"""
    file.seek(0)
    try:
        return hashlib.file_digest(file, 'sha256').digest()[:12].hex()
    finally:
        file.seek(0)


class VideoParseError(Exception):
    """单条录像解析失败，可以跳过该录像继续刷新。"""


def is_custom_pluck_video(video) -> bool:
    return (
        video.level in CUSTOM_PLUCK_LEVELS
        and video.mode in CUSTOM_PLUCK_MODES
    )


def normalize_pluck(value) -> float | None:
    if value is None:
        return None
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        return None
    return value


def _calculate_pluck(file_path: str, data=None):
    if data is None:
        with open(file_path, 'rb') as file:
            data = file.read()

    parsed_video, _ = create_video_from_data(file_path, data)
    parsed_video.parse()
    parsed_video.analyse()
    parsed_video.analyse_for_features(['pluck'])
    parsed_video.current_time = 1e8
    return parsed_video.pluck


calculate_pluck = timeout(
    PLUCK_TIMEOUT_SECONDS,
    use_signals=False,
    timeout_exception=TimeoutError,
)(_calculate_pluck)


class VideoQueryError(ValueError):
    """录像检索请求参数不合法，由 API 层转换成 400。"""


VIDEO_QUERY_LIMIT = 1000
VIDEO_QUERY_MAX_IN_VALUES = 32
VIDEO_QUERY_MAX_VALUE_LENGTH = 128
VIDEO_QUERY_ALLOWED_PARAMS = frozenset({'filters', 'sorts'})
VIDEO_QUERY_OPS = frozenset({'eq', 'in', 'gte', 'gt', 'lte', 'lt'})
VIDEO_QUERY_LOWER_OPS = frozenset({'gte', 'gt'})
VIDEO_QUERY_UPPER_OPS = frozenset({'lte', 'lt'})
VIDEO_QUERY_LOOKUPS = {'eq': 'exact', 'in': 'in', 'gte': 'gte', 'gt': 'gt', 'lte': 'lte', 'lt': 'lt'}
VIDEO_QUERY_INT_FIELDS = frozenset({'id', 'file_size', 'stored_file_size', 'timems', 'bv', 'left', 'right', 'double', 'cl', 'left_ce', 'right_ce', 'double_ce', 'ce', 'flag', 'op', 'isl', 'cell0', 'cell1', 'cell2', 'cell3', 'cell4', 'cell5', 'cell6', 'cell7', 'cell8'})
VIDEO_QUERY_FLOAT_FIELDS = frozenset({'bvs', 'left_s', 'right_s', 'double_s', 'cl_s', 'left_ces', 'right_ces', 'double_ces', 'ce_s', 'path', 'pluck', 'flag_s', 'ioe', 'thrp', 'corr', 'stnb'})
VIDEO_QUERY_DATETIME_FIELDS = frozenset({'upload_time', 'end_time'})
VIDEO_QUERY_ENUM_FIELDS = frozenset({'state', 'software', 'level', 'mode'})
VIDEO_QUERY_DERIVED_FIELDS = frozenset({'stnb'})
VIDEO_QUERY_FILTER_FIELDS = VIDEO_QUERY_INT_FIELDS | VIDEO_QUERY_FLOAT_FIELDS | VIDEO_QUERY_DATETIME_FIELDS | VIDEO_QUERY_ENUM_FIELDS | VIDEO_QUERY_DERIVED_FIELDS
VIDEO_QUERY_SORT_FIELDS = frozenset({'id', 'level', 'mode', 'state', 'timems', 'bv', 'bvs', 'thrp', 'stnb'})
VIDEO_QUERY_STNB_LEVELS = frozenset({'b', 'i', 'e'})
