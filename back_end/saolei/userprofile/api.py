from datetime import datetime, timezone
import logging
from typing import List
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.http import FileResponse, HttpRequest, HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from django_ratelimit.decorators import ratelimit
from ninja import File, Form, Query, Router, Schema, UploadedFile
from ninja.decorators import decorate_view
from ninja.orm import create_schema

from common.services import query_user_directory_page
from utils import verify_image
from utils.exceptions import ExceptionToResponse
from videomanager.models import VideoModel
from videomanager.schema import VIDEO_METADATA_FIELDS, VideoMetadataOut
from .decorators import banned_blocked, login_required_error, staff_required
from .models import UserProfile
from .schema import PUBLIC_NAME_FIELDS, RawUserNames, SelfUserInfoOut, UserDirectoryPageOut, UserDirectoryQuery, UserInfoOut
from .services import has_sub200_expert_video, refresh_avatar_chance, try_update_user_signature, update_admin_profile, update_user_names
from .utils import NAME_FIELDS

router = Router()
logger = logging.getLogger('userprofile')
AVATAR_ACCEL_REDIRECT_PREFIX = '/internal-media/'


@router.get('/query', response=UserDirectoryPageOut)
@decorate_view(ratelimit(key='ip', rate='60/m', block=True))
def query_users(request, filters: Query[UserDirectoryQuery]):
    """
    - ratelimit(key='ip', rate='60/m', block=True)

    Public user directory. Match one ID exactly; an omitted platform selects the site user ID.
    Platform codes c/a/w/m select verified public account links. An empty ID lists all users.
    Ordering is stable by user ID for equal statistics.
    """
    return query_user_directory_page(filters)


class AdminUserProfileOutBase(RawUserNames):
    @staticmethod
    def resolve_userms_identifiers(user: UserProfile) -> list[str]:
        return user.userms.identifiers if user.userms else []

    @staticmethod
    def resolve_userms_video_num_limit(user: UserProfile) -> int | None:
        return user.userms.video_num_limit if user.userms else None


AdminUserProfileOut = create_schema(
    UserProfile,
    name='AdminUserProfileOut',
    fields=[
        'id', 'username', 'email',
        'signature', 'country',
        'is_banned', 'is_staff',
        'left_realname_n', 'left_avatar_n', 'left_signature_n',
        'last_change_avatar', 'last_change_signature',
        'date_updated', 'can_hide_realname', 'hide_realname',
    ],
    custom_fields=[
        *PUBLIC_NAME_FIELDS,
        ('userms_id', int | None, None),
        ('userms_identifiers', list[str], []),
        ('userms_video_num_limit', int | None, None),
    ],
    base_class=AdminUserProfileOutBase,
)

ADMIN_USERPROFILE_FIELDS = (
    'username', 'email',
    'signature', 'country', 'is_banned',
    'left_realname_n', 'left_avatar_n', 'left_signature_n', 'can_hide_realname',
)

AdminUserProfileUpdateIn = create_schema(
    UserProfile,
    name='AdminUserProfileUpdateIn',
    fields=list(ADMIN_USERPROFILE_FIELDS),
    optional_fields='__all__',
    custom_fields=[(field, str, None) for field in NAME_FIELDS],
)


@router.get('/admin/detail/{user_id}', response=AdminUserProfileOut)
@decorate_view(staff_required)
def get_user_profile_admin(request, user_id: int):
    """
    - staff_required
    """
    return get_object_or_404(UserProfile.objects.select_related('userms'), id=user_id)


@router.patch('/admin/update/{user_id}', response=AdminUserProfileOut)
@decorate_view(staff_required)
def update_user_profile_admin(request, user_id: int, data: AdminUserProfileUpdateIn = Form(...)):  # noqa: B008
    """
    - staff_required
    """
    get_object_or_404(UserProfile, id=user_id)
    return update_admin_profile(user_id, data.model_dump(exclude_unset=True), request.user)


@router.get('/info/0', response=SelfUserInfoOut)
@decorate_view(login_required_error, cache_control(max_age=5), ratelimit(key='user', rate='60/m'))
def get_self_info(request):
    """
    - login_required_error
    - cache_control(max_age=5)
    - ratelimit(key='user', rate='60/m')
    """
    return request.user


@router.get('/info/{user_id}', response=UserInfoOut)
@decorate_view(cache_control(max_age=5))
def get_user_info(request, user_id: int):
    """
    - Rate limited by nginx
    - cache_control(max_age=5)
    """
    return get_object_or_404(UserProfile, id=user_id)


@router.get('/infobulk', response=List[UserInfoOut])
@decorate_view(ratelimit(key='ip', rate='2/s'))
def get_user_info_bulk(request, ids: str):
    """
    The format of `ids` is a comma-separated list of user ids. Example: `ids=1,2,3`
    """
    user_ids: List[int] = ids.split(',')
    return UserProfile.objects.filter(id__in=user_ids)


@router.get(path='/infoupdated', response=List[int])
@decorate_view(ratelimit(key='ip', rate='2/s'))
def get_user_info_updated(request, since: int):
    """
    Get the ids of users that have been updated since the given timestamp.
    """
    since_datetime = datetime.fromtimestamp(since / 1000, tz=timezone.utc)
    return UserProfile.objects.filter(date_updated__gte=since_datetime).values_list('id', flat=True)


@router.get('/identifier', response=List[str])
@decorate_view(ratelimit(key='ip', rate='2/s'))
def get_user_identifier(request, user_id: int):
    """
    - ratelimit(key='ip', rate='2/s')
    """
    user = get_object_or_404(UserProfile, id=user_id)
    return user.userms.identifiers if user.userms else []


@router.get('/avatar/{user_id}')
def get_user_avatar(request, user_id: int):
    """
    - Rate limited by nginx
    """
    avatar_name = UserProfile.objects.filter(id=user_id).values_list('avatar', flat=True).first()
    if not avatar_name:
        return HttpResponseNotFound()
    if settings.DEBUG:
        try:
            return FileResponse(default_storage.open(avatar_name, 'rb'), filename=avatar_name)
        except FileNotFoundError:
            return HttpResponseNotFound()
    response = HttpResponse()
    del response['Content-Type']
    response['X-Accel-Redirect'] = f'{AVATAR_ACCEL_REDIRECT_PREFIX}{quote(avatar_name, safe="/")}'
    return response


@router.get('/videolist', response=list[VideoMetadataOut])
@decorate_view(ratelimit(key='ip', rate='1/s'))
def get_user_videos(request, user_id: int):
    """
    - ratelimit(key='ip', rate='1/s')
    """
    user = get_object_or_404(UserProfile, id=user_id)
    queryset = VideoModel.objects.filter(player=user)
    if user != request.user:
        queryset = queryset.filter(ongoing_tournament=False)
    return queryset.only(*VIDEO_METADATA_FIELDS)


class UpdateUserProfileIn(Schema):
    realname: str = None
    signature: str = None
    firstname: str = None
    lastname: str = None
    hide_realname: bool | None = None


@router.post('/update_profile')
@decorate_view(
    login_required_error,
    banned_blocked,
    ratelimit(key='ip', rate='1/m'),
)
def update_user_profile(request: HttpRequest, data: UpdateUserProfileIn = Form(...)):  # noqa: B008
    """
    - login_required_error
    - banned_blocked
    - ratelimit(key='ip', rate='1/m')

    ### Example response
    ```json
    {
        "realname": {"type": "success"},
        "signature": None,
        "firstname": {"type": "error", "object": "firstname", "category": "validation"},
        "lastname": {"type": "error", "object": "censorship", "category": "illegal"}
    }
    ```

    ### Reference
    Response is a `dict[str, None | dict]`. The keys are `realname`, `signature`, `firstname` and `lastname`, plus `hide_realname` when submitted. For the values,
    - If the field is not requested, the value is `None`.
    - If the field is successfully updated (including the case where the value doesn't change), the value is `{"type": "success"}`.
    - If the field is not successfully updated, the value is `{"type": "error", "object": str, "category": str}`. The cases for `object` and `category` are listed below.

    Name changes and an optional `hide_realname` are committed together. Any failure
    rolls back this entire group; signature updates retain their independent result.

    |object|category|Description|
    |---|---|---|
    |censorship|unknown|The censorship backend raises an unexpected exception.|
    |censorship|illegal|The realname is blocked by censorship.|
    |database|validation|The value doesn't pass the database's validation.|
    |name|exist|The name fields cannot be updated after they are set. The user must contact a moderator to request a change.|
    |signature|cooldown|The user doesn't have budget for this service.|
    |signature|expTime|The signature can only be updated by a sub200 player.|

    ### 403 Forbidden
    If the user doesn't have permission to update any of the fields:
    - The user is not logged in.
    - The user is banned.
    """
    user: UserProfile = request.user
    user_ip = request.get_host()

    data_out: dict[str, None | dict] = {
        'realname': None,
        'firstname': None,
        'lastname': None,
        'signature': None,
    }
    success_out = {'type': 'success'}

    names = {field: getattr(data, field) for field in NAME_FIELDS if getattr(data, field) is not None}
    name_results = list(names)
    if data.hide_realname is not None:
        name_results.append('hide_realname')
    if name_results:
        try:
            user = update_user_names(user.pk, names, user_ip, data.hide_realname)
            for field in name_results:
                data_out[field] = success_out
        except ExceptionToResponse as e:
            for field in name_results:
                data_out[field] = e.body

    if (signature := data.signature) is not None:
        try:
            try_update_user_signature(user, signature, user_ip)
            data_out['signature'] = success_out
        except ExceptionToResponse as e:
            data_out['signature'] = e.body

    return data_out


@router.post('/update_avatar')
@decorate_view(
    login_required_error,
    banned_blocked,
    ratelimit(key='ip', rate='1/m'),
)
def update_user_avatar(request, avatar: File[UploadedFile]):
    """
    - login_required_error
    - banned_blocked
    - ratelimit(key='ip', rate='1/m')

    ### Success response
    ```json
    {"type": "success"}
    ```

    ### Error response
    ```json
    {"type": "error", "object": str, "category": str}
    ```
    |object|category|Description|
    |---|---|---|
    |avatar|validation|The file doesn't pass the database's validation.|
    |censorship|unknown|The censorship backend raises an unexpected exception.|
    |censorship|illegal|The realname is blocked by censorship.|

    ### 403 Forbidden
    The request should not have been sent from a normal frontend.
    - The user is not logged in.
    - The user is not a sub200 player.
    - The user doesn't have enough budget for the service.
    """
    user: UserProfile = request.user

    if not has_sub200_expert_video(user):
        return HttpResponseForbidden()

    refresh_avatar_chance(user)
    if user.left_avatar_n <= 0:
        return HttpResponseForbidden()

    try:
        is_valid = verify_image(avatar.read(), user.id, request.get_host())
    except Exception:
        raise ExceptionToResponse('censorship', 'unknown')

    if not is_valid:
        raise ExceptionToResponse('censorship', 'illegal')

    user.avatar = avatar
    user.left_avatar_n -= 1
    logger.info(f'用户 {user.username}#{user.id} 修改头像')
    try:
        user.save(update_fields=['avatar', 'left_avatar_n', 'date_updated'])
    except ValidationError:
        raise ExceptionToResponse('avatar', 'validation')

    return {'type': 'success'}
