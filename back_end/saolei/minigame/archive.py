from io import BytesIO
import json

from py7zr import FILTER_LZMA2, SevenZipFile
from py7zr.io import BytesIOFactory


def pack_replay(replay):
    output = BytesIO()
    with SevenZipFile(output, 'w', filters=[{'id': FILTER_LZMA2, 'preset': 1, 'dict_size': 1 << 20}]) as archive:
        archive.writestr(json.dumps(replay, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8'), 'replay.json')
    return output.getvalue()


def unpack_replay(data):
    factory = BytesIOFactory(limit=64 * 1024 * 1024)
    with SevenZipFile(BytesIO(bytes(data)), 'r') as archive:
        if archive.getnames() != ['replay.json'] or archive.needs_password():
            raise ValueError('Expected an unencrypted archive containing only replay.json')
        archive.extractall(factory=factory)
    replay = json.loads(factory.get('replay.json').read())
    if not isinstance(replay, dict):
        raise ValueError('Expected a replay JSON object')
    return replay
