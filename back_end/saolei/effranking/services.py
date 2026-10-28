from functools import partial

from django.db import transaction

from utils.querysets import player_batches
from videomanager.models import VideoModel
from .thrp.cache import ThrpRankingCache
from .thrp.nf_services import refresh_expert_nf_records
from .thrp.services import prepare_add_videos, prepare_remove_videos, prepare_video_update, VIDEO_FIELDS, write_records
from .thrp.utils import is_expert_nf
from .utils import log_update_errors


def _sync_video(video_id: int, previous_video: dict):
    with log_update_errors('sync_video', video_id=video_id, previous_player_id=previous_video['player_id']):
        video = VideoModel.objects.filter(pk=video_id).values(*VIDEO_FIELDS).first()
        players = {previous_video['player_id']}
        if video:
            players.add(video['player_id'])
        ranking = ThrpRankingCache()
        previous = ranking.read_records(players)
        records = prepare_video_update(video, video_id, previous)
        nf_players = {item['player_id'] for item in (previous_video, video) if is_expert_nf(item)}
        refresh_expert_nf_records(records, nf_players)
        write_records(ranking, previous, records)


def sync_video(video_id: int, previous_video: dict):
    """数据库提交后读取持久化的派生成绩，再刷新受影响玩家。"""
    transaction.on_commit(partial(_sync_video, video_id, previous_video))


def _update_videos(videos, remove: bool):
    with log_update_errors('remove_videos' if remove else 'add_videos'):
        ranking = ThrpRankingCache()
        for players in player_batches(videos, 100):
            subset = videos.filter(player_id__in=players)
            previous = ranking.read_records(players)
            records = prepare_remove_videos(subset, previous) if remove else prepare_add_videos(subset, previous)
            refresh_expert_nf_records(records, players)
            write_records(ranking, previous, records)


def add_videos_to_eff_ranks(videos):
    """批量吸收获得排行资格的录像，不逐条触发保存信号。"""
    transaction.on_commit(partial(_update_videos, videos.all(), False))


def remove_videos_from_eff_ranks(videos):
    """批量失效后补位，调用方传入由固定录像 id 定位的 queryset。"""
    transaction.on_commit(partial(_update_videos, videos.all(), True))
