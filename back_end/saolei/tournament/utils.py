from datetime import datetime, time, timedelta, timezone as datetime_timezone
import secrets
import string
from typing import Any

from django.utils import timezone

MAX_TOURNAMENT_BEST = 9223372036854775807
TOURNAMENT_SCORE_HALF_LIFE = timedelta(days=365 * 2)
TOURNAMENT_FINISH_DELAY = timedelta(hours=1)


def get_next_week_window():
    today = timezone.localdate()
    next_monday = today + timedelta(days=7 - today.weekday())
    start_time = timezone.make_aware(datetime.combine(next_monday, time.min), timezone.get_current_timezone())
    year, week, _ = start_time.isocalendar()
    return year, week, start_time, start_time + timedelta(days=7)


def generate_random_token(length=5):
    """生成指定位数的随机字母数字混合码"""
    alphabet = string.ascii_letters + string.digits  # 大小写字母+数字
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def insert_to_id_value_list_asc(list_asc: list[tuple[int, Any]], video_id: int, value: Any):
    insert_index = len(list_asc)
    for i, item in enumerate(list_asc):
        if value < item[1]:
            insert_index = i
            break
    list_asc.insert(insert_index, (video_id, value))
    list_asc.pop()


def default_weekly_classic_et():
    return [(0, 240000), (0, 240000)]


def default_weekly_classic_it():
    return [(0, 60000), (0, 60000), (0, 60000), (0, 60000), (0, 60000)]


def tournament_score_decay_factor(start_time, end_time):
    # 允许负时间差：折算到早于计分时间的年度锚点时，负指数会自动放大积分。
    elapsed_seconds = (end_time - start_time).total_seconds()
    half_life_seconds = TOURNAMENT_SCORE_HALF_LIFE.total_seconds()
    return 2 ** (-elapsed_seconds / half_life_seconds)


def tournament_score_reference_time():
    now = timezone.now().astimezone(datetime_timezone.utc)
    return datetime(now.year, 1, 1, tzinfo=datetime_timezone.utc)
