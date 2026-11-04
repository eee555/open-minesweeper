from functools import partial
import json

from django.db import transaction

from news.services import emit, PB_NEWS_TOP_N
from utils.querysets import player_batches
from utils.ranking_lock import ranking_access
from videomanager.models import VideoModel
from .cache import pipeline
from .pb import services as pb
from .pb.cache import PBRankingCache
from .saolei import services as saolei
from .saolei.utils import RANKING_NAMES
from .top import services as top
from .top.cache import TopRankingCache
from .utils import log_update_errors


def _read_records(players):
    players = list(players)
    with pipeline() as pipe:
        saolei.read_records(pipe, players)
        PBRankingCache().read_records(pipe, players)
        TopRankingCache().read_records(pipe, players)
        results = pipe.execute()
    split = len(RANKING_NAMES)
    return saolei.unpack_records(results[:split], players), PBRankingCache().unpack_records(results[split:split + len(players)], players), TopRankingCache.unpack_records(results[-1], players)


def _publish_pb_news(old_pb, pb_changes, ranking):
    """PB 刷新后，只有终点仍在前 10 的事件才附带旧/新成绩、录像与名次。"""
    candidates = [(player_id, field) for (player_id, field), candidate in pb_changes.items() if candidate is not None]
    if not candidates:
        return
    with pipeline() as pipe:
        for player_id, field in candidates:
            pipe.hget(ranking.player_key(player_id), field)
        rows = pipe.execute()
    for (player_id, field), raw in zip(candidates, rows):
        if raw is None:
            continue
        new = json.loads(raw)
        if new.get('rank') is None or new['rank'] > PB_NEWS_TOP_N:
            continue
        old = old_pb[player_id].get(field)
        if old and old['video_id'] == new['video_id'] and old['timems'] == new['timems']:
            continue
        emit('pb', player_id, {'field': field, 'old': old, 'new': new})


def _write_records(previous, saolei_records, pb_changes, top_records, video_id=None):
    old_saolei, old_pb, old_top = previous
    ranking = PBRankingCache()
    previous_ranks = ranking.read_previous_ranks(old_pb, pb_changes) if pb_changes else {}
    with pipeline() as pipe:
        saolei.write_records(pipe, old_saolei, saolei_records)
        ranking.write_changes(pipe, old_pb, pb_changes)
        affected = top.write_records(pipe, old_top, top_records)
        pipe.execute()
    top.complete_update(old_top, top_records, affected, video_id=video_id)
    if pb_changes:
        ranking.refresh_changed_ranks(previous_ranks, pb_changes)
        _publish_pb_news(old_pb, pb_changes, ranking)


@ranking_access(operation='speedranking.sync_video')
def _sync_video(video_id: int, previous_player_id: int):
    with log_update_errors('sync_video', video_id=video_id, previous_player_id=previous_player_id):
        video = VideoModel.objects.filter(pk=video_id).values(*saolei.VIDEO_FIELDS, 'iqg').first()
        players = {previous_player_id}
        if video:
            players.add(video['player_id'])
        previous = _read_records(players)
        saolei_records = saolei.prepare_video_update(video, video_id, previous[0])
        pb_changes = pb.prepare_video_update(video, video_id, previous[1])
        top_records = top.prepare_video_update(video, video_id, previous[2])
        _write_records(previous, saolei_records, pb_changes, top_records, video_id=video_id)


def sync_video(video_id: int, previous_player_id: int):
    """提交后共同读取、分别判断并共同写入各大榜，PB 随后刷新 rank。"""
    transaction.on_commit(partial(_sync_video, video_id, previous_player_id))


@ranking_access(operation='speedranking.update_videos')
def _update_videos(videos, remove: bool):
    with log_update_errors('remove_videos' if remove else 'add_videos'):
        for players in player_batches(videos, 100):
            subset = videos.filter(player_id__in=players)
            previous = _read_records(players)
            if remove:
                ids_by_player = {}
                for player_id, video_id in subset.values_list('player_id', 'id'):
                    ids_by_player.setdefault(player_id, set()).add(video_id)
                saolei_records = saolei.prepare_remove_videos(ids_by_player, previous[0])
                pb_changes = pb.prepare_remove_videos(ids_by_player, previous[1])
                top_records = top.prepare_remove_videos(ids_by_player, previous[2])
            else:
                saolei_records = saolei.prepare_add_videos(subset, previous[0])
                pb_changes = pb.prepare_add_videos(subset, previous[1])
                top_records = top.prepare_add_videos(subset, previous[2])
            _write_records(previous, saolei_records, pb_changes, top_records)


def add_videos_to_speed_ranks(videos):
    """批量吸收已公开或已审核的录像，数据库事务提交后更新各大榜。"""
    transaction.on_commit(partial(_update_videos, videos.all(), False))


def remove_videos_from_speed_ranks(videos):
    """批量失效后仅补位保持的纪录；传入按录像 id 固定的 queryset。"""
    transaction.on_commit(partial(_update_videos, videos.all(), True))
