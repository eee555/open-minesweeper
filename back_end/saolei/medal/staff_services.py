from userprofile.models import UserProfile
from .definitions import all_definitions
from .models import MedalGrant, MedalOverride, MedalOverrideLog
from .services import MedalError


def staff_catalog():
    """管理员可看到停用和隐藏定义；不复用公开图鉴的可见性过滤。"""
    return all_definitions()


def staff_player_state(user_id):
    user = UserProfile.objects.filter(pk=user_id).only('id', 'username').first()
    if user is None:
        raise MedalError('user')
    return {
        'user_id': user.id,
        'username': user.username,
        'grants': list(MedalGrant.objects.filter(user=user).order_by('definition_code', 'scope_key')),
        'overrides': list(MedalOverride.objects.filter(user=user).order_by('definition_code', 'scope_key')),
        'history': list(MedalOverrideLog.objects.filter(user=user).order_by('-created_at', '-id')[:50]),
    }
