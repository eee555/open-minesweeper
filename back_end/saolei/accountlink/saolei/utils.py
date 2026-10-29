from datetime import datetime, timezone

from saolei_api import ResponseError, Video

SUPPORTED_SOFTWARE = frozenset({'Clone', 'Vienna', 'Arbiter', '元扫雷3.3.4'})
LEVELS = {'beg': 'b', 'int': 'i', 'exp': 'e'}


def video_defaults(video: Video, account_id: int) -> dict:
    if video.id <= 0 or video.user_id != account_id or video.real_time < 0 or video.board_3bv < 0:
        raise ResponseError('Invalid video metadata or player ID')
    return {
        'upload_time': datetime.fromtimestamp(video.upload_time, timezone.utc),
        'level': LEVELS[video.level], 'bv': video.board_3bv, 'timems': video.real_time,
        'nf': video.nf, 'software': video.software, 'status': video.status,
    }
