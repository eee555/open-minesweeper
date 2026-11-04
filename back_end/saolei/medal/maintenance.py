from django.db import transaction

from userprofile.models import UserProfile
from .cache import delete_player_states
from .models import MedalDefinition, MedalScan, PlayerMedalSummary, PlayerProgress
from .utils import NOVICE_MODES, open_modes


@transaction.atomic
def correct_modes():
    definition = MedalDefinition.objects.select_for_update().filter(code=NOVICE_MODES).first()
    if definition is None:
        return
    scope = definition.scope
    old_modes = ['00', '01', '04', '05', '06', '07', '08', '09', '10', '11']
    if not isinstance(scope, dict) or scope.get('modes') != old_modes:
        return  # 保留运营自定义的要求。
    definition.scope = {**scope, 'modes': open_modes()}
    definition.save(update_fields=['scope'])
    # 让已有进度的玩家在下一次访问时走现有异步历史补发流程。
    progress_users = PlayerProgress.objects.filter(code=NOVICE_MODES).values_list('user_id', flat=True)
    users = tuple(UserProfile.objects.select_for_update().filter(pk__in=progress_users).order_by('pk').values_list('pk', flat=True))
    MedalScan.objects.filter(user_id__in=users).delete()
    PlayerMedalSummary.objects.filter(user_id__in=users).delete()
    transaction.on_commit(lambda: delete_player_states(users))
