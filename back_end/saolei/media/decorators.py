"""作品页专用装饰器：media_banned_blocked；见 MEDIA_PLAN.md 第 7、9 节。"""

from functools import wraps

from django.http import HttpResponseForbidden

from .models import UserMedia


def media_banned_blocked(view_func):
    """只禁止投稿：UserMedia.banned 独立于 UserProfile.is_banned 的全站封禁。"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and UserMedia.objects.filter(pk=request.user.pk, banned=True).exists():
            return HttpResponseForbidden()
        return view_func(request, *args, **kwargs)
    return _wrapped_view
