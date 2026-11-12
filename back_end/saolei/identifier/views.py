import logging

from django.http import HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotFound, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from userprofile.decorators import login_required_error, staff_required
from utils.response import HttpResponseConflict
from videomanager.models import VideoModel
from .models import Identifier
from .services import bind_identifier, unbind_identifier

logger = logging.getLogger('userprofile')


# 请求修改自己的标识
@require_POST
@login_required_error
def add_identifier(request):
    user = request.user
    if not (identifier_text := request.POST.get('identifier')):
        return HttpResponseBadRequest()
    identifier = Identifier.objects.filter(identifier=identifier_text).first()
    if not identifier or not identifier.safe:
        return JsonResponse({'type': 'error', 'object': 'identifier', 'category': 'notFound'})
    if identifier.userms:
        identifier_user = identifier.userms.parent
        if identifier_user.id == user.id:
            return HttpResponseConflict()  # 本人已有该标识
        return JsonResponse({'type': 'error', 'object': 'identifier', 'category': 'conflict', 'value': identifier_user.id})  # 返回标识冲突的用户
    video_count = VideoModel.objects.filter(player=user, video__identifier=identifier_text).count()
    if not video_count:
        return JsonResponse({'type': 'error', 'object': 'identifier', 'category': 'notFound'})
    bind_identifier(identifier, user.userms)
    logger.info(f'用户 {user.username}#{user.id} 绑定标识 "{identifier_text}"')
    return JsonResponse({'type': 'success', 'object': 'identifier', 'category': 'add', 'value': video_count})


# 请求删除自己的标识
@require_POST
@login_required_error
def del_identifier(request):
    user = request.user
    if not (identifier_text := request.POST.get('identifier')):
        return HttpResponseBadRequest()
    if not (identifier := Identifier.objects.filter(identifier=identifier_text).first()):
        return HttpResponseNotFound()
    if identifier.userms.parent.id != user.id:
        return HttpResponseForbidden()
    changed_count = unbind_identifier(identifier, user.userms)
    logger.info(f'用户 {user.username}#{user.id} 解绑标识 "{identifier_text}"')
    logger.info(f'排队同步了 {changed_count} 个录像状态')
    return JsonResponse({'type': 'success', 'object': 'identifier', 'category': 'add', 'value': changed_count})


# 管理员查询标识
@require_GET
@staff_required
def staff_get_identifier(request):
    identifier_text = request.GET.get('identifier')
    if not identifier_text:
        return HttpResponseBadRequest()
    identifier = Identifier.objects.filter(identifier=identifier_text).first()
    if not identifier:
        return HttpResponseNotFound()
    if identifier.userms:
        userid = identifier.userms.parent.id
    else:
        userid = None
    return JsonResponse({'user': userid, 'safe': identifier.safe})
