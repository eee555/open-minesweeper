"""玩家认证 API。权限、CSRF 与限流只在 API 层处理。

所有图写入都在 HTTP 请求内的单个事务中同步完成并返回结果，没有后台任务与任务查询。
"""

from django.views.decorators.cache import cache_control
from django_ratelimit.decorators import ratelimit
from ninja import Field, Router, Schema
from ninja.decorators import decorate_view
from ninja.security import django_auth_superuser

from userprofile.decorators import login_required_error, staff_or_superuser_required
from userprofile.schema import (GraphNodeOut, GraphSnapshotOut, GraphUpdateResultOut, MaintenanceStateOut,
                                SetVerifiedOut, VerificationActionOut, VerificationStatusOut)
from .services import (end_maintenance_session, read_graph, read_node, read_verification_status, set_user_verified,
                       start_maintenance_session, submit_graph_update, verify_player)
from .utils import MAX_MAINTENANCE_SECONDS

router = Router()
admin_router = Router()


class VerificationTargetIn(Schema):
    user_id: int


class SetVerifiedIn(Schema):
    user_id: int
    verified: bool


class VerificationEdgeIn(Schema):
    from_user_id: int
    to_user_id: int


class VerifiedNodeIn(Schema):
    user_id: int
    verified: bool


class GraphUpdateIn(Schema):
    add_edges: list[VerificationEdgeIn] = Field(default_factory=list)
    remove_edges: list[VerificationEdgeIn] = Field(default_factory=list)
    set_verified: list[VerifiedNodeIn] = Field(default_factory=list)


class MaintenanceStartIn(Schema):
    duration_seconds: int = Field(..., ge=1, le=MAX_MAINTENANCE_SECONDS)


@router.get('/status', response=VerificationStatusOut)
@decorate_view(login_required_error, cache_control(no_store=True, private=True), ratelimit(key='user', rate='60/m'))
def get_verification_status(request):
    """
    - login_required_error
    - cache_control(no_store=True, private=True)
    - ratelimit(key='user', rate='60/m')

    只返回本人当前认证、统一准入与全站维护状态；不展示认证来源或关系历史。
    """
    return read_verification_status(request.user)


@router.post('/verify', response=VerificationActionOut)
@decorate_view(login_required_error, ratelimit(key='user', rate='10/m'))
def verify_player_api(request, data: VerificationTargetIn):
    """
    - login_required_error
    - ratelimit(key='user', rate='10/m')

    已认证用户按本站 ID 主动认证另一名用户；不要求对方申请、确认或批准，请求内即生效。
    """
    return verify_player(request.user.pk, data.user_id)


@admin_router.post('/set-verified', response=SetVerifiedOut)
@decorate_view(staff_or_superuser_required)
def set_verified(request, data: SetVerifiedIn):
    """
    - staff_or_superuser_required（is_staff 或 is_superuser + CSRF）
    - 管理员专用接口无限流

    管理员显式设置目标用户的 verified=True/False，可为自己；不创建或删除边，不改动其他节点。
    """
    return set_user_verified(request.user.pk, data.user_id, data.verified)


@admin_router.get('/graph', auth=django_auth_superuser, response=GraphSnapshotOut)
@decorate_view(cache_control(no_store=True, private=True))
def get_verification_graph(request):
    """
    - auth=django_auth_superuser（会话认证，写操作自带 CSRF）
    - cache_control(no_store=True, private=True)
    - 管理员专用接口无限流

    读取当前全部有向边、已认证节点与维护会话状态；图结构不向普通用户公开。
    """
    return read_graph(request.user.pk)


@admin_router.get('/graph/{user_id}', auth=django_auth_superuser, response=GraphNodeOut)
def get_verification_node(request, user_id: int):
    """
    - auth=django_auth_superuser（会话认证，写操作自带 CSRF）
    - 管理员专用接口无限流

    按用户读取单节点的认证状态、入边与出边，供站长分次核对完整批次。
    """
    return read_node(user_id)


@admin_router.post('/maintenance', auth=django_auth_superuser, response=MaintenanceStateOut)
def start_verification_maintenance(request, data: MaintenanceStartIn):
    """
    - auth=django_auth_superuser（会话认证自带 CSRF）
    - 管理员专用接口无限流

    站长开启独占维护会话，时长由站长指定且不超过 1 小时。期间普通主动认证与管理员设置
    verified 返回 409，读接口与批次提交仍可用；超时自动恢复，站长需重新发起流程。
    """
    return start_maintenance_session(request.user.pk, data.duration_seconds)


@admin_router.delete('/maintenance', auth=django_auth_superuser, response={204: None})
def end_verification_maintenance(request):
    """
    - auth=django_auth_superuser（会话认证自带 CSRF）
    - 管理员专用接口无限流

    站长主动结束自己开启的维护会话，立即恢复图写入服务。
    """
    end_maintenance_session(request.user.pk)
    return 204, None


@admin_router.post('/graph-update', auth=django_auth_superuser, response=GraphUpdateResultOut)
def update_verification_graph(request, data: GraphUpdateIn):
    """
    - auth=django_auth_superuser（会话认证自带 CSRF）
    - 管理员专用接口无限流

    站长一次提交全部新增边、删除边与节点最终状态；后端在同一事务内原子执行，
    不推导可达性、替代路径或撤销范围。提交成功后立即结束维护会话。
    """
    return submit_graph_update(request.user.pk, data.model_dump())
