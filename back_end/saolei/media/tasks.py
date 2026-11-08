"""作品页后台任务：月度热度基准刷新；见 MEDIA_PLAN.md 第 10 节。"""

from django.tasks import task, TaskResultStatus
from django_tasks_db.models import DBTaskResult

from .services import refresh_hot_reference


@task(priority=-1)
def task_refresh_media_hot_reference():
    """月度低频刷新，优先级低于日常请求。"""
    return refresh_hot_reference()


def enqueue_media_hot_reference():
    """防堆积：已有 READY/RUNNING 的同任务时不再入队；作业失败可按幂等逻辑重跑。"""
    pending = DBTaskResult.objects.filter(
        task_path=task_refresh_media_hot_reference.module_path,
        status__in=[TaskResultStatus.READY, TaskResultStatus.RUNNING],
    )
    if pending.exists():
        return None
    return task_refresh_media_hot_reference.enqueue()
