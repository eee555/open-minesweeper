from pathlib import Path

from django.conf import settings
from django.db import connection


def get_snapshot_path():
    return Path(getattr(settings, 'MONITOR_SNAPSHOT_PATH', settings.BASE_DIR / 'runtime' / 'monitor.json'))


def get_db_size():
    db_name = connection.settings_dict['NAME']
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT SUM(data_length + index_length)
            FROM information_schema.TABLES
            WHERE table_schema = %s
        """, [db_name])
        row = cursor.fetchone()
        return int(row[0]) if row else 0
