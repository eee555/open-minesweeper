import json
import logging
from uuid import uuid4

from django.db.models import QuerySet
from django_redis import get_redis_connection
from redis.exceptions import RedisError

from config.text_choices import MS_TextChoices
from utils import ComplexEncoder
from .config import SHARE_PREVIEW_CACHE_LIMIT, SHARE_PREVIEW_CLEANUP_TTL
from .models import VideoModel

cache = get_redis_connection('saolei_website')
NEWEST_QUEUE_LIMIT = 1000
logger = logging.getLogger('videomanager')
SHARE_PREVIEW_COUNT_KEY = 'video:share-preview:count'
SHARE_PREVIEW_PENDING_KEY = 'video:share-preview:cleanup-pending'


def reserve_share_preview_cleanup(*, created=False):
    """Approximate count and best-effort enqueue deduplication; never an execution lock."""
    try:
        raw = cache.get(SHARE_PREVIEW_COUNT_KEY)
        try:
            count = int(raw) if raw is not None else -1
        except ValueError:
            count = -1
        needs_calibration = count < 0
        if created:
            if needs_calibration:
                cache.set(SHARE_PREVIEW_COUNT_KEY, 1)
                count = 1
            else:
                count = cache.incr(SHARE_PREVIEW_COUNT_KEY)
        if needs_calibration or count >= SHARE_PREVIEW_CACHE_LIMIT:
            token = uuid4().hex
            if cache.set(SHARE_PREVIEW_PENDING_KEY, token, nx=True, ex=SHARE_PREVIEW_CLEANUP_TTL):
                return token
    except RedisError:
        logger.exception('Failed to track share preview cache usage')
    return None


def release_share_preview_cleanup(token):
    if token is None:
        return
    try:
        if cache.get(SHARE_PREVIEW_PENDING_KEY) == token.encode('ascii'):
            cache.delete(SHARE_PREVIEW_PENDING_KEY)
    except RedisError:
        logger.exception('Failed to clear share preview cleanup marker')


def set_share_preview_count(count):
    try:
        cache.set(SHARE_PREVIEW_COUNT_KEY, count)
    except RedisError:
        logger.exception('Failed to calibrate share preview cache count')


def decrement_share_preview_count():
    try:
        cache.decr(SHARE_PREVIEW_COUNT_KEY)
    except RedisError:
        logger.exception('Failed to decrement share preview cache count')


def serialize_video_to_queue(video: VideoModel):
    return {
        'state': video.state,
        'time': video.upload_time,
        'player_id': video.player_id,
    }


class VideoQueueCache:
    key: str

    def __init__(self, key: str):
        self.key = key

    def trim(self):
        if cache.hlen(self.key) <= NEWEST_QUEUE_LIMIT:
            return 0
        values = cache.hgetall(self.key)
        ordered_ids = sorted(values, key=lambda video_id: (json.loads(values[video_id])['time'], int(video_id)), reverse=True)
        removed_ids = ordered_ids[NEWEST_QUEUE_LIMIT:]
        return cache.hdel(self.key, *removed_ids) if removed_ids else 0

    def add(self, video: VideoModel):
        if video.ongoing_tournament:
            return
        cache.hset(self.key, video.id, json.dumps(serialize_video_to_queue(video), cls=ComplexEncoder))

    def add_bulk(self, videos):
        mapping = {
            video.id: json.dumps(serialize_video_to_queue(video), cls=ComplexEncoder)
            for video in videos
            if not video.ongoing_tournament
        }
        if mapping:
            cache.hset(self.key, mapping=mapping)

    def update_bulk(self, videos):
        videos = [video for video in videos if not video.ongoing_tournament]
        video_ids = [video.id for video in videos]
        if not video_ids:
            return

        cached_values = cache.hmget(self.key, video_ids)
        mapping = {
            video.id: json.dumps(serialize_video_to_queue(video), cls=ComplexEncoder)
            for video, cached_value in zip(videos, cached_values)
            if cached_value is not None
        }
        if mapping:
            cache.hset(self.key, mapping=mapping)

    def remove(self, video: VideoModel):
        cache.hdel(self.key, video.id)

    def remove_bulk(self, videos):
        video_ids = [video.id for video in videos]
        if video_ids:
            cache.hdel(self.key, *video_ids)


newest_cache = VideoQueueCache('newest_queue')


def add_videos_to_state_queues_bulk(videos: QuerySet[VideoModel]):
    """按录像状态批量恢复普通队列。"""
    newest_cache.add_bulk(videos.filter(state__in=[MS_TextChoices.State.OFFICIAL, MS_TextChoices.State.IDENTIFIER]))
