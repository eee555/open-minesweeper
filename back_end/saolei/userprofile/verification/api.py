"""玩家认证 API。权限、CSRF 与限流都只在 API 层处理。

认证和取消认证只提交后台任务并返回 202；树和有效认证状态在任务完整提交后才变化。
"""

from uuid import UUID

from django.views.decorators.cache import cache_control
from django_ratelimit.decorators import ratelimit
from ninja import Form, Router, Schema
from ninja.decorators import decorate_view
from ninja.security import django_auth_superuser

from userprofile.decorators import admin_csrf_required, login_required_error, staff_or_superuser_required
from userprofile.schema import VerificationStatusOut, VerificationTaskAcceptedOut, VerificationTaskResultOut
from userprofile.tasks import task_apply_verification
from .services import create_request, read_task_result, read_verification_status, reject_request, submit_approval, submit_operation
from .utils import OPERATION_DETACH, OPERATION_GRANT, OPERATION_REVOKE

router = Router()
admin_router = Router()


class VerificationTargetIn(Schema):
    user_id: int


class VerificationRequestIn(Schema):
    user_id: int


@router.get('/request', response=VerificationStatusOut)
@decorate_view(login_required_error, cache_control(no_store=True, private=True), ratelimit(key='user', rate='60/m'))
def get_verification_request(request):
    """
    - login_required_error
    - cache_control(no_store=True, private=True)
    - ratelimit(key='user', rate='60/m')

    只返回本人当前申请、冷却与本人已提交任务的受理状态；不提供收到申请的列表，
    也不展示认证来源、认证人或历史。GET 不写库。
    """
    return read_verification_status(request.user)


@router.post('/requests', response=VerificationStatusOut)
@decorate_view(login_required_error)
def create_verification_request(request, data: VerificationRequestIn = Form(...)):  # noqa: B008
    """
    - login_required_error
    - 无发送额度或速率限额（按项目方决定）

    以本人为申请人，向指定的另一名本站用户发出申请。未到期的当前申请会被拒绝；
    已到期的未批准申请在本短事务内删除后重建。已批准或管理员认证的节点不按时间删除。
    """
    return create_request(request.user.pk, data.user_id)


@router.post('/requests/{user_id}/approve', response={202: VerificationTaskAcceptedOut})
@decorate_view(login_required_error)
def approve_verification_request(request, user_id: int):
    """
    - login_required_error
    - 无批准额度或速率限额（按项目方决定）

    认证方直接输入申请人 ID。服务端核对申请发给当前用户、未批准、未到期后提交后台任务；
    收件人是否已认证不影响受理权限，202 只表示已入队。
    """
    task_id, existing = submit_approval(task_apply_verification, request.user.pk, user_id)
    return 202, {'task_id': task_id, 'existing': existing}


@router.post('/requests/{user_id}/reject', response={204: None})
@decorate_view(login_required_error, ratelimit(key='user', rate='30/m'))
def reject_verification_request(request, user_id: int):
    """
    - login_required_error
    - ratelimit(key='user', rate='30/m')

    指定收件人直接输入申请人 ID 拒绝。保留 created_at，七天冷却不提前结束。
    """
    reject_request(request.user.pk, user_id)
    return 204, None


@router.post('/detach', response={202: VerificationTaskAcceptedOut})
@decorate_view(login_required_error, admin_csrf_required, ratelimit(key='user', rate='10/m'))
def detach_verification(request):
    """
    - login_required_error
    - admin_csrf_required
    - ratelimit(key='user', rate='10/m')

    本人解除已被认证的入边，不接收目标用户 ID。已经因上游失效而未认证但关系仍在时也可提交。
    """
    task_id, existing = submit_operation(task_apply_verification, OPERATION_DETACH, request.user.pk, request.user.pk)
    return 202, {'task_id': task_id, 'existing': existing}


@router.get('/tasks/{task_id}', response=VerificationTaskResultOut)
@decorate_view(login_required_error, cache_control(no_store=True, private=True), ratelimit(key='user', rate='120/m'))
def get_verification_task(request, task_id: UUID):
    """
    - login_required_error
    - cache_control(no_store=True, private=True)
    - ratelimit(key='user', rate='120/m')

    仅任务提交者可查询，且只接受本模块的任务。不返回任务原始参数或认证关系。
    """
    return read_task_result(request.user.pk, task_id)


@admin_router.post('/grant', response={202: VerificationTaskAcceptedOut})
@decorate_view(staff_or_superuser_required)
def grant_verification(request, data: VerificationTargetIn = Form(...)):  # noqa: B008
    """
    - staff_or_superuser_required（is_staff 或 is_superuser + CSRF）
    - 管理员专用接口无限流

    管理员或站长主动认证目标（可为自己），后台任务完成后目标成为独立根节点并恢复有效子树。
    不要求操作者本身已认证。
    """
    task_id, existing = submit_operation(task_apply_verification, OPERATION_GRANT, request.user.pk, data.user_id)
    return 202, {'task_id': task_id, 'existing': existing}


@admin_router.post('/revoke', auth=django_auth_superuser, response={202: VerificationTaskAcceptedOut})
def revoke_verification(request, data: VerificationTargetIn = Form(...)):  # noqa: B008
    """
    - auth=django_auth_superuser（会话认证自带 CSRF）
    - 管理员专用接口无限流

    仅站长可取消任意用户的认证：后台任务切断目标入边，目标及有效后代均未认证，
    后代内部已批准关系保留。已实名用户仍可通过实名条件准入。
    """
    task_id, existing = submit_operation(task_apply_verification, OPERATION_REVOKE, request.user.pk, data.user_id)
    return 202, {'task_id': task_id, 'existing': existing}
