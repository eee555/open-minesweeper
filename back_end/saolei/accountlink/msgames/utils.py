from datetime import datetime, time, timedelta, timezone
import hashlib
from urllib.parse import urlsplit

from msgames_api import Profile, Record, RecordMetric

from config.customranking import CUSTOM_PLUCK_CONFIGS

RECORD_LABELS = {
    RecordMetric.TIME: 'Time', RecordMetric.THREE_BVS: '3BVS',
    RecordMetric.IOE: 'IOE', RecordMetric.DENSITY: 'Density', RecordMetric.PROBLEMS: 'Problems',
}
SCORE_FIELDS = ('Time', '3BV', '3BVS', 'IOE', 'Mines')
IMPORT_EXTENSIONS = ('.avf', '.mvf', '.rmv')


def normalize_profile(profile: Profile, player_id: int) -> dict:
    if profile.player_id != player_id or not profile.name or not profile.name.strip() or len(profile.name) > 128:
        raise ValueError('Invalid MSGames profile')
    local_name = str(profile.local_name)
    if len(local_name) > 128 or (profile.fields.get('Joined') and profile.joined is None):
        raise ValueError('Invalid MSGames profile fields')
    return {
        'name': profile.name, 'local_name': local_name, 'joined': profile.joined,
        **{field: getattr(profile, field) or '' for field in ('country', 'state', 'hand', 'mouse')},
    }


def normalize_replays(records: list[Record], player_id: int) -> list[dict]:
    videos = {}
    for record in records:
        replay = record.replay
        if replay is None:
            continue
        if record.player_id != player_id or replay.player_id not in (None, player_id):
            raise ValueError('Unexpected replay owner')
        parts = urlsplit(replay.url)
        if parts.scheme != 'https' or parts.hostname not in ('minesweepergame.com', 'www.minesweepergame.com'):
            raise ValueError('Unexpected replay host')
        if record.fields.get('Date', '') not in ('', '-', 'N/A') and record.date is None:
            raise ValueError('Invalid replay upload date')
        if record.date is not None:
            upload_date_upper_bound(record.date)
        key = hashlib.sha256(replay.url.encode('utf-8')).hexdigest()
        video = videos.setdefault(key, {
            'source_key': key, 'url': replay.url, 'filename': replay.filename,
            'upload_date': record.date, 'categories': [], 'scores': [], 'density_levels': [],
        })
        if record.metric == RecordMetric.DENSITY:
            # MSGames labels use columns x rows; project configurations use rows, columns, mines.
            for group in record.groups or ('',):
                level = next((
                    level for level, (rows, columns, mines) in CUSTOM_PLUCK_CONFIGS.items()
                    if group == f'{columns}x{rows}' and record.mines == mines
                ), None)
                if level not in video['density_levels']:
                    video['density_levels'].append(level)
        if record.date is not None and (video['upload_date'] is None or record.date < video['upload_date']):
            video['upload_date'] = record.date
        metric = RECORD_LABELS[record.metric]
        category = ' / '.join(filter(None, (metric, ', '.join(record.groups), record.style, record.category)))
        score = f'{metric}: ' + '; '.join(f'{field}: {record.fields[field]}' for field in SCORE_FIELDS if record.fields.get(field))
        if category not in video['categories']:
            video['categories'].append(category)
        if score not in video['scores']:
            video['scores'].append(score)
    return [
        {
            **{key: value for key, value in video.items() if key not in ('categories', 'scores')},
            'category': '\n'.join(video['categories']), 'score': '\n'.join(video['scores']),
        }
        for video in videos.values()
    ]


def upload_date_upper_bound(upload_date):
    try:
        return datetime.combine(upload_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    except OverflowError as exc:
        raise ValueError('Invalid replay upload date') from exc


def supports_replay(filename: str, category: str, density_levels: list) -> bool:
    if not filename.lower().endswith(IMPORT_EXTENSIONS):
        return False
    is_density = any(line.split(' / ', 1)[0] == 'Density' for line in category.splitlines())
    # Old Density rows without structured configurations must be synchronized before import.
    if is_density and not density_levels:
        return False
    return all(level in CUSTOM_PLUCK_CONFIGS for level in density_levels)
