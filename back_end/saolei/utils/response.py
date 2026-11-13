from django.http import HttpResponse, JsonResponse


def ratelimited_error(request, exception):
    return HttpResponse(status=429)


class HttpResponseConflict(HttpResponse):
    status_code = 409


def identity_access_required_response():
    """实名或玩家认证均不满足时的统一准入错误。"""
    return JsonResponse({'type': 'error', 'object': 'userprofile', 'category': 'identity_access_required'})
