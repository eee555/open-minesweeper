from functools import wraps

from django.http import HttpResponseForbidden
from django.views.decorators.csrf import csrf_protect


def admin_csrf_required(view_func):
    """Only staff/superuser calls require CSRF; ordinary callers keep their existing contract."""
    protected_view = csrf_protect(view_func)

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
            return protected_view(request, *args, **kwargs)
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def staff_required(view_func):
    """Require staff permission and Django CSRF protection on unsafe requests."""
    protected_view = csrf_protect(view_func)

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden()  # Return 403 Forbidden response
        if not request.user.is_staff:
            return HttpResponseForbidden()  # Return 403 Forbidden response
        return protected_view(request, *args, **kwargs)
    return _wrapped_view


def banned_blocked(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_banned:
            return HttpResponseForbidden()  # Return 403 Forbidden response
        return view_func(request, *args, **kwargs)  # Call the view if not banned
    return _wrapped_view


def login_required_error(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden()  # Return 403 Forbidden response
        return view_func(request, *args, **kwargs)  # Call the view if not banned
    return _wrapped_view
