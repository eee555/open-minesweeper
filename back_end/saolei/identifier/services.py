from django.db import transaction

from config.text_choices import MS_TextChoices
from msuser.models import UserMS
from utils.exceptions import ExceptionToResponse
from utils.ranking_lock import ranking_access
from videomanager.models import VideoModel
from .models import Identifier
from .tasks import task_sync_identifier_videos


def _pending_video_count(identifier_text: str, player, state: str):
    return VideoModel.objects.filter(player=player, video__identifier=identifier_text, state=state).count()


def _enqueue_video_sync(identifier_text: str, player_id: int):
    """绑定关系提交后才允许 worker 读取这批录像，避免任务抢在事务提交前执行。"""
    transaction.on_commit(lambda: task_sync_identifier_videos.enqueue(identifier_text, player_id))


@ranking_access(operation='identifier.bind')
def bind_identifier(identifier: Identifier, userms: UserMS):
    """绑定标识；录像状态与排行的批量同步交由后台任务完成。"""
    if not identifier.safe:
        raise ExceptionToResponse('identifier', 'invalid')
    if identifier.userms_id is not None and identifier.userms_id != userms.id:
        raise ExceptionToResponse('identifier', 'collision')

    with transaction.atomic():
        player = userms.parent
        if identifier.identifier not in userms.identifiers:
            userms.identifiers.append(identifier.identifier)
            userms.save(update_fields=['identifiers'])

        if identifier.userms_id != userms.id:
            identifier.userms = userms
            identifier.save(update_fields=['userms'])

        changed_count = _pending_video_count(identifier.identifier, player, MS_TextChoices.State.IDENTIFIER)
        _enqueue_video_sync(identifier.identifier, player.pk)

    return changed_count


@ranking_access(operation='identifier.unbind')
def unbind_identifier(identifier: Identifier, userms: UserMS | None = None):
    """解绑标识；录像状态与排行的批量同步交由后台任务完成。"""
    if userms is None:
        userms = identifier.userms
    if userms is None:
        raise ValueError('Identifier is not bound')
    if identifier.userms_id is not None and identifier.userms_id != userms.id:
        raise ValueError('Identifier is bound to another user')

    with transaction.atomic():
        player = userms.parent
        if identifier.identifier in userms.identifiers:
            userms.identifiers.remove(identifier.identifier)
            userms.save(update_fields=['identifiers'])

        if identifier.userms_id is not None:
            identifier.userms = None
            identifier.save(update_fields=['userms'])

        changed_count = _pending_video_count(identifier.identifier, player, MS_TextChoices.State.OFFICIAL)
        _enqueue_video_sync(identifier.identifier, player.pk)

    return changed_count


def set_safe(identifier: Identifier, safe: bool):
    """设置标识安全状态；标识绑定用户时不能设为不安全。"""
    if not safe and identifier.userms_id is not None:
        raise ValueError('Bound identifier cannot be marked unsafe')
    if identifier.safe == safe:
        return

    identifier.safe = safe
    identifier.save(update_fields=['safe'])
