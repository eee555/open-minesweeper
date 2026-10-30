from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import msrc

from .config import MAX_COMPRESSION_MEMORY_KIB, MAX_REPLAY_BYTES
from .utils import pack_compression_format, replay_filename


class CompressionConfigurationError(Exception):
    """依赖无法生成指定的目标格式，停止整批转换。"""


def original_file(file_name, compression_format=0, original_filename=None):
    with default_storage.open(file_name, 'rb') as source:
        data = source.read()
    if compression_format:
        data = msrc.decompress(data, max_output_size=MAX_REPLAY_BYTES, max_memory_kib=MAX_COMPRESSION_MEMORY_KIB)
    return ContentFile(data, name=replay_filename(file_name, original_filename))


def validate_compression_target(target):
    container_version, algorithm_id, algorithm_version = target
    if (container_version, algorithm_id) != (1, 1) or algorithm_version not in (1, 2):
        raise CompressionConfigurationError(f'Unsupported MSRC target: {target}')


def compress_original(data, target):
    validate_compression_target(target)
    algorithm_version = target[2]
    if len(data) > MAX_REPLAY_BYTES:
        raise ValueError('Replay exceeds decompression output limit')
    archive = msrc.compress(data, algorithm_version=algorithm_version)
    info = msrc.inspect(archive)
    actual = (info.container_version, info.algorithm_id, info.algorithm_version)
    if actual != target:
        raise CompressionConfigurationError(f'MSRC returned {actual}, expected {target}')
    restored = msrc.decompress(archive, max_output_size=MAX_REPLAY_BYTES, max_memory_kib=MAX_COMPRESSION_MEMORY_KIB)
    if restored != data:
        raise ValueError('Compressed replay does not restore the original bytes')
    return archive, pack_compression_format(*actual)
