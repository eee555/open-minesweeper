import logging

from django.dispatch import receiver

from .cache import publish
from .events import news_event_detected


logger = logging.getLogger(__name__)


@receiver(news_event_detected)
def record_news_event(sender, category, player_id, payload, **kwargs):
    # 新闻是派生数据，发布失败绝不应拖垮主榜单流程，故吞掉异常仅记录 traceback。
    try:
        publish(category, player_id, payload)
    except Exception:
        logger.exception('Failed to publish %s news event for player %s', category, player_id)
