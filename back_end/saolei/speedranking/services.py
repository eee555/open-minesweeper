from functools import partial
import json

from django.db import transaction

from news.services import emit
from news.utils import LSF_NEWS_TOP_N, PB_NEWS_TOP_N
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


def _publish_pb_news(old_pb, pb_changes, ranking, news_targets):
    """PB 刷新后，只有终点仍在前 10 的事件才附带旧/新成绩、录像与名次。"""
    candidates = [(player_id, field) for (player_id, field), candidate in pb_changes.items() if candidate is not None and player_id in news_targets]
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


def _publish_lsf_news(news_targets, before, after):
    """用写入前后各一次的真实 LSF 快照发布新闻；触发录像（可能多条）由调用路径给出。

    video_ids 携带该玩家本批所有相关录像，video_id 取最小者作为主链接，二者一并写入，
    前端据此可跳到每一条相关录像，避免同批多录像时只链接到其中一条。
    """
    for player_id, video_ids in news_targets.items():
        video_ids = video_ids or []
        old_lsf, old_rank = before.get(player_id, (None, None))
        new_lsf, new_rank = after.get(player_id, (None, None))
        if new_rank is None or new_rank >= LSF_NEWS_TOP_N or old_lsf == new_lsf:
            continue
        emit('lsf', player_id, {
            'video_id': video_ids[0] if video_ids else None,
            'video_ids': video_ids,
            'old': {'lsf': old_lsf, 'rank': old_rank + 1 if old_rank is not None else None} if old_lsf is not None else None,
            'new': {'lsf': new_lsf, 'rank': new_rank + 1},
        })


def _news_targets(old_top, top_records, pb_changes):
    """批量刷榜时按变动项收集：每条 PB 纪录变动与每条 LSF 变动各带造成它的录像 id。

    同一玩家同批新增多条录像时 triggers 会包含多条 id，全部保留（按 id 升序）作为
    LSF 新闻的 video_ids，其中最小者仍作为 video_id 主链接；前端据此可跳到每一条
    相关录像，而非只链接到其中一条。
    """
    pb_videos = {}
    for (player_id, _), candidate in pb_changes.items():
        if candidate is not None:
            pb_videos.setdefault(player_id, set()).add(candidate[0])
    targets = {}
    for player_id, record in top_records.items():
        old = old_top[player_id]
        if record == old and player_id not in pb_videos:
            continue
        old_ids = {item['video_id'] for value in old.values() for item in value['videos']}
        new_ids = {item['video_id'] for value in record.values() for item in value['videos']}
        triggers = (new_ids - old_ids) | pb_videos.get(player_id, set())
        targets[player_id] = sorted(triggers) if triggers else None
    return targets


def _write_records(previous, saolei_records, pb_changes, top_records, news_targets=None):
    """写入前备好待修改玩家的旧快照，写入后再取一次，新闻由调用路径决定是否发布。"""
    old_saolei, old_pb, old_top = previous
    ranking = PBRankingCache()
    top_ranking = TopRankingCache()
    previous_ranks = ranking.read_previous_ranks(old_pb, pb_changes) if pb_changes else {}
    lsf_before = top_ranking.lsf_snapshot(news_targets) if news_targets else {}
    with pipeline() as pipe:
        saolei.write_records(pipe, old_saolei, saolei_records)
        ranking.write_changes(pipe, old_pb, pb_changes)
        affected = top.write_records(pipe, old_top, top_records)
        pipe.execute()
    lsf_after = top.complete_update(old_top, top_records, affected, ranking=top_ranking, snapshot_players=news_targets)
    if pb_changes:
        ranking.refresh_changed_ranks(previous_ranks, pb_changes)
    if news_targets:
        _publish_pb_news(old_pb, pb_changes, ranking, news_targets)
        _publish_lsf_news(news_targets, lsf_before, lsf_after)


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
        news_targets = {video['player_id']: [video_id]} if video else None
        _write_records(previous, saolei_records, pb_changes, top_records, news_targets=news_targets)


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
                video_ids = {}
                for player_id, video_id in subset.values_list('player_id', 'id'):
                    video_ids.setdefault(player_id, []).append(video_id)
                ids_by_player = {player_id: set(ids) for player_id, ids in video_ids.items()}
                saolei_records = saolei.prepare_remove_videos(ids_by_player, previous[0])
                pb_changes = pb.prepare_remove_videos(ids_by_player, previous[1])
                top_records = top.prepare_remove_videos(ids_by_player, previous[2])
                news_targets = None
            else:
                saolei_records = saolei.prepare_add_videos(subset, previous[0])
                pb_changes = pb.prepare_add_videos(subset, previous[1])
                top_records = top.prepare_add_videos(subset, previous[2])
                news_targets = _news_targets(previous[2], top_records, pb_changes)
            _write_records(previous, saolei_records, pb_changes, top_records, news_targets=news_targets)


def add_videos_to_speed_ranks(videos):
    """批量吸收已公开或已审核的录像，数据库事务提交后更新各大榜。"""
    transaction.on_commit(partial(_update_videos, videos.all(), False))


def remove_videos_from_speed_ranks(videos):
    """批量失效后仅补位保持的纪录；传入按录像 id 固定的 queryset。"""
    transaction.on_commit(partial(_update_videos, videos.all(), True))
