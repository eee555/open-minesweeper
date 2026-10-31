from datetime import datetime

from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from ninja import File, Form, Router, UploadedFile
from ninja.decorators import decorate_view
from ninja.security import django_auth_superuser
from pydantic import Json

from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from .schema import IdentifierText, UploadAccessOut, UploadResultOut
from .services import register_memorial_identifiers, upload_memorial_video


router = Router(auth=django_auth_superuser, tags=['Memorial video uploads'])


def _get_memorial_target(user_id):
    user = UserProfile.objects.select_related('userms').filter(pk=user_id).first()
    if user is None:
        raise ExceptionToResponse('memorial', 'not_found', status_code=404)
    if not user.is_memorial:
        raise ExceptionToResponse('memorial', 'not_memorial', status_code=409)
    if user.userms_id is None:
        raise ExceptionToResponse('memorial', 'userms_missing', status_code=409)
    return user


@router.get('/users/{user_id}/videos', response=UploadAccessOut)
@decorate_view(ensure_csrf_cookie, cache_control(no_store=True))
def upload_access(request, user_id: int):
    """
    - auth=django_auth_superuser
    - ensure_csrf_cookie
    - cache_control(no_store=True)
    """
    return {'csrf_token': get_token(request), 'user': _get_memorial_target(user_id)}


@router.post('/users/{user_id}/videos', response=UploadResultOut)
def upload_video(request, user_id: int, identifiers: Json[list[IdentifierText]] = Form(...), upload_time: datetime = Form(...), file: UploadedFile = File(...)):  # noqa: B008
    """
    - auth=django_auth_superuser (session and CSRF)

    Bind all selected identifiers before importing the file. Binding failures do not block the upload.
    """
    user = _get_memorial_target(user_id)
    bindings = register_memorial_identifiers(user, identifiers)
    try:
        video = upload_memorial_video(user, file, upload_time)
    except ExceptionToResponse as error:
        return JsonResponse({**error.body, 'bindings': bindings}, status=max(error.status_code, 400))
    return {'video': video, 'bindings': bindings}
