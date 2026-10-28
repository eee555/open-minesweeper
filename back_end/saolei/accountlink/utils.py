from bilibili_api import sync
from bilibili_api.user import User

from userprofile.models import UserProfile
from utils.exceptions import ExceptionToResponse
from .models import AccountBilibili, Platform, PLATFORM_CONFIG

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0',
}
private_platforms = [Platform.QQ]


def isPrivate(platform) -> bool:
    return platform in private_platforms


def link_account(platform: Platform, linkid, user: UserProfile):
    model = PLATFORM_CONFIG[platform]['model']
    linkid = model._meta.pk.to_python(linkid)
    account = model.objects.select_for_update().filter(id=linkid).first()
    if not account:
        account = model.objects.create(id=linkid, parent=user)
    else:
        if account.parent_id != user.pk:
            raise ExceptionToResponse('accountlink', 'collision', status_code=409)
        account.parent = user
        account.save(update_fields=['parent'])
    return account


def delete_account(user: UserProfile, platform: Platform):
    if platform == Platform.MINERACER:
        raise ExceptionToResponse('mineracer', 'unlink_not_supported', status_code=409)
    if platform in PLATFORM_CONFIG:
        PLATFORM_CONFIG[platform]['model'].objects.filter(parent=user).delete()


def update_bilibili_account(account: AccountBilibili):
    bili_user = User(uid=account.id)
    try:
        info = sync(bili_user.get_user_info())
        relation = sync(bili_user.get_relation_info())
        overview = sync(bili_user.get_overview_stat())
    except TimeoutError:
        raise ExceptionToResponse(obj='import', category='timeout')
    except Exception:
        raise ExceptionToResponse(obj='import', category='requestexception')

    official = info.get('official', {})
    account.name = info.get('name', '') or ''
    account.face = info.get('face', '') or ''
    account.sign = info.get('sign', '') or ''
    account.level = info.get('level', 0) or 0
    account.following = relation.get('following', 0) or 0
    account.follower = relation.get('follower', 0) or 0
    account.video_count = overview.get('video', 0) or 0
    account.article_count = overview.get('article', 0) or 0
    account.opus_count = overview.get('opus', 0) or 0
    account.official_title = official.get('title', '') or ''
    account.save(update_fields=[
        'name', 'face', 'sign', 'level',
        'following', 'follower',
        'video_count', 'article_count', 'opus_count',
        'official_title',
    ])
