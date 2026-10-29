from functools import partial

from django.db import transaction

from utils.querysets import player_batches
from videomanager.models import VideoModel
from .cache import pipeline
from .nf_ioe import services as nf_ioe
from .nf_ioe.cache import NFIOERankingCache
from .nf_ioe.utils import is_eligible
from .thrp.cache import ThrpRankingCache
from .thrp.nf_services import refresh_expert_nf_records
from .thrp.services import prepare_add_videos, prepare_remove_videos, prepare_video_update, VIDEO_FIELDS, write_records
from .thrp.utils import is_expert_nf
from .utils import log_update_errors


def _read_records(rankings, players):
    players = list(players)
    with pipeline() as pipe:
        for ranking in rankings:
            pipe.hmget(ranking.detail_key, players)
        rows = pipe.execute()
    return {ranking.ranking_name: ranking.parse_records(players, raw) for ranking, raw in zip(rankings, rows)}


def _sync_video(video_id: int, previous_video: dict, ranking_names: set[str]):
    with log_update_errors('sync_video', video_id=video_id, previous_player_id=previous_video['player_id']):
        video = VideoModel.objects.filter(pk=video_id).values(*set(VIDEO_FIELDS + nf_ioe.VIDEO_FIELDS)).first()
        players = {previous_video['player_id']}
        if video:
            players.add(video['player_id'])
        rankings = []
        if 'thrp' in ranking_names:
            rankings.append(ThrpRankingCache())
        if 'nf_ioe' in ranking_names and (is_eligible(previous_video) or is_eligible(video)):
            rankings.append(NFIOERankingCache())
        if not rankings:
            return
        previous = _read_records(rankings, players)
        if 'thrp' in previous:
            thrp_records = prepare_video_update(video, video_id, previous['thrp'])
            nf_players = {item['player_id'] for item in (previous_video, video) if is_expert_nf(item)}
            refresh_expert_nf_records(thrp_records, nf_players)
        if 'nf_ioe' in previous:
            ioe_records = nf_ioe.prepare_video_update(video, video_id, previous['nf_ioe'])
        with pipeline() as pipe:
            if 'thrp' in previous:
                write_records(ThrpRankingCache(), previous['thrp'], thrp_records, pipe=pipe)
            if 'nf_ioe' in previous:
                nf_ioe.write_records(NFIOERankingCache(), previous['nf_ioe'], ioe_records, pipe=pipe)
            pipe.execute()


def sync_video(video_id: int, previous_video: dict, ranking_names: set[str]):
    """数据库提交后读取持久化的派生成绩，再刷新受影响玩家。"""
    transaction.on_commit(partial(_sync_video, video_id, previous_video, ranking_names))


def _update_videos(videos, remove: bool):
    with log_update_errors('remove_videos' if remove else 'add_videos'):
        ranking = ThrpRankingCache()
        ioe_ranking = NFIOERankingCache()
        for players in player_batches(videos, 100):
            subset = videos.filter(player_id__in=players)
            previous = _read_records([ranking, ioe_ranking], players)
            records = prepare_remove_videos(subset, previous['thrp']) if remove else prepare_add_videos(subset, previous['thrp'])
            refresh_expert_nf_records(records, players)
            ioe_records = nf_ioe.prepare_remove_videos(subset, previous['nf_ioe']) if remove else nf_ioe.prepare_add_videos(subset, previous['nf_ioe'])
            with pipeline() as pipe:
                write_records(ranking, previous['thrp'], records, pipe=pipe)
                nf_ioe.write_records(ioe_ranking, previous['nf_ioe'], ioe_records, pipe=pipe)
                pipe.execute()


def add_videos_to_eff_ranks(videos):
    """批量吸收获得排行资格的录像，不逐条触发保存信号。"""
    transaction.on_commit(partial(_update_videos, videos.all(), False))


def remove_videos_from_eff_ranks(videos):
    """批量失效后补位，调用方传入由固定录像 id 定位的 queryset。"""
    transaction.on_commit(partial(_update_videos, videos.all(), True))
