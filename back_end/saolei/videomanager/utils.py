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
