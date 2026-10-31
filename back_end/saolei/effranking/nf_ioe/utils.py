from math import isfinite
from typing import Literal

from config.text_choices import MS_TextChoices
from videomanager.models import MAX_TIMEMS

RankStat = Literal['b', 'i', 'e', 'sum']
LEVELS = ('b', 'i', 'e')
RANK_STATS = (*LEVELS, 'sum')


def empty_record():
    return dict.fromkeys(LEVELS)


def is_eligible(video: dict | None):
    return video is not None and video['level'] in LEVELS and video['right_ce'] == 0 and video['mode'] == MS_TextChoices.Mode.STD and video['state'] == MS_TextChoices.State.OFFICIAL and not video['ongoing_tournament']


def encode_score(value: float, timems: int, maximum: int = 1):
    """分值未满时不比较用时；负值使更好的成绩排在前面。"""
    return -(maximum + MAX_TIMEMS - timems) if value == maximum else -value


def candidate_for_video(video: dict | None):
    if not is_eligible(video):
        return None
    value = video['ioe']
    if value is None or not isfinite(value):
        return None
    return {'value': value, 'video_id': video['id'], 'timems': video['timems']}


def is_better(candidate: dict, previous: dict | None):
    return previous is None or encode_score(candidate['value'], candidate['timems']) < encode_score(previous['value'], previous['timems'])


def record_scores(record: dict):
    scores = {level: encode_score(part['value'], part['timems']) if (part := record[level]) is not None else None for level in LEVELS}
    parts = [part for part in record.values() if part is not None]
    value = sum(part['value'] for part in parts)
    scores['sum'] = encode_score(value, record['e']['timems'] if record['e'] is not None else 0, 3) if parts else None
    return scores
