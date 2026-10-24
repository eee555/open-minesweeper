from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from accountlink.models import AccountLinkQueue, Platform
from config.text_choices import MS_TextChoices
from tournament.models import TournamentParticipant
from userprofile.models import UserProfile
from videomanager.events import videos_bulk_changed
from videomanager.models import VideoModel
from .cache import delete_player_states, invalidate_catalog
from .models import MedalDefinition, MedalGrant, PlayerMedalSummary
from .tasks import enqueue_player_refresh


@receiver(post_save, sender=MedalDefinition)
@receiver(post_delete, sender=MedalDefinition)
def invalidate_medal_catalog(sender, **kwargs):
    invalidate_catalog()


@receiver(pre_delete, sender=VideoModel, dispatch_uid='medal.invalidate_summary_on_video_delete')
@receiver(pre_delete, sender=TournamentParticipant, dispatch_uid='medal.invalidate_summary_on_participant_delete')
@transaction.atomic
def invalidate_summary_on_evidence_delete(sender, instance, **kwargs):
    # SET_NULL 不触发授予的 save；删除前仍能按外键找到受影响的摘要。
    field = 'video' if sender is VideoModel else 'participant'
    player_ids = MedalGrant.objects.filter(**{field: instance}).values_list('user_id', flat=True)
    locked_ids = list(UserProfile.objects.select_for_update().filter(pk__in=player_ids).order_by('pk').values_list('pk', flat=True))
    PlayerMedalSummary.objects.filter(user_id__in=locked_ids).delete()
    if locked_ids:
        pending = tuple(locked_ids)
        transaction.on_commit(lambda pending=pending: delete_player_states(pending))


def _lost_qualification(old, instance):
    if old.get('state') == MS_TextChoices.State.OFFICIAL and instance.state != MS_TextChoices.State.OFFICIAL:
        return True
    if instance.ongoing_tournament and not old.get('ongoing_tournament'):
        return True
    if old.get('mode') == MS_TextChoices.Mode.STD and instance.mode != MS_TextChoices.Mode.STD:
        return True
    if old.get('level') and instance.level and old.get('level') != instance.level:
        return True
    if 'right_ce' in old and old.get('right_ce') != instance.right_ce:
        return True
    return False


def _score_worse(old, instance):
    old_time = old.get('timems')
    if old_time is not None and instance.timems is not None and instance.timems > old_time:
        return True
    old_bv = old.get('bv')
    if old_bv is not None and instance.bv is not None and instance.bv < old_bv:
        return True
    return False


def _video_task_kwargs(instance, player_id, old, *, deleted, created):
    video_id = instance.pk
    level = getattr(instance, 'level', None)
    old_level = old.get('level') or level
    previous = old.get('player_id')
    if previous and previous != getattr(instance, 'player_id', None) and player_id == previous:
        levels = [item for item in {old_level, level} if item]
        return {'video_ids': [video_id], 'degrade_levels': levels, 'invalidate_once': True}
    degrade = set()
    invalidate = False
    if deleted:
        degrade.add(level)
        invalidate = True
    elif not created and old:
        lost = _lost_qualification(old, instance)
        if lost or _score_worse(old, instance):
            degrade.add(old_level)
            if level and level != old_level:
                degrade.add(level)
            # 退审、进赛、改 mode/level/NF 会让新手集合过期；仅成绩变差不需要。
            if lost:
                invalidate = True
    kwargs = {'video_ids': [video_id]}
    levels = [item for item in degrade if item]
    if levels:
        kwargs['degrade_levels'] = levels
    if invalidate:
        kwargs['invalidate_once'] = True
    return kwargs


def _enqueue_video_players(instance, *, deleted=False, created=False):
    old = getattr(instance, '_old_values', None) or {}
    player_ids = []
    current = getattr(instance, 'player_id', None)
    if current:
        player_ids.append(current)
    previous = old.get('player_id')
    if previous and previous not in player_ids:
        player_ids.append(previous)
    for player_id in player_ids:
        if not getattr(instance, 'pk', None):
            transaction.on_commit(lambda player_id=player_id: enqueue_player_refresh(player_id))
            continue
        kwargs = _video_task_kwargs(instance, player_id, old, deleted=deleted, created=created)
        transaction.on_commit(lambda player_id=player_id, kwargs=kwargs: enqueue_player_refresh(player_id, **kwargs))


@receiver(post_save, sender=VideoModel, dispatch_uid='medal.refresh_on_video_save')
@receiver(post_delete, sender=VideoModel, dispatch_uid='medal.refresh_on_video_delete')
def enqueue_medal_refresh_on_video(sender, instance, created=False, **kwargs):
    _enqueue_video_players(instance, deleted=kwargs.get('signal') is post_delete, created=created)


@receiver(videos_bulk_changed, dispatch_uid='medal.refresh_on_videos_bulk_changed')
def enqueue_medal_refresh_on_bulk_videos(sender, player_ids, **kwargs):
    for player_id in sorted(set(player_ids) - {None}):
        transaction.on_commit(lambda player_id=player_id: enqueue_player_refresh(player_id), robust=True)


@receiver(post_save, sender=UserProfile, dispatch_uid='medal.refresh_on_profile_save')
def enqueue_medal_refresh_on_profile(sender, instance, created=False, update_fields=None, **kwargs):
    if update_fields is not None and '_realname' not in update_fields:
        return
    if created and instance.realname == '匿名':
        return
    user_id = instance.pk
    if not user_id:
        return
    transaction.on_commit(lambda user_id=user_id: enqueue_player_refresh(user_id))


@receiver(post_save, sender=AccountLinkQueue, dispatch_uid='medal.refresh_on_saolei_link_save')
@receiver(post_delete, sender=AccountLinkQueue, dispatch_uid='medal.refresh_on_saolei_link_delete')
def enqueue_medal_refresh_on_saolei_link(sender, instance, **kwargs):
    if instance.platform != Platform.SAOLEI:
        return
    user_id = instance.userprofile_id
    if not user_id:
        return
    transaction.on_commit(lambda user_id=user_id: enqueue_player_refresh(user_id))
