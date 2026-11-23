from contextlib import contextmanager
import logging

logger = logging.getLogger('customranking')


@contextmanager
def log_update_errors(operation: str, **context):
    try:
        yield
    except Exception:
        logger.exception('Pluck ranking update failed: %s %s', operation, context)
        raise
