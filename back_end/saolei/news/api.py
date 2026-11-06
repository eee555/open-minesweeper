from django_ratelimit.decorators import ratelimit
from ninja import Router, Schema
from ninja.decorators import decorate_view

from .cache import CATEGORIES, read_events


router = Router()


class NewsEventOut(Schema):
    id: str
    category: str
    occurred_at: int
    player_id: int
    payload: dict


@router.get('/events', response=list[NewsEventOut])
@decorate_view(ratelimit(key='ip', rate='5/s'))
def get_news_events(request, category: str = 'all', limit: int = 50):
    """
    - ratelimit(key='ip', rate='5/s')

    Read the live news events from the cache only; expired events are never retained.
    """
    selected = None if category == 'all' or category not in CATEGORIES else category
    return read_events(selected, max(1, min(limit, 200)))
