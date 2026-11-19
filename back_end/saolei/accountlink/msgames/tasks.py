from django.tasks import task

from accountlink.models import AccountMinesweeperGames
from accountlink.services import update_msgames_video_list
from utils.exceptions import ExceptionToResponse


@task
def task_sync_msgames(account_id: int, parent_id: int):
    """同步目录；保存业务错误供本人轮询，不返回异常堆栈。"""
    account = AccountMinesweeperGames.objects.filter(pk=account_id, parent_id=parent_id).first()
    if account is None:
        return ExceptionToResponse('accountlink', 'not_found').body
    try:
        update_msgames_video_list(account)
        account.refresh_from_db(fields=['video_update_time'])
        return {'status': 'SYNCED', 'count': account.videos.count(), 'video_update_time': account.video_update_time.isoformat()}
    except ExceptionToResponse as exc:
        return exc.body
