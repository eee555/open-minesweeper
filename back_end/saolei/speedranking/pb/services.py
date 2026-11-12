from django.db.models import F, Window
from django.db.models.functions import RowNumber

from config.text_choices import MS_TextChoices
from utils.querysets import player_batches
from videomanager.models import VideoModel
from .cache import PBRankingCache
from .utils import encode_score, LEVELS, parse_field, record_field
from ..cache import pipeline
from ..pb_derived import services as pb_derived
from ..utils import log_update_errors

VIDEO_FIELDS = ('id', 'player_id', 'level', 'mode', 'state', 'ongoing_tournament', 'bv', 'timems', 'right_ce', 'upload_time')


def eligible_videos(videos, nf=False):
    videos = videos.filter(level__in=LEVELS, mode=MS_TextChoices.Mode.STD, state=MS_TextChoices.State.OFFICIAL, ongoing_tournament=False)
    return videos.filter(right_ce=0) if nf else videos


def candidates_for_video(video):
    if video is None or video['level'] not in LEVELS:
        return {}
    if video['mode'] != MS_TextChoices.Mode.STD or video['state'] != MS_TextChoices.State.OFFICIAL or video['ongoing_tournament']:
        return {}
    candidate = (video['id'], encode_score(video['timems'], video['upload_time']))
    modes = (False, True) if video['right_ce'] == 0 else (False,)
    return {(video['player_id'], record_field(nf, video['level'], video['bv'])): candidate for nf in modes}


def best_candidate(player_id: int, field: str):
    """仅在补位或重建时查数据库，按原始用时及上传时间选优。"""
    nf, level, bv = parse_field(field)
    video = eligible_videos(VideoModel.objects.filter(player_id=player_id, level=level, bv=bv), nf).order_by('timems', 'upload_time', 'id').values(*VIDEO_FIELDS).first()
    return (video['id'], encode_score(video['timems'], video['upload_time'])) if video else None


def prepare_video_update(video, video_id, previous):
    candidates = candidates_for_video(video)
    held = {(player_id, field) for player_id, records in previous.items() for field, record in records.items() if record['video_id'] == video_id}
    scores = PBRankingCache().read_scores(previous, set(candidates) | held)
    changes = {}
    for key in held:
        candidate = candidates.get(key)
        if candidate is None or scores[key] is None or candidate[1] > scores[key]:
            changes[key] = best_candidate(*key)
        elif candidate[1] < scores[key]:
            changes[key] = candidate
    for key, candidate in candidates.items():
        if key not in held and (scores[key] is None or candidate[1] < scores[key]):
            changes[key] = candidate
    return changes


def best_videos(videos, nf=False):
    return eligible_videos(videos, nf).annotate(
        rn=Window(RowNumber(), partition_by=[F('player_id'), F('level'), F('bv')], order_by=[F('timems').asc(), F('upload_time').asc(), F('id').asc()]),
    ).filter(rn=1).values(*VIDEO_FIELDS)


def prepare_add_videos(videos, previous, ranking=None):
    ranking = ranking or PBRankingCache()
    candidates = {}
    for nf in (False, True):
        for video in best_videos(videos, nf).iterator(chunk_size=1000):
            key = video['player_id'], record_field(nf, video['level'], video['bv'])
            candidates[key] = video['id'], encode_score(video['timems'], video['upload_time'])
    scores = ranking.read_scores(previous, set(candidates))
    return {key: candidate for key, candidate in candidates.items() if scores[key] is None or candidate[1] < scores[key]}


def prepare_remove_videos(ids_by_player, previous):
    changes = {}
    for player_id, records in previous.items():
        for field, record in records.items():
            if record['video_id'] in ids_by_player.get(player_id, set()):
                changes[player_id, field] = best_candidate(player_id, field)
    return changes


def rebuild_player_record(player_id: int, level: str, bv: int, nf: bool):
    """强制修复一个用户的小榜纪录和可能残留的 member，并刷新该小榜排名。"""
    field = record_field(nf, level, bv)
    ranking = PBRankingCache()
    with log_update_errors('pb.rebuild_record', player_id=player_id, field=field):
        candidate = best_candidate(player_id, field)
        changes = {(player_id, field): candidate}
        with pipeline() as pipe:
            previous_ranks = ranking.remove_player_members(pipe, player_id, field)
            ranking.write_changes(pipe, {player_id: {}}, changes)
            pipe.execute()
        ranking.refresh_changed_ranks(previous_ranks, changes)
        pb_derived.rebuild_player(player_id)
        return next((record for record in ranking.get_player_records(player_id) if (record['nf'], record['level'], record['bv']) == (nf, level, bv)), None)


def rebuild_pb_ranks(batch_size=100, progress=None):
    """暂停相关写入后清空 PB 缓存，分段建榜，最后逐小榜填充 rank 和人数 hash。"""
    if batch_size <= 0:
        raise ValueError('batch_size must be positive')
    ranking = PBRankingCache()
    count = 0
    with log_update_errors('pb.rebuild', batch_size=batch_size):
        ranking.flush()
        videos = eligible_videos(VideoModel.objects.all())
        for players in player_batches(videos, batch_size):
            previous = {player_id: {} for player_id in players}
            changes = prepare_add_videos(videos.filter(player_id__in=players), previous, ranking)
            with pipeline() as pipe:
                ranking.write_changes(pipe, previous, changes)
                pipe.execute()
            count += len(players)
            if progress:
                progress(count, players[-1])
        for field in ranking.ranking_fields():
            ranking.refresh_ranks({field: (0, -1)})
        pb_derived.rebuild_all(batch_size)
    return count
