from functools import wraps

from django.http import HttpResponseForbidden

from config.tournaments import GSC_Defaults
from userprofile.decorators import admin_csrf_required


def GSC_admin_required(view_func):
    protected_view = admin_csrf_required(view_func)

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or (request.user.id != GSC_Defaults.HOST_ID and not request.user.is_staff):
            return HttpResponseForbidden()  # Return 403 Forbidden response
        return protected_view(request, *args, **kwargs)
    return _wrapped_view
