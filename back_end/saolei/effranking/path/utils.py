from math import isfinite
from typing import Literal

from config.text_choices import MS_TextChoices

LEVELS = ('b', 'i', 'e')
METRICS = ('path', 'cpath', 'epath')
RankStat = Literal['b_path', 'b_cpath', 'b_epath', 'i_path', 'i_cpath', 'i_epath', 'e_path', 'e_cpath', 'e_epath', 'sum_path', 'sum_cpath', 'sum_epath']
STAT_PARTS = {f'{level}_{metric}': (level, metric) for level in (*LEVELS, 'sum') for metric in METRICS}
RANK_STATS = tuple(STAT_PARTS)
RECORD_FIELDS = tuple(f'{level}_{metric}' for level in LEVELS for metric in METRICS)


def empty_record():
    return dict.fromkeys(RECORD_FIELDS)


def is_eligible(video: dict | None):
    return video is not None and video['level'] in LEVELS and video['mode'] == MS_TextChoices.Mode.STD and video['state'] == MS_TextChoices.State.OFFICIAL and not video['ongoing_tournament']


def candidate_for_video(video: dict | None, metric: str):
    if not is_eligible(video):
        return None
    value = video[metric]
    return {'value': value, 'video_id': video['id']} if value is not None and isfinite(value) and value >= 0 else None


def is_better(candidate: dict, previous: dict | None):
    return previous is None or candidate['value'] < previous['value']


def record_scores(record: dict):
    scores = {stat: part['value'] if (part := record[stat]) is not None else None for stat in RECORD_FIELDS}
    for metric in METRICS:
        parts = [scores[f'{level}_{metric}'] for level in LEVELS]
        scores[f'sum_{metric}'] = sum(parts) if all(value is not None for value in parts) else None
    return scores
