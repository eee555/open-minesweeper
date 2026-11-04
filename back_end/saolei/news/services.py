from .events import news_event_detected


def emit(category: str, player_id: int, payload: dict) -> None:
    """排行榜侧只声明发生了什么，存储由 news.signals 完成。"""
    news_event_detected.send(sender=category, category=category, player_id=player_id, payload=payload)
