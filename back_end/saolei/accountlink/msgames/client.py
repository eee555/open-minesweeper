from contextlib import contextmanager

from django.conf import settings
import httpx
from msgames_api import Client, MsgamesError, ParseError, RecordMetric, RequestError

from config.global_settings import MaxSizes
from utils.exceptions import ExceptionToResponse
from .utils import normalize_profile, normalize_replays

E2E_PROFILE_IDS = (2147483000, 2147483001)


@contextmanager
def msgames_client():
    try:
        with Client(timeout=5, max_replay_bytes=MaxSizes.VIDEOFILE) as client:
            yield client
    except RequestError as exc:
        category = 'timeout' if isinstance(exc.__cause__, httpx.TimeoutException) else 'requestexception'
        raise ExceptionToResponse('import', category, status_code=503) from exc
    except (ParseError, ValueError) as exc:
        raise ExceptionToResponse('import', 'indexerror', status_code=503) from exc
    except MsgamesError as exc:
        raise ExceptionToResponse('import', 'requestexception', status_code=503) from exc


def fetch_profile(player_id: int) -> dict:
    # Reserved synthetic IDs keep browser tests independent of the external site.
    if settings.E2E_TEST and settings.DEBUG and not settings.PRODUCTION_MARK.exists() and player_id in E2E_PROFILE_IDS:
        return {'name': 'MSGames Fixture', 'local_name': '关联姓名'}
    with msgames_client() as client:
        return normalize_profile(client.get_profile(player_id), player_id)


def fetch_replays(player_id: int) -> list[dict]:
    with msgames_client() as client:
        records = [record for metric in RecordMetric for record in client.get_records(player_id, metric)]
        return normalize_replays(records, player_id)


def download_replay(url: str) -> bytes:
    with msgames_client() as client:
        return client.download_replay(url)
