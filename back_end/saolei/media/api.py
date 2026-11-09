"""作品页 Ninja API；接口清单见 MEDIA_PLAN.md 第 8 节。"""

from django.db import DatabaseError, IntegrityError
from django.http import HttpRequest
from django_ratelimit.decorators import ratelimit
from ninja import Router
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.security import django_auth_superuser

from accountlink.models import AccountLinkQueue
from userprofile.decorators import banned_blocked, login_required_error, staff_required
from . import cache, clients, services
from .decorators import media_banned_blocked
from .models import Media, UserMedia
from .schema import (
    BanIn, DeletedOut, EditIn, IdIn, LikeIn, LikeOut, MEDIA_QUERY_LIMIT, MediaOut, MediaPageOut,
    MediaQueryError, MediaQueryOut, MeOut, RejectIn, SubmitIn, UserRankingPageOut, VerifyIn,
)
from .utils import (
    format_to_platform, MediaStatus, normalize_external_author_id, normalize_language, parse_media_url,
)

router = Router()

MEDIA_PAGE_MAX_COUNT = 50
MEDIA_DETAIL_BATCH_LIMIT = 50
MEDIA_QUERY_FIELDS = ('title', 'suffix')
MEDIA_QUERY_MODES = ('exact', 'iexact', 'contains', 'icontains', 'startswith', 'istartswith', 'endswith', 'iendswith', 'regex')
MEDIA_QUERY_RESPONSES = {200: MediaQueryOut, 400: MediaQueryError}
MEDIA_SORT_FIELDS = {'hot': 'hot_value', 'likes': 'likes', 'created_at': 'created_at'}


def _service(func, *args, **kwargs):
    """service 层只抛业务状态错误，统一在 API 层转成 HttpError。"""
    try:
        return func(*args, **kwargs)
    except services.MediaServiceError as exc:
        raise HttpError(exc.status_code, exc.message) from exc


def _page_bounds(start, count, maximum=MEDIA_PAGE_MAX_COUNT):
    return max(0, start), max(1, min(count, maximum))


def _media_page(items, total, start):
    return {'items': list(items), 'total': total, 'start': start, 'anchor': cache.get_hot_reference()}


def _ranked_media(media_ids):
    rows = Media.objects.filter(pk__in=media_ids, status=MediaStatus.VERIFIED).in_bulk()
    return [rows[media_id] for media_id in media_ids if media_id in rows]


def _parse_media_ids(value):
    parts = (value or '').split(',')
    if not parts or len(parts) > MEDIA_DETAIL_BATCH_LIMIT or any(not part.isascii() or not part.isdecimal() or not 1 <= int(part) <= 2**63 - 1 for part in parts):
        raise HttpError(400, f'Expected 1 to {MEDIA_DETAIL_BATCH_LIMIT} positive media IDs.')
    return list(dict.fromkeys(map(int, parts)))


def _fetch_optional(media_format, suffix):
    try:
        return clients.fetch_media_metadata_optional(media_format, suffix)
    except clients.MediaFetchError as exc:
        raise HttpError(exc.status_code, exc.category) from exc


def _page_queryset(queryset, start, count):
    total = queryset.count()
    return list(queryset[start:start + count]), total


@router.get('/ranking', response=MediaPageOut)
@decorate_view(ratelimit(key='ip', rate='5/s', group='media-ranking'))
def get_ranking(request, sort: str = 'hot', start: int = 0, count: int = 20):
    """
    - ratelimit(key='ip', rate='5/s', group='media-ranking')

    热门 / 精品 tab：两个作品 zset 分页，只返回 status='verified' 的作品。
    """
    if sort not in ('hot', 'likes'):
        raise HttpError(400, 'Unknown media ranking sort.')
    start, count = _page_bounds(start, count)
    key = cache.MEDIA_RANK_HOT if sort == 'hot' else cache.MEDIA_RANK_LIKES
    media_ids, total = cache.get_ranking(key, start, count)
    return _media_page(_ranked_media(media_ids), total, start)


@router.get('/user-ranking', response=UserRankingPageOut)
@decorate_view(ratelimit(key='ip', rate='5/s', group='media-user-ranking'))
def get_user_ranking(request, sort: str = 'hot', start: int = 0, count: int = 20):
    """
    - ratelimit(key='ip', rate='5/s', group='media-user-ranking')

    排行榜页《作品》tab：作者聚合榜，只统计已审核作品。
    """
    if sort not in ('hot', 'likes'):
        raise HttpError(400, 'Unknown media ranking sort.')
    start, count = _page_bounds(start, count)
    rows, total = cache.get_user_ranking(sort, start, count)
    items = [{'user_id': user_id, 'hot': hot, 'likes': likes} for user_id, hot, likes in rows]
    return {'items': items, 'total': total, 'start': start, 'anchor': cache.get_hot_reference()}


@router.get('/latest', response=MediaPageOut)
@decorate_view(ratelimit(key='ip', rate='5/s', group='media-latest'))
def get_latest(request, start: int = 0, count: int = 20):
    """
    - ratelimit(key='ip', rate='5/s', group='media-latest')

    《最新》tab：不走 Redis，按外站发表时间倒序，同时间用 id 做 tie-breaker。
    """
    start, count = _page_bounds(start, count)
    queryset = Media.objects.filter(status=MediaStatus.VERIFIED).order_by('-created_at', '-id')
    items, total = _page_queryset(queryset, start, count)
    return _media_page(items, total, start)


@router.get('/pending', response=MediaPageOut)
@decorate_view(ratelimit(key='ip', rate='5/s', group='media-pending'))
def get_pending(request, start: int = 0, count: int = 20):
    """
    - ratelimit(key='ip', rate='5/s', group='media-pending')

    审核中 tab：所有访客可见，按本站投稿时间倒序。
    """
    start, count = _page_bounds(start, count)
    queryset = Media.objects.filter(status=MediaStatus.PENDING).order_by('-submitted_at', '-id')
    items, total = _page_queryset(queryset, start, count)
    return _media_page(items, total, start)


@router.get('/detailbatch', response=list[MediaOut])
@decorate_view(ratelimit(key='ip', rate='5/s', group='media-detail'))
def get_detail_batch(request, ids: str):
    """
    - ratelimit(key='ip', rate='5/s', group='media-detail')

    批量详情：ids 为逗号分隔的正整数，最多 50 个，按请求顺序返回存在的行。
    """
    media_ids = _parse_media_ids(ids)
    rows = Media.objects.in_bulk(media_ids)
    return [rows[media_id] for media_id in media_ids if media_id in rows]


@router.get('/query/{mode}', response=MEDIA_QUERY_RESPONSES, exclude_unset=True)
@decorate_view(ratelimit(key='ip', rate='6/m', group='media-query', block=False))
def query_media(request, mode: str, value: str, field: str = 'title', limit: int = MEDIA_QUERY_LIMIT):
    """
    - ratelimit(key='ip', rate='6/m', group='media-query', block=False)

    数据库页作品匹配查找：title / suffix，最多 1000 条，含 rejected 作品；regex 走 MySQL ICU。
    """
    if getattr(request, 'limited', False):
        raise HttpError(429, 'Media query rate limit exceeded. Please try again later.')
    if mode not in MEDIA_QUERY_MODES or field not in MEDIA_QUERY_FIELDS:
        raise HttpError(400, 'Unsupported media query mode or field.')
    if not 1 <= len(value) <= 200:
        raise HttpError(400, 'Invalid query length.')
    limit = max(1, min(limit, MEDIA_QUERY_LIMIT))
    queryset = Media.objects.filter(**{f'{field}__{mode}': value}).order_by('id')
    try:
        items = list(queryset[:limit + 1])
    except DatabaseError as exc:
        if mode == 'regex' and exc.args and 3684 <= exc.args[0] <= 3700:
            raise HttpError(400, 'Invalid regular expression or regular expression resource limit exceeded.') from exc
        raise
    if len(items) > limit:
        return 400, {'code': 'too_many_matches', 'detail': f'Media query matches more than {limit} results. Please narrow your search.'}
    return {'items': items, 'total': len(items)}


@router.get('/user/{user_id}', response=MediaPageOut)
@decorate_view(ratelimit(key='ip', rate='30/m', group='media-user'))
def get_user_media(request, user_id: int, sort: str = 'hot', order: str = 'desc', page: int = 1,
                   pageSize: int = 20):
    """
    - ratelimit(key='ip', rate='30/m', group='media-user')

    个人主页作品 tab：展示所有状态且对所有人可见，直接查库分页。
    """
    if sort not in MEDIA_SORT_FIELDS or order not in ('asc', 'desc'):
        raise HttpError(400, 'Unknown media sort or order.')
    page = max(1, page)
    page_size = max(1, min(pageSize, MEDIA_PAGE_MAX_COUNT))
    prefix = '-' if order == 'desc' else ''
    queryset = Media.objects.filter(user_id=user_id).order_by(f'{prefix}{MEDIA_SORT_FIELDS[sort]}', f'{prefix}id')
    start = (page - 1) * page_size
    items, total = _page_queryset(queryset, start, page_size)
    return _media_page(items, total, start)


@router.get('/me', response=MeOut)
@decorate_view(ratelimit(key='user', rate='30/m', group='media-me', block=True), login_required_error)
def get_me(request):
    """
    - login_required_error
    - ratelimit(key='user', rate='30/m', group='media-me', block=True)

    未创建 UserMedia 行时返回零值，不写库。
    """
    profile = UserMedia.objects.filter(pk=request.user.pk).first()
    return {
        'balance': services.get_balance(request.user),
        'likes_sent': profile.likes_sent if profile else 0,
        'banned': profile.banned if profile else False,
    }


@router.post('/submit', response=MediaOut)
@decorate_view(ratelimit(key='user', rate='10/h', group='media-submit', block=True), media_banned_blocked,
               banned_blocked, login_required_error)
def submit_media(request, data: SubmitIn):
    """
    - login_required_error
    - banned_blocked
    - media_banned_blocked
    - ratelimit(key='user', rate='10/h', group='media-submit', block=True)

    外站超时 / 上游不可用降级为待补全投稿；外站作者 id 只在此请求内用于归属核验，不写入 Media。
    """
    try:
        media_format, suffix = parse_media_url(data.url)
        language = normalize_language(data.language)
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc
    identifiers = {
        str(identifier).strip() for identifier in AccountLinkQueue.objects.filter(
            platform=format_to_platform(media_format), userprofile=request.user, verified=True,
        ).values_list('identifier', flat=True)
    }
    if not identifiers:
        raise HttpError(403, 'A verified account link is required.')
    metadata = _fetch_optional(media_format, suffix)
    if metadata is None:
        return _service(services.create_media, request.user, media_format=media_format, suffix=suffix,
                        language=language, metadata_pending=True)
    if metadata.author_id not in identifiers:
        raise HttpError(403, 'author_mismatch')
    return _service(services.create_media, request.user, media_format=media_format, suffix=suffix,
                    language=language, title=metadata.title, created_at=metadata.created_at)


@router.post('/like', response=LikeOut)
@decorate_view(ratelimit(key='user', rate='1/s', group='media-like', block=True), banned_blocked, login_required_error)
def like_media(request, data: LikeIn):
    """
    - login_required_error
    - banned_blocked
    - ratelimit(key='user', rate='1/s', group='media-like', block=True)

    每次只投 1 个红宝石；审核中作品也可投喂，但只写 DB 不写 zset。
    每 UTC 自然日最多 10 次成功投喂，由 service 层与余额扣减同事务计数。
    """
    return _service(services.like_media, request.user, data.media_id)


@router.get('/admin/rejected', response=MediaPageOut)
@decorate_view(staff_required)
def get_rejected(request, start: int = 0, count: int = 20):
    """
    - staff_required (GET 只读，不校验 CSRF)

    查看已驳回作品；替代原 GET /admin/deletion-log。
    """
    start, count = _page_bounds(start, count)
    queryset = Media.objects.filter(status=MediaStatus.REJECTED).order_by('-submitted_at', '-id')
    items, total = _page_queryset(queryset, start, count)
    return _media_page(items, total, start)


@router.post('/admin/verify', response=MediaOut)
@decorate_view(staff_required)
def verify_media(request, data: VerifyIn):
    """
    - staff_required (role check + Django CSRF on unsafe methods)

    降级投稿的 external_author_id 是一次性核验输入：查 AccountLinkQueue 确认该外站账号属于投稿人，不落库。
    """
    media = Media.objects.filter(pk=data.id).first()
    if media is None:
        raise HttpError(404, 'Media not found.')
    if media.metadata_pending:
        if not data.title or not data.title.strip():
            raise HttpError(400, 'A title is required for degraded submissions.')
        if not data.external_author_id:
            raise HttpError(400, 'An external author id is required for degraded submissions.')
        try:
            identifier = normalize_external_author_id(data.external_author_id)
        except ValueError as exc:
            raise HttpError(400, 'Invalid external author id.') from exc
        linked = AccountLinkQueue.objects.filter(
            platform=format_to_platform(media.format), identifier=identifier,
            userprofile_id=media.user_id, verified=True,
        ).exists()
        if not linked:
            raise HttpError(403, 'The external account does not belong to the submitter.')
    return _service(services.verify_media, data.id, request.user.pk, title=data.title, created_at=data.created_at)


@router.post('/admin/reject', response=MediaOut)
@decorate_view(staff_required)
def reject_media(request, data: RejectIn):
    """
    - staff_required (role check + Django CSRF on unsafe methods)

    pending → rejected，不删行、退还红宝石并立刻清零 likes / hot_value。
    """
    return _service(services.reject_media, data.id, request.user.pk, data.reason)


@router.post('/admin/reopen', response=MediaOut)
@decorate_view(staff_required)
def reopen_media(request, data: IdIn):
    """
    - staff_required (role check + Django CSRF on unsafe methods)

    rejected → pending，复用同一行。
    """
    return _service(services.reopen_media, data.id, request.user.pk)


@router.post('/admin/ban', response=bool)
@decorate_view(staff_required)
def ban_media_user(request, data: BanIn):
    """
    - staff_required (role check + Django CSRF on unsafe methods)

    只禁止投稿，不影响浏览与投喂。
    """
    services.set_media_banned(data.user_id, True)
    return True


@router.post('/admin/unban', response=bool)
@decorate_view(staff_required)
def unban_media_user(request, data: BanIn):
    """
    - staff_required (role check + Django CSRF on unsafe methods)
    """
    services.set_media_banned(data.user_id, False)
    return True


@router.post('/admin/edit', response=MediaOut)
@decorate_view(staff_required)
def edit_media(request, data: EditIn):
    """
    - staff_required (role check + Django CSRF on unsafe methods)

    仅 pending / rejected 可编辑；改 url 会重跑 URL 解析与 format+suffix 唯一校验，metadata_pending 仍由审核补录处理。
    """
    media = Media.objects.filter(pk=data.id).first()
    if media is None:
        raise HttpError(404, 'Media not found.')
    if media.status == MediaStatus.VERIFIED:
        raise HttpError(409, 'Verified media cannot be edited.')
    fields = []
    if data.title is not None:
        media.title = str(data.title).strip()[:200]
        fields.append('title')
    if data.language is not None:
        try:
            media.language = normalize_language(data.language)
        except ValueError as exc:
            raise HttpError(400, str(exc)) from exc
        fields.append('language')
    if data.created_at is not None:
        media.created_at = data.created_at
        fields.append('created_at')
    if data.url is not None:
        try:
            new_format, new_suffix = parse_media_url(data.url)
        except ValueError as exc:
            raise HttpError(400, str(exc)) from exc
        if Media.objects.filter(format=new_format, suffix=new_suffix).exclude(pk=media.pk).exists():
            raise HttpError(409, '该作品已投稿过，不可重复投稿')
        media.format, media.suffix = new_format, new_suffix
        fields += ['format', 'suffix']
    if not fields:
        raise HttpError(400, 'No fields to update.')
    try:
        media.save(update_fields=fields)
    except IntegrityError:
        raise HttpError(409, '该作品已投稿过，不可重复投稿') from None
    return media


@router.post('/admin/delete', auth=django_auth_superuser, response=DeletedOut)
def delete_media_admin(request: HttpRequest, data: IdIn):
    """
    - auth=django_auth_superuser (Django session, superuser only, CSRF required)

    站长硬删除已通过作品：退还红宝石、写快照日志并回退四个 zset。
    """
    return {'deleted': _service(services.hard_delete_media, data.id, request.auth.pk)}
