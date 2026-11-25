from datetime import UTC
from math import isfinite


MODE_ABBREVIATIONS = {'00': 'STD', '05': 'SPNG', '06': 'HCNG', '10': 'LK'}
STAT_FORMATS = {
    'cl': ('Cl', 'd'), 'ce': ('Ce', 'd'),
    'path': ('Path', '.3f'), 'cpath': ('cPath', '.3f'),
    'epath': ('ePath', '.3f'), 'pluck': ('pLuck', '.3f'),
    'op': ('Op', 'd'), 'isl': ('Is', 'd'),
    **{f'cell{index}': (f'Cell{index}', 'd') for index in range(9)},
    'ioe': ('IOE', '.3f'), 'thrp': ('ThrP', '.3f'), 'corr': ('Corr', '.3f'),
    'cl_s': ('Cls', '.3f'), 'ce_s': ('Ces', '.3f'), 'bvs': ('Bvs', '.3f'),
    'stnb': ('STNB', '.1f'),
}


def parse_preview_stats(stat: str) -> tuple[str, ...]:
    if not stat.strip():
        return ()
    stats = tuple(dict.fromkeys(item.strip() for item in stat.split(',')))
    if any(item not in STAT_FORMATS for item in stats):
        raise ValueError('Invalid share preview stats.')
    return stats


def preview_number(value, format_spec: str) -> str:
    if value is None or not isfinite(value):
        return 'N/A'
    return format(value, format_spec)


def preview_text(video, board, stats: tuple[str, ...]) -> tuple[str, str]:
    mode = MODE_ABBREVIATIONS.get(video.mode, f'M{video.mode}')
    duration = f'{video.timems // 1000}.{video.timems % 1000:03d}'
    title = f'{mode} {board.rows}x{board.columns}/{board.mines} {duration}/{preview_number(video.bv, "d")} by {video.player.username}'
    description = video.upload_time.astimezone(UTC).strftime('%Y-%m-%d %H:%M:%S')
    if stats:
        values = []
        for stat in stats:
            label, format_spec = STAT_FORMATS[stat]
            values.append(f'{label} {preview_number(getattr(video, stat), format_spec)}')
        description += '\n' + ', '.join(values)
    return title, description
