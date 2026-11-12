import logging
from typing import Literal

from django.db import DatabaseError
from django.db.models.functions import Collate
from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit
from ninja import Field, Form, Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.orm import create_schema
from pydantic import NonNegativeInt

from userprofile.decorators import staff_required
from userprofile.models import UserProfile
from .models import Identifier
from .services import bind_identifier, set_safe, unbind_identifier

router = Router()
logger = logging.getLogger(__name__)
IdentifierMatch = Literal['exact', 'iexact', 'contains', 'icontains', 'startswith', 'istartswith', 'endswith', 'iendswith', 'regex']
QUERY_MATCH_LIMIT = 1000


IdentifierOut = create_schema(
    Identifier,
    fields=['identifier'],
    custom_fields=[('user_id', int | None, None), ('safe', bool | None, None)],
)


class IdentifierQueryOut(Schema):
    items: list[IdentifierOut]


class IdentifierQueryError(Schema):
    code: Literal['too_many_matches']
    detail: str


QUERY_RESPONSES = {200: IdentifierQueryOut, 400: IdentifierQueryError}


def _identifier_result(identifier: Identifier, *, staff: bool):
    user = getattr(identifier.userms, 'parent', None) if identifier.userms_id is not None else None
    result = {'identifier': identifier.identifier, 'user_id': user.id if user else None}
    if staff:
        result['safe'] = identifier.safe
    return result


def _query_results(identifiers, *, staff: bool):
    items = list(identifiers.select_related('userms__parent').order_by('id')[:QUERY_MATCH_LIMIT + 1])
    if len(items) > QUERY_MATCH_LIMIT:
        return 400, {'code': 'too_many_matches', 'detail': f'Identifier query matches more than {QUERY_MATCH_LIMIT} results. Please narrow your search.'}
    return {'items': [_identifier_result(item, staff=staff) for item in items]}


def _query_identifiers(request, identifier: str, mode: IdentifierMatch):
    """
    Search identifiers using native Django/MySQL lookups. Staff can also search unsafe identifiers and receive safe.
    Queries matching over 1000 items return HTTP 400 without partial results. No server pagination.
    Case-insensitive non-regex modes use utf8mb4_0900_as_ci; accents remain significant.
    Regex uses MySQL ICU syntax, including inline flags such as (?i), and native resource limits.
    """
    if getattr(request, 'limited', False):
        raise HttpError(429, 'Identifier query rate limit exceeded. Please try again later.')
    if not 1 <= len(identifier) <= 128:
        raise HttpError(400, 'Invalid identifier length.')
    staff = request.user.is_authenticated and request.user.is_staff
    identifiers = Identifier.objects.all() if staff else Identifier.objects.filter(safe=True)
    field = 'identifier'
    if mode in {'iexact', 'icontains', 'istartswith', 'iendswith'}:
        # The stored column is case-sensitive. MySQL LIKE alone does not make these lookups case-insensitive.
        identifiers = identifiers.alias(search_text=Collate('identifier', 'utf8mb4_0900_as_ci'))
        field = 'search_text'
    identifiers = identifiers.filter(**{f'{field}__{mode}': identifier})
    try:
        return _query_results(identifiers, staff=staff)
    except DatabaseError as exc:
        # MySQL 8 ICU errors cover invalid patterns and regex resource limits. Preserve unrelated database errors.
        if mode == 'regex' and exc.args and 3684 <= exc.args[0] <= 3700:
            raise HttpError(400, 'Invalid regular expression or regular expression resource limit exceeded.') from exc
        raise


@router.get('/query/exact', response=QUERY_RESPONSES, exclude_unset=True)
@decorate_view(ratelimit(key='ip', rate='2/s', group='identifier-exact', block=False))
def query_identifier_exact(request, identifier: str):
    """
    - ratelimit(key='ip', rate='2/s', group='identifier-exact', block=False)

    exact matching. Returns all matches, up to 1000 items; more matches return HTTP 400. Rate limit: HTTP 429.
    """
    return _query_identifiers(request, identifier, 'exact')


@router.get('/query/iexact', response=QUERY_RESPONSES, exclude_unset=True)
@decorate_view(ratelimit(key='ip', rate='6/m', group='identifier-text', block=False))
def query_identifier_iexact(request, identifier: str):
    """
    - ratelimit(key='ip', rate='6/m', group='identifier-text', block=False)

    iexact matching. Returns all matches, up to 1000 items; more matches return HTTP 400. Rate limit: HTTP 429.
    """
    return _query_identifiers(request, identifier, 'iexact')


@router.get('/query/contains', response=QUERY_RESPONSES, exclude_unset=True)
@decorate_view(ratelimit(key='ip', rate='6/m', group='identifier-text', block=False))
def query_identifier_contains(request, identifier: str):
    """
    - ratelimit(key='ip', rate='6/m', group='identifier-text', block=False)

    contains matching. Returns all matches, up to 1000 items; more matches return HTTP 400. Rate limit: HTTP 429.
    """
    return _query_identifiers(request, identifier, 'contains')


@router.get('/query/icontains', response=QUERY_RESPONSES, exclude_unset=True)
@decorate_view(ratelimit(key='ip', rate='6/m', group='identifier-text', block=False))
def query_identifier_icontains(request, identifier: str):
    """
    - ratelimit(key='ip', rate='6/m', group='identifier-text', block=False)

    icontains matching. Returns all matches, up to 1000 items; more matches return HTTP 400. Rate limit: HTTP 429.
    """
    return _query_identifiers(request, identifier, 'icontains')


@router.get('/query/startswith', response=QUERY_RESPONSES, exclude_unset=True)
@decorate_view(ratelimit(key='ip', rate='10/m', group='identifier-prefix', block=False))
def query_identifier_startswith(request, identifier: str):
    """
    - ratelimit(key='ip', rate='10/m', group='identifier-prefix', block=False)

    startswith matching. Returns all matches, up to 1000 items; more matches return HTTP 400. Rate limit: HTTP 429.
    """
    return _query_identifiers(request, identifier, 'startswith')


@router.get('/query/istartswith', response=QUERY_RESPONSES, exclude_unset=True)
@decorate_view(ratelimit(key='ip', rate='6/m', group='identifier-text', block=False))
def query_identifier_istartswith(request, identifier: str):
    """
    - ratelimit(key='ip', rate='6/m', group='identifier-text', block=False)

    istartswith matching. Returns all matches, up to 1000 items; more matches return HTTP 400. Rate limit: HTTP 429.
    """
    return _query_identifiers(request, identifier, 'istartswith')


@router.get('/query/endswith', response=QUERY_RESPONSES, exclude_unset=True)
@decorate_view(ratelimit(key='ip', rate='6/m', group='identifier-text', block=False))
def query_identifier_endswith(request, identifier: str):
    """
    - ratelimit(key='ip', rate='6/m', group='identifier-text', block=False)

    endswith matching. Returns all matches, up to 1000 items; more matches return HTTP 400. Rate limit: HTTP 429.
    """
    return _query_identifiers(request, identifier, 'endswith')


@router.get('/query/iendswith', response=QUERY_RESPONSES, exclude_unset=True)
@decorate_view(ratelimit(key='ip', rate='6/m', group='identifier-text', block=False))
def query_identifier_iendswith(request, identifier: str):
    """
    - ratelimit(key='ip', rate='6/m', group='identifier-text', block=False)

    iendswith matching. Returns all matches, up to 1000 items; more matches return HTTP 400. Rate limit: HTTP 429.
    """
    return _query_identifiers(request, identifier, 'iendswith')


@router.get('/query/regex', response=QUERY_RESPONSES, exclude_unset=True)
@decorate_view(ratelimit(key='ip', rate='2/m', group='identifier-regex', block=False))
def query_identifier_regex(request, identifier: str):
    """
    - ratelimit(key='ip', rate='2/m', group='identifier-regex', block=False)

    regex matching. Returns all matches, up to 1000 items; more matches return HTTP 400. Rate limit: HTTP 429.
    """
    return _query_identifiers(request, identifier, 'regex')


@router.get('/query/user/{user_id}', response=QUERY_RESPONSES, exclude_unset=True)
@decorate_view(staff_required)
def query_user_identifiers(request, user_id: int):
    """
    - staff_required

    Return a player's identifiers with their safe values, including unsafe records.
    """
    return _query_results(Identifier.objects.filter(userms__parent__id=user_id), staff=True)


class IdentifierBindIn(Schema):
    identifier: str = Field(..., min_length=1, max_length=128)
    id: NonNegativeInt


@router.post('/bind', response=IdentifierOut)
@decorate_view(staff_required)
def staff_bind_identifier(request, data: Form[IdentifierBindIn]):
    """
    - staff_required

    Bind to a user; id=0 unbinds the current owner without deleting the identifier.
    """
    if data.id == 0:
        identifier = get_object_or_404(Identifier, identifier=data.identifier)
        changed_count = unbind_identifier(identifier) if identifier.userms_id is not None else 0
    else:
        user = get_object_or_404(UserProfile.objects.select_related('userms'), id=data.id)
        if user.userms is None:
            raise HttpError(400, 'User has no minesweeper profile.')
        identifier, _ = Identifier.objects.get_or_create(identifier=data.identifier, defaults={'safe': True})
        if not identifier.safe:
            raise HttpError(409, 'Identifier must be safe before binding.')
        if identifier.userms_id is not None and identifier.userms_id != user.userms_id:
            raise HttpError(409, 'Unbind the current owner before binding another user.')
        changed_count = bind_identifier(identifier, user.userms)
    logger.info('Staff #%s set identifier %r owner to #%s; pending videos=%s', request.user.id, data.identifier, data.id, changed_count)
    return _identifier_result(identifier, staff=True)


class IdentifierSafeIn(Schema):
    identifier: str = Field(..., min_length=1, max_length=128)
    safe: bool


@router.post('/safe', response=IdentifierOut)
@decorate_view(staff_required)
def staff_set_identifier_safe(request, data: Form[IdentifierSafeIn]):
    """
    - staff_required
    """
    identifier = get_object_or_404(Identifier.objects.select_related('userms__parent'), identifier=data.identifier)
    try:
        set_safe(identifier, data.safe)
    except ValueError as exc:
        raise HttpError(409, 'Unbind the current owner by setting id=0 before marking the identifier unsafe.') from exc
    logger.info('Staff #%s set identifier %r safe=%s', request.user.id, data.identifier, data.safe)
    return _identifier_result(identifier, staff=True)
