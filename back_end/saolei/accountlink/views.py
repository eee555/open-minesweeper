from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, JsonResponse
from django.tasks import TaskResultStatus
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from userprofile.decorators import login_required_error
from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from .models import AccountLinkQueue, AccountSaolei, Platform, VideoSaolei
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


@require_GET
@ratelimit(key='ip', rate='1/s')
def view_saolei_get_import_list(request: HttpRequest):
    videos = VideoSaolei.objects.all()
    user_id = request.GET.get('user_id')
    saolei_id = request.GET.get('saolei_id')
    if user_id and saolei_id:
        return HttpResponseBadRequest()
    if user_id:
        user = UserProfile.objects.filter(id=user_id).first()
        if not user:
            return HttpResponseNotFound()
        videos = videos.filter(user=user.account_saolei)
    if saolei_id:
        account = AccountSaolei.objects.filter(id=saolei_id).first()
        if not account:
            return HttpResponseNotFound()
        videos = videos.filter(user=account)

    data = videos.values('id', 'user__id', 'upload_time', 'level', 'bv', 'timems', 'nf', 'state', 'import_video__id', 'import_task__status')
    return JsonResponse(list(data), safe=False)


@require_GET
def view_saolei_get_import_summary(request: HttpRequest):
    if not (saolei_id := request.GET.get('saolei_id')):
        return HttpResponseBadRequest
    if not (saolei_account := AccountSaolei.objects.filter(id=saolei_id).first()):
        return HttpResponseNotFound()

    bulk_task = saolei_account.video_import_task
    bulk_task_status = bulk_task.status if bulk_task else None

    videos = VideoSaolei.objects.filter(user=saolei_account)
    imported_videos = videos.filter(import_video__isnull=False)
    data = {
        'bulk_task_status': bulk_task_status,
        'total': videos.count(),
        'old_imported': imported_videos.filter(import_task__isnull=True).count(),
        'new_total': videos.filter(import_task__isnull=False).count(),
        'new_ready': videos.filter(import_task__status=TaskResultStatus.READY).count(),
        'new_success': imported_videos.filter(import_task__isnull=False).count(),
        'new_failed': imported_videos.filter(import_task__status=TaskResultStatus.FAILED).count(),
        'new_connection': videos.filter(import_video__isnull=True, import_task__status=TaskResultStatus.SUCCESSFUL).count(),
    }

    return JsonResponse(data)
