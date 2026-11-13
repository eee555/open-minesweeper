"""玩家认证模块的基础常量，不引用本 APP 的任何其他模块。"""

from utils.exceptions import ExceptionToResponse

MAINTENANCE_KEY = 'userprofile:verification:maintenance'
GRAPH_WRITE_LOCK_KEY = 'userprofile:verification:write_lock'
GRAPH_WRITE_LOCK_SECONDS = 30
MAX_MAINTENANCE_SECONDS = 3600
# 单次 SQL 的 IN 列表/批量插入上限，避免超大完整批次生成过长语句；次数只随规模线性分块而不随命令数逐条增长。
GRAPH_BATCH_CHUNK_SIZE = 500


def verification_error(category: str, status_code: int = 409):
    return ExceptionToResponse('verification', category, status_code=status_code)
