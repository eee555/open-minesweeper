"""效率榜新闻：把当次写入前后的个人纪录差异转成 news 分区事件。"""

from news.services import emit

from .cache import pipeline
from .nf_ioe.utils import record_scores as ioe_record_scores
from .thrp.utils import NF_STAT, record_scores as thrp_record_scores

CATEGORY = 'eff'


def _scores(ranking, record):
    return thrp_record_scores(record) if ranking.ranking_name == 'thrp' else ioe_record_scores(record)


def _news_value(ranking, record, stat):
    """返回纪录展示值与主录像；sum 是派生值没有对应录像，高级 NF 取首条达成录像。"""
    if stat == 'sum':
        level_fields = (field for field in ranking.record_fields if field != NF_STAT)
        parts = [record[field] for field in level_fields if record.get(field) is not None]
        return (sum(part['value'] for part in parts), None) if parts else (None, None)
    if stat == NF_STAT:
        nf = record.get(NF_STAT)
        if nf is None:
            return (None, None)
        return nf['value'], nf['video_ids'][0] if nf['video_ids'] else None
    part = record.get(stat)
    return (part['value'], part['video_id']) if part is not None else (None, None)


def prepare_news(entries):
    """entries 为 (ranking, previous, records)；只保留成绩变优的单项，名次由调用方补全。"""
    candidates = []
    for ranking, previous, records in entries:
        for player_id, record in records.items():
            old = previous[player_id]
            old_scores = _scores(ranking, old)
            new_scores = _scores(ranking, record)
            for stat in ranking.stats:
                new_score = new_scores[stat]
                if new_score is None:
                    continue
                old_score = old_scores[stat]
                if old_score is not None and new_score >= old_score:
                    continue
                old_value, old_video_id = _news_value(ranking, old, stat)
                new_value, new_video_id = _news_value(ranking, record, stat)
                if new_value is None:
                    continue
                candidates.append((ranking, player_id, stat, old_value, old_video_id, new_value, new_video_id))
    return candidates


def queue_news_ranks(pipe, candidates):
    for ranking, player_id, stat, *_ in candidates:
        pipe.zrank(ranking.rank_key(stat), str(player_id))


def read_news_ranks(candidates):
    """写入前读取旧名次；与写入后的查询分开，避免混入写命令的返回值。"""
    if not candidates:
        return []
    with pipeline() as pipe:
        queue_news_ranks(pipe, candidates)
        return pipe.execute()


def publish_news(candidates, old_ranks, new_ranks):
    """按 PB 新闻的格式逐条发布：field、旧/新成绩与各自名次。"""
    for candidate, old_rank, new_rank in zip(candidates, old_ranks, new_ranks, strict=True):
        ranking, player_id, stat, old_value, old_video_id, new_value, new_video_id = candidate
        if new_rank is None:
            continue
        old = {'value': old_value, 'video_id': old_video_id, 'rank': old_rank + 1 if old_rank is not None else None}
        emit(CATEGORY, player_id, {
            'field': f'{ranking.ranking_name}:{stat}',
            'old': old if old_value is not None else None,
            'new': {'value': new_value, 'video_id': new_video_id, 'rank': new_rank + 1},
        })
