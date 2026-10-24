import json
from typing import Annotated
from urllib.parse import quote

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import FileResponse, HttpRequest, HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from django_ratelimit.decorators import ratelimit
from ninja import Field, Form, Query, Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.orm import create_schema
from ninja.security import django_auth_superuser
from pydantic import StrictInt

from config.text_choices import MS_TextChoices
from userprofile.decorators import staff_required
from userprofile.models import UserProfile
from .cache import cache, newest_cache
from .models import ExpandVideoModel, STNB_COEFFICIENTS, VideoModel
from .schema import ParsedVideoOut, PUBLIC_VIDEO_METADATA_FIELDS, PublicVideoMetadataOut, VIDEO_INFO_BATCH_LIMIT, VIDEO_METADATA_FIELDS, VideoBaseOut, VideoMetadataOut
from .services import delete_video_by_id
from .view_utils import video_all_fields

router = Router()
VIDEO_ACCEL_REDIRECT_PREFIX = '/internal-media/'
VideoDeleteIn = create_schema(VideoModel, name='VideoDeleteIn', fields=['id'], custom_fields=[('id', Annotated[StrictInt, Field(gt=0, le=2**63 - 1)], ...)])


class VideoDeleteAccessOut(Schema):
    csrf_token: str


class VideoDeleteOut(Schema):
    id: int
    deleted: bool
    affected_tournament_ids: list[int]


def _parse_video_ids(ids: str):
    parts = ids.split(',')
    if len(parts) > VIDEO_INFO_BATCH_LIMIT or not parts or any(len(part) > 19 or not part.isascii() or not part.isdecimal() or int(part) < 1 or int(part) > 2**63 - 1 for part in parts):
        raise HttpError(400, f'Expected 1 to {VIDEO_INFO_BATCH_LIMIT} positive video IDs.')
    return list(dict.fromkeys(map(int, parts)))


def _visible_video_info(request, videos):
    if request.user.is_authenticated:
        return videos.filter(Q(ongoing_tournament=False) | Q(player_id=request.user.pk))
    return videos.filter(ongoing_tournament=False)


# Explicit groups keep Ninja's shared Operation.run wrapper from sharing endpoint quotas.
@router.get('/staticdetailbatch', response=list[ParsedVideoOut])
@decorate_view(ratelimit(group='video-staticdetailbatch', key='ip', rate='5/s'))
def get_static_video_detail_batch(request, ids: str):
    """
    - ratelimit(group='video-staticdetailbatch', key='ip', rate='5/s')

    Stable file-derived fields. Unpublished videos are only returned to their owner, including for staff requests.
    """
    videos = VideoModel.objects.filter(id__in=_parse_video_ids(ids))
    return _visible_video_info(request, videos).select_related('video')


@router.get('/abstractbulk', response=list[PublicVideoMetadataOut])
@decorate_view(ratelimit(group='video-abstractbulk', key='ip', rate='1/2s'))
def get_video_abstract_bulk(request, first: int, count: int):
    """
    - ratelimit(group='video-abstractbulk', key='ip', rate='1/2s')

    Current website fields for public video IDs from `first` to `first + count - 1`. Count is capped at 10000.
    Unpublished videos are skipped for all callers, including their owner and staff.
    """
    first = max(1, first)
    count = max(1, min(10000, count))
    return VideoModel.objects.filter(id__gte=first, id__lt=first + count, ongoing_tournament=False).only(*PUBLIC_VIDEO_METADATA_FIELDS)


@router.get('/newest_queue', response=list[VideoMetadataOut])
@decorate_view(ratelimit(key='ip', rate='5/s'))
def get_newest_queue(request):
    """
    - ratelimit(key='ip', rate='5/s')

    Read public queue metadata directly from the cached snapshot, without querying videos.
    """
    videos = []
    for video_id, raw in cache.hgetall(newest_cache.key).items():
        cached = json.loads(raw)
        videos.append({
            'id': int(video_id), 'player_id': cached['player_id'], 'upload_time': cached['time'],
            'state': cached['state'], 'ongoing_tournament': False,
        })
    return videos


@router.post('/newest_queue/remove', response={204: None})
@decorate_view(staff_required)
def remove_newest_queue_video(request, video_id: int = Form(..., alias='id')):  # noqa: B008
    """
    - staff_required
    """
    cache.hdel(newest_cache.key, video_id)
    return 204, None


@router.get('/query')
@decorate_view(ratelimit(key='ip', rate='60/m'))
def video_query(request, level: MS_TextChoices.Level, mode: MS_TextChoices.Mode, o: str = 'timems', r: bool = False, ps: int = 20, page: int = 1, bmin: int = 0, bmax: int = 1000, nf: bool = False, states: list[MS_TextChoices.State] = Query(None, alias='s[]')):  # noqa: B008
    """
    - ratelimit(key='ip', rate='60/m')
    """
    if o == 'player__realname' or (o not in video_all_fields and o != 'stnb'):
        raise HttpError(400, 'Invalid sort field.')
    videos = VideoModel.objects.filter(level=level, mode=mode, bv__range=(bmin, bmax))
    if nf:
        videos = videos.filter(right_ce=0)
    if states:
        videos = videos.filter(state__in=states)
    if not request.user.is_staff:
        videos = videos.filter(ongoing_tournament=False)
    videos = videos.annotate(stnb=F('iqg') * STNB_COEFFICIENTS.get(level))
    order = ('-' if r else '') + o
    orderby = (order,) if o == 'timems' else (order, 'timems')
    videos = videos.order_by(*orderby).values('id', 'upload_time', 'state', 'ongoing_tournament', 'player__id')
    paginator = Paginator(videos, max(1, min(ps, 100)))
    rows = list(paginator.get_page(page))
    players = UserProfile.objects.in_bulk({row['player__id'] for row in rows})
    for row in rows:
        row['player__realname'] = players[row['player__id']].realname
    return {'count': paginator.count, 'videos': rows}


@router.get('/admin/detail/{video_id}')
@decorate_view(staff_required)
def get_video_admin(request, video_id: int):
    """
    - staff_required
    """
    fields = ['player', 'upload_time', 'state', 'software', 'level', 'mode', 'right_ce', 'timems', 'bv', 'bvs', 'ongoing_tournament']
    fields.extend('video__' + field.name for field in ExpandVideoModel._meta.get_fields())
    row = VideoModel.objects.filter(pk=video_id).values(*fields, player__realname=F('player___realname')).first()
    if row is None:
        raise HttpError(404, 'Video not found.')
    return row


@router.post('/admin/delete', auth=django_auth_superuser, response=VideoDeleteOut)
def delete_video_admin(request: HttpRequest, data: VideoDeleteIn):
    """
    - auth=django_auth_superuser (Django session, superuser only, CSRF required)

    Delete one video using a JSON object, e.g. {"id": 123}. The ID must be a positive integer.
    A missing video returns deleted=false, allowing a caller to reconcile a previous uncertain response.
    Database deletion is atomic. Clients may send multiple requests sequentially and stop on any error.
    Existing deletion signals clean up expansions, files and rankings. The newest queue retains its snapshots.

    Warning: tournament videos become unavailable, but saved tournament results are not recalculated.
    Later explicit recalculation follows each tournament type and score source. Affected tournament IDs
    are returned and logged as a warning; private notifications are not implemented yet.
    """
    return delete_video_by_id(data.id, actor_id=request.auth.pk)


@router.get('/admin/delete', auth=django_auth_superuser, response=VideoDeleteAccessOut)
@decorate_view(ensure_csrf_cookie, cache_control(no_store=True))
def get_video_delete_access(request: HttpRequest):
    """
    - auth=django_auth_superuser (Django session, superuser only)
    - ensure_csrf_cookie
    - cache_control(no_store=True)

    Check access to the hidden video deletion page and initialize its CSRF cookie and request token.
    """
    return {'csrf_token': get_token(request)}


@router.get('/query_by_id')
@decorate_view(ratelimit(key='ip', rate='60/m'))
def video_query_by_id(request, user_id: int = Query(..., alias='id')):  # noqa: B008
    """
    - ratelimit(key='ip', rate='60/m')
    """
    user = get_object_or_404(UserProfile, id=user_id)
    videos = VideoModel.objects.filter(player=user)
    if request.user != user:
        videos = videos.filter(ongoing_tournament=False)
    # Self-contained export endpoint, also used outside the website.
    return list(videos.values(
        'id', 'upload_time', 'end_time', 'level', 'mode', 'timems', 'bv', 'bvs', 'state', 'video__identifier',
        'software', 'right_ce', 'flag', 'cell0', 'cell1', 'cell2', 'cell3', 'cell4', 'cell5', 'cell6', 'cell7', 'cell8', 'left', 'right', 'double', 'op', 'isl', 'path', 'pluck',
    ))


def _can_request_video(request: HttpRequest, video: VideoModel):
    if not video.ongoing_tournament:
        return True
    if not request.user.is_authenticated:
        return False
    return request.user.id == video.player_id


def _video_file_response(request: HttpRequest, video_id: int):
    video = get_object_or_404(VideoModel, id=video_id)
    if not _can_request_video(request, video):
        raise HttpError(403, 'Forbidden.')
    file_name = video.file.name
    if settings.DEBUG:
        try:
            response = FileResponse(default_storage.open(file_name, 'rb'))
        except FileNotFoundError:
            raise HttpError(404, 'Video file not found.')
    else:
        response = HttpResponse()
        response['X-Accel-Redirect'] = f'{VIDEO_ACCEL_REDIRECT_PREFIX}{quote(file_name, safe="/")}'
    response['Content-Type'] = 'application/octet-stream'
    file_name_uri = quote(file_name.split('/')[-1])
    response['Content-Disposition'] = f'attachment; filename="{file_name_uri}"'
    return response


VideoFullOut = create_schema(
    VideoModel,
    fields=[
        'id', 'player',
        'software', 'level', 'mode', 'state',
        'timems', 'bv', 'path', 'flag', 'op', 'isl',
        'upload_time', 'end_time', 'file_size',
        'left', 'right', 'double', 'cl',
        'left_ce', 'right_ce', 'double_ce', 'ce',
        'cell0', 'cell1', 'cell2', 'cell3', 'cell4', 'cell5', 'cell6', 'cell7', 'cell8',
    ],
    custom_fields=[
        ('video__identifier', str, ''),
        ('cl', int | None, None),
        ('ce', int | None, None),
    ],
)


@router.get('/preview')
@decorate_view(ratelimit(key='ip', rate='20/m'))
def video_preview(request: HttpRequest, video_id_with_extension: str = Query(..., alias='id')):  # noqa: B008
    """
    - ratelimit(key='ip', rate='20/m')
    """
    try:
        video_id = int(video_id_with_extension[:-4])
    except ValueError:
        raise HttpError(400, 'Invalid video id.')
    response = _video_file_response(request, video_id)
    response['Access-Control-Expose-Headers'] = 'Content-Disposition'
    return response


@router.get('/download/{video_id}')
@decorate_view(ratelimit(key='ip', rate='20/m'))
def video_download(request: HttpRequest, video_id: int):
    """
    - ratelimit(key='ip', rate='20/m')
    """
    return _video_file_response(request, video_id)


@router.get('/review_queue', response=list[VideoMetadataOut])
@decorate_view(ratelimit(key='ip', rate='1/s'))
def get_review_queue(request):
    """
    - ratelimit(key='ip', rate='1/s')
    """
    videos = VideoModel.objects.filter(state=MS_TextChoices.State.PLAIN)
    if not request.user.is_staff:
        videos = videos.filter(ongoing_tournament=False)

    return videos.only(*VIDEO_METADATA_FIELDS)


@router.get('/infobulk', response=list[VideoBaseOut])
@decorate_view(ratelimit(group='video-infobulk', key='ip', rate='1/s'))
def get_video_info_bulk(request, first: int, count: int):
    """
    - ratelimit(group='video-infobulk', key='ip', rate='1/s')

    Video id from `first` to `first + count - 1`. Hidden videos are skipped. Count is capped at 2000.
    """
    first = max(1, first)
    count = max(1, min(2000, count))

    return VideoModel.objects.filter(id__gte=first, id__lt=first + count, ongoing_tournament=False)


@router.get('/detailbulk', response=list[VideoFullOut])
@decorate_view(ratelimit(group='video-detailbulk', key='ip', rate='1/s'))
def get_video_detail_bulk(request, first: int, count: int):
    """
    - ratelimit(group='video-detailbulk', key='ip', rate='1/s')

    Video id from `first` to `first + count - 1`. Hidden videos are skipped. Count is capped at 500.
    """
    first = max(1, first)
    count = max(1, min(500, count))

    return VideoModel.objects.filter(id__gte=first, id__lt=first + count, ongoing_tournament=False)
