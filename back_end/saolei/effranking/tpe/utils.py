from math import isfinite
from typing import Literal

from config.text_choices import MS_TextChoices

RankStat = Literal['i', 'e', 'sum']
LEVELS = ('i', 'e')
RANK_STATS = (*LEVELS, 'sum')


def empty_record():
    return dict.fromkeys(LEVELS)


def is_eligible(video: dict | None):
    return video is not None and video['level'] in LEVELS and video['mode'] == MS_TextChoices.Mode.STD and video['state'] == MS_TextChoices.State.OFFICIAL and not video['ongoing_tournament']


def candidate_for_video(video: dict | None):
    if not is_eligible(video):
        return None
    ioe = video['ioe']
    if ioe is None or not isfinite(ioe) or ioe <= 0:
        return None
    value = video['timems'] / ioe / 1000
    return {'value': value, 'video_id': video['id']} if isfinite(value) else None


def is_better(candidate: dict, previous: dict | None):
    return previous is None or candidate['value'] < previous['value']


def record_scores(record: dict):
    scores = {level: part['value'] if (part := record[level]) is not None else None for level in LEVELS}
    scores['sum'] = sum(scores.values()) if all(value is not None for value in scores.values()) else None
    return scores
