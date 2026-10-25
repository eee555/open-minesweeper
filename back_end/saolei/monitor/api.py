from django.http import FileResponse
from django_ratelimit.decorators import ratelimit
from ninja import Router
from ninja.decorators import decorate_view
from ninja.errors import HttpError

from .schema import MonitorSnapshotOut
from .utils import get_snapshot_path

router = Router()


@router.get('/summary', response=MonitorSnapshotOut)
@decorate_view(ratelimit(key='ip', rate='30/m', block=True))
def summary(request):
    """
    - ratelimit(key='ip', rate='30/m', block=True)

    Read the precomputed file for local development; production Nginx serves it directly.
    """
    try:
        file = get_snapshot_path().open('rb')
    except FileNotFoundError:
        raise HttpError(503, 'Monitor snapshot is not available yet.') from None
    response = FileResponse(file, content_type='application/json')
    response['Cache-Control'] = 'no-cache'
    return response
