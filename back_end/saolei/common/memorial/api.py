from datetime import datetime
import logging

from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from ninja import File, Form, Router, UploadedFile
from ninja.decorators import decorate_view
from ninja.security import django_auth_superuser
from pydantic import Json

from accountlink.models import AccountLinkQueue, Platform, PLATFORM_CONFIG
from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from .schema import AccountLinkIn, AccountLinkOut, AccountUnlinkOut, IdentifierText, MemorialAccountLinkOut, MemorialLinksOut, UploadAccessOut, UploadResultOut
from .services import assign_memorial_account_link, ASSIGNABLE_MEMORIAL_PLATFORMS, register_memorial_identifiers, remove_memorial_account_link, upload_memorial_video


router = Router(auth=django_auth_superuser, tags=['Memorial video uploads'])
logger = logging.getLogger('userprofile')


def _get_memorial_target(user_id):
    user = UserProfile.objects.select_related('userms').filter(pk=user_id).first()
    if user is None:
        raise ExceptionToResponse('memorial', 'not_found', status_code=404)
    if not user.is_memorial:
        raise ExceptionToResponse('memorial', 'not_memorial', status_code=409)
    if user.userms_id is None:
        raise ExceptionToResponse('memorial', 'userms_missing', status_code=409)
    return user


def _memorial_link_out(user, link) -> MemorialAccountLinkOut:
    model = PLATFORM_CONFIG[Platform(link.platform)]['model']
    account = model.objects.filter(pk=link.identifier).first()
    # WoM 不保存用户名，只能回落到空串；Saolei 与 MSGames 都保存了远端名称。
    name = getattr(account, 'name', '') if account is not None else ''
    return {
        'platform': link.platform,
        'identifier': link.identifier,
        'verified': link.verified,
        'name': name or '',
    }


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


@router.get('/users/{user_id}/account-links', response=MemorialLinksOut)
@decorate_view(ensure_csrf_cookie, cache_control(no_store=True))
def links_access(request, user_id: int):
    """
    - auth=django_auth_superuser
    - ensure_csrf_cookie
    - cache_control(no_store=True)

    List the account links a superuser assigned to a memorial account.
    """
    user = _get_memorial_target(user_id)
    links = list(AccountLinkQueue.objects.filter(userprofile=user, platform__in=ASSIGNABLE_MEMORIAL_PLATFORMS).order_by('platform'))
    return {'csrf_token': get_token(request), 'user': user, 'links': [_memorial_link_out(user, link) for link in links]}


@router.post('/users/{user_id}/account-links', response=AccountLinkOut)
def assign_link(request, user_id: int, data: AccountLinkIn = Form(...)):  # noqa: B008
    """
    - auth=django_auth_superuser (session and CSRF)

    Assign one verified platform account to a memorial account, replacing any existing
    assignment for the same platform. Only Saolei.wang, MSGames and Minesweeper.Online.
    """
    result = assign_memorial_account_link(user_id, data.platform, data.identifier)
    logger.warning('Superuser #%s assigned memorial account link user=%s', request.user.pk, user_id)
    return result


@router.delete('/users/{user_id}/account-links', response=AccountUnlinkOut)
def remove_link(request, user_id: int, platform: str):
    """
    - auth=django_auth_superuser (session and CSRF)

    Remove one platform account assigned by a superuser; other platforms are kept.
    """
    result = remove_memorial_account_link(user_id, platform)
    logger.warning('Superuser #%s removed memorial account link user=%s', request.user.pk, user_id)
    return result
