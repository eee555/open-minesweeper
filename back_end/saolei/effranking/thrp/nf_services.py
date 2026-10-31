from math import isfinite

from django.db.models import F, Q, Window
from django.db.models.functions import RowNumber

from config.text_choices import MS_TextChoices
from videomanager.models import VideoModel
from .utils import NF_STAT


def refresh_expert_nf_records(records: dict, player_ids):
    """一次查询取全部满分录像或最佳一局，局数由 id 列表长度得出。"""
    player_ids = set(player_ids)
    if not player_ids:
        return
    for player_id in player_ids:
        records[player_id][NF_STAT] = None
    videos = VideoModel.objects.filter(
        player_id__in=player_ids, level=MS_TextChoices.Level.EXPERT, right_ce=0,
        mode=MS_TextChoices.Mode.STD, state=MS_TextChoices.State.OFFICIAL,
        ongoing_tournament=False, thrp__isnull=False,
    ).annotate(
        rn=Window(RowNumber(), partition_by=[F('player_id')], order_by=[F('thrp').desc(), F('id').asc()]),
    ).filter(Q(rn=1) | Q(thrp=1)).order_by('player_id', '-thrp', 'id').values('id', 'player_id', 'thrp')
    for video in videos.iterator(chunk_size=1000):
        if not isfinite(video['thrp']):
            continue
        part = records[video['player_id']][NF_STAT]
        if part is None:
            part = {'value': video['thrp'], 'video_ids': []}
            records[video['player_id']][NF_STAT] = part
        part['video_ids'].append(video['id'])
