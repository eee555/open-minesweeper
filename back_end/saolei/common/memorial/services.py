import logging

from django.db import transaction

from common.services import bind_import_identifier, import_video_by_file
from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from utils.ranking_lock import ranking_access

logger = logging.getLogger('userprofile')


def _lock_import_user(user):
    user = UserProfile.objects.select_for_update().select_related('userms').get(pk=user.pk)
    if user.userms_id is None:
        raise ExceptionToResponse('memorial', 'userms_missing', status_code=409)
    return user


@ranking_access(operation='memorial.bind')
def register_memorial_identifiers(user: UserProfile, identifiers):
    results = []
    for identifier in dict.fromkeys(identifiers):
        try:
            with transaction.atomic():
                user = _lock_import_user(user)
                result = bind_import_identifier(user, identifier)
        except Exception as error:
            logger.exception('Memorial identifier binding failed user=%s identifier=%r', user.pk, identifier)
            result = {'identifier': identifier, 'bound': False, 'error': str(error)}
        results.append(result)
        logger.info('Memorial identifier binding user=%s result=%s', user.pk, result)
    return results


@ranking_access(operation='memorial.upload')
@transaction.atomic
def upload_memorial_video(user: UserProfile, file, upload_time):
    user = _lock_import_user(user)
    video = import_video_by_file(user, file, upload_time)
    logger.info(
        'Memorial video upload user=%s userms=%s video=%s requested=%s final=%s',
        user.pk, user.userms_id, video.pk, upload_time, video.upload_time,
    )
    return video
