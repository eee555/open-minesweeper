from django.db import transaction
from django.tasks import TaskResultStatus
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from identifier.tasks import task_sync_identifier_videos
from msuser.models import UserMS
from userprofile.models import UserProfile
from userprofile.utils import validate_name


@transaction.atomic
def register_users(users: list[dict]):
    for user in users:
        validate_name(user['realname'])
    return [UserProfile.objects.create_user(userms=UserMS.objects.create(), **user) for user in users]


def run_identifier_sync_tasks():
    """E2E 不启动 worker，夹具同步推进标识录像任务，让后续请求读到最终状态。"""
    rows = list(DBTaskResult.objects.filter(
        task_path=task_sync_identifier_videos.module_path,
        status=TaskResultStatus.READY,
    ).order_by('id'))
    for row in rows:
        task_sync_identifier_videos.call(*row.args_kwargs['args'])
        DBTaskResult.objects.filter(pk=row.pk).update(status=TaskResultStatus.SUCCESSFUL, finished_at=timezone.now())