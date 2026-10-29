from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, JsonResponse
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from userprofile.decorators import login_required_error
from utils.exceptions import ExceptionToResponse
from .models import AccountLinkQueue, Platform
from .services import update_account
from .utils import delete_account


# 解绑自己的账号，只需要指定平台
@require_POST
@login_required_error
def delete_link(request):
    if not (platform := request.POST.get('platform')):
        return HttpResponseBadRequest()
    if platform == Platform.MINERACER:
        return ExceptionToResponse('mineracer', 'unlink_not_supported', status_code=409).response()
    if accountlink := AccountLinkQueue.objects.filter(platform=platform, userprofile=request.user).first():
        if accountlink.verified:
            delete_account(request.user, platform)
        accountlink.delete()
        return HttpResponse()
    return HttpResponseNotFound()


@require_POST
@login_required_error
@ratelimit(key='user', rate='6/h')
def update_link(request):
    if not (platform := request.POST.get('platform')):
        return HttpResponseBadRequest()
    try:
        update_account(platform, request.user)
    except ExceptionToResponse as e:
        return e.response()
    return JsonResponse({'type': 'success'})
