import logging

from django.db import transaction

from accountlink.models import AccountLinkQueue, Platform, PLATFORM_CONFIG
from accountlink.utils import delete_account
from common.services import bind_import_identifier, import_video_by_file
from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from utils.ranking_lock import ranking_access

logger = logging.getLogger('userprofile')

# 只有这些平台的账号可以由站长直接指定；其余平台依赖本人身份验证流程，纪念账号无法自行完成。
ASSIGNABLE_MEMORIAL_PLATFORMS = frozenset({Platform.SAOLEI, Platform.MSGAMES, Platform.WOM})


def _lock_import_user(user):
    user = UserProfile.objects.select_for_update().select_related('userms').get(pk=user.pk)
    if user.userms_id is None:
        raise ExceptionToResponse('memorial', 'userms_missing', status_code=409)
    return user


def _lock_memorial_target(user_id: int) -> UserProfile:
    user = UserProfile.objects.select_for_update().filter(pk=user_id).first()
    if user is None:
        raise ExceptionToResponse('memorial', 'not_found', status_code=404)
    if not user.is_memorial:
        raise ExceptionToResponse('memorial', 'not_memorial', status_code=409)
    return user


def _checked_platform(platform) -> Platform:
    value = Platform(platform) if platform in Platform.values else None
    if value not in ASSIGNABLE_MEMORIAL_PLATFORMS:
        raise ExceptionToResponse('memorial', 'platform_not_assignable', status_code=400)
    return value


@ranking_access(operation='memorial.account_link')
@transaction.atomic
def assign_memorial_account_link(user_id: int, platform, identifier: str) -> dict:
    """站长直接为纪念账号指定一个已核实的外部平台账号，覆盖本人申请与管理员核实的流程。"""
    user = _lock_memorial_target(user_id)
    platform = _checked_platform(platform)
    identifier = (identifier or '').strip()
    if not identifier:
        raise ExceptionToResponse('memorial', 'identifier_required', status_code=400)

    model = PLATFORM_CONFIG[platform]['model']
    try:
        linkid = model._meta.pk.to_python(identifier)
    except (TypeError, ValueError):
        raise ExceptionToResponse('memorial', 'identifier_invalid', status_code=400) from None
    if linkid is None or str(linkid) != identifier:
        raise ExceptionToResponse('memorial', 'identifier_invalid', status_code=400)

    owner = model.objects.select_for_update().filter(pk=linkid).first()
    if owner is not None and owner.parent_id != user.pk:
        raise ExceptionToResponse('accountlink', 'collision', status_code=409)

    taken = AccountLinkQueue.objects.select_for_update().filter(platform=platform, identifier=identifier).exclude(userprofile=user)
    if taken.filter(verified=True).exists():
        raise ExceptionToResponse('accountlink', 'collision', status_code=409)
    taken.delete()

    # 每个平台在一个用户下只能有一条账号记录（OneToOne），换绑时先移除旧的。
    model.objects.filter(parent=user).exclude(pk=linkid).delete()
    account = owner or model.objects.create(id=linkid, parent=user)
    if owner is not None:
        account.parent = user
        account.save(update_fields=['parent'])
    AccountLinkQueue.objects.update_or_create(
        platform=platform, userprofile=user,
        defaults={'identifier': identifier, 'verified': True},
    )
    logger.warning('Superuser assigned account link platform=%s identifier=%s to memorial user=%s', platform, identifier, user.pk)
    return {'platform': platform.value, 'identifier': identifier, 'verified': True}


@ranking_access(operation='memorial.account_unlink')
@transaction.atomic
def remove_memorial_account_link(user_id: int, platform) -> dict:
    """解除站长指定的平台关联，同时删除平台账号记录，保留其他平台的关联。"""
    user = _lock_memorial_target(user_id)
    platform = _checked_platform(platform)
    link = AccountLinkQueue.objects.select_for_update().filter(userprofile=user, platform=platform).first()
    if link is None:
        raise ExceptionToResponse('accountlink', 'not_found', status_code=404)
    delete_account(user, platform)
    link.delete()
    logger.warning('Superuser removed account link platform=%s from memorial user=%s', platform, user.pk)
    return {'platform': platform.value, 'removed': True}


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
