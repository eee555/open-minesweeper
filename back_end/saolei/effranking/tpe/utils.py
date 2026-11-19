from math import isfinite
from typing import Literal

from config.text_choices import MS_TextChoices

RankStat = Literal['i', 'i2', 'i3', 'e', 'e2', 'e3', 'sum', 'sum2', 'sum3']
LEVELS = ('i', 'e')
POWERS = {'': 1, '2': 2, '3': 3}
STAT_PARTS = {f'{level}{suffix}': (level, power) for level in (*LEVELS, 'sum') for suffix, power in POWERS.items()}
RANK_STATS = tuple(STAT_PARTS)
RECORD_FIELDS = tuple(f'{level}{suffix}' for level in LEVELS for suffix in POWERS)


def empty_record():
    return dict.fromkeys(RECORD_FIELDS)


def is_eligible(video: dict | None):
    return video is not None and video['level'] in LEVELS and video['mode'] == MS_TextChoices.Mode.STD and video['state'] == MS_TextChoices.State.OFFICIAL and not video['ongoing_tournament']


def candidate_for_video(video: dict | None, power: int = 1):
    if not is_eligible(video):
        return None
    ioe = video['ioe']
    if ioe is None or not isfinite(ioe) or ioe <= 0:
        return None
    value = video['timems'] / ioe ** power / 1000
    return {'value': value, 'video_id': video['id']} if isfinite(value) else None


def is_better(candidate: dict, previous: dict | None):
    return previous is None or candidate['value'] < previous['value']


def record_scores(record: dict):
    scores = {stat: part['value'] if (part := record[stat]) is not None else None for stat in RECORD_FIELDS}
    for suffix in POWERS:
        parts = [scores[f'{level}{suffix}'] for level in LEVELS]
        scores[f'sum{suffix}'] = sum(parts) if all(value is not None for value in parts) else None
    return scores
