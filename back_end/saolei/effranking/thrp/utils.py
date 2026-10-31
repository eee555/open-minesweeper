from datetime import datetime, timezone
from math import floor, isfinite
from typing import Literal

from config.text_choices import MS_TextChoices

RankStat = Literal['b', 'i', 'e', 'sum', 'e_nf']
LEVELS = ('b', 'i', 'e')
NF_STAT = 'e_nf'
RANK_STATS = (*LEVELS, 'sum', NF_STAT)
THRP_SCALE = 1_000_000
SCORE_TIME_FACTOR = 2 ** 29
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def empty_record():
    return dict.fromkeys((*LEVELS, NF_STAT))


def is_expert_nf(video: dict | None):
    """判断高级 NF 资格，不以某条录像是否保持个人最佳为条件。"""
    return video is not None and video['level'] == MS_TextChoices.Level.EXPERT and video['right_ce'] == 0 and video['mode'] == MS_TextChoices.Mode.STD and video['state'] == MS_TextChoices.State.OFFICIAL and not video['ongoing_tournament']


def candidate_for_video(video: dict | None):
    """从合格录像提取原始成绩、主表 id 和完整上传时间。"""
    if video is None or video['level'] not in LEVELS:
        return None
    if video['mode'] != MS_TextChoices.Mode.STD or video['state'] != MS_TextChoices.State.OFFICIAL or video['ongoing_tournament']:
        return None
    value = video['thrp']
    if value is None or not isfinite(value):
        return None
    return {'value': value, 'video_id': video['id'], 'upload_time': video['upload_time'].astimezone(timezone.utc).isoformat()}


def is_better(candidate: dict, previous: dict | None):
    return previous is None or (-candidate['value'], candidate['upload_time']) < (-previous['value'], previous['upload_time'])


def encode_score(value: float, upload_time: str):
    """只为排序量化分值与分钟时间，不改变原始纪录。"""
    delta = datetime.fromisoformat(upload_time) - EPOCH
    upload = delta.days * 1440 + delta.seconds // 60
    if not 0 <= upload < SCORE_TIME_FACTOR:
        raise ValueError('Upload time is outside the Thrp score encoding range')
    units = floor(value * THRP_SCALE + 0.5)
    return -units * SCORE_TIME_FACTOR + upload


def record_scores(record: dict):
    """普通四项按分值和时间编码，高级 NF 独立按成绩或满分局数编码。"""
    scores = {level: encode_score(part['value'], part['upload_time']) if (part := record[level]) is not None else None for level in LEVELS}
    parts = [part for level in LEVELS if (part := record[level]) is not None]
    scores['sum'] = encode_score(sum(part['value'] for part in parts), max(part['upload_time'] for part in parts)) if parts else None
    nf = record.get(NF_STAT)
    scores[NF_STAT] = -(len(nf['video_ids']) if nf['value'] == 1 else nf['value']) if nf else None
    return scores
