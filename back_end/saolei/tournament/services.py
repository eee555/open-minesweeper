import logging

from django.db import transaction
from django.db.models import Exists, OuterRef, Q, Sum
from django.utils import timezone

from config.text_choices import MS_TextChoices, Tournament_TextChoices
from customranking.services import add_videos_to_custom_pluck_ranks
from effranking.services import add_videos_to_eff_ranks
from speedranking.services import add_videos_to_speed_ranks
from tournament.cache import TournamentCache
from tournament.weekly.utils import WEEKLY_SCORE_CATEGORIES, WEEKLY_TOTAL_FIELDS
from utils.exceptions import ExceptionToResponse
from utils.ranking_lock import ranking_access
from videomanager.cache import add_videos_to_state_queues_bulk
from videomanager.events import videos_bulk_changed
from videomanager.models import VideoModel
from .models import (
    GSCParticipant,
    Tournament,
    TournamentParticipant,
    TournamentUser,
    WeeklyEffParticipant,
    WeeklyParticipant,
    WeeklyTournament,
)

cache = TournamentCache()
logger = logging.getLogger('tournament')


def with_participant_video_status(participants):
    return participants.annotate(has_videos=Exists(VideoModel.objects.filter(tournaments__id=OuterRef('tournament_id'), player_id=OuterRef('user_id'))))


def checkin_with_arbiter(video: VideoModel, arbiter_identifier: str):
    participants = cache.checkin_arbiter(video, arbiter_identifier)
    tournament_ids = {participant.tournament for participant in participants}
    if tournament_ids:
        video.ongoing_tournament = True
    return list(Tournament.objects.filter(id__in=tournament_ids))


def checkin_with_token(video: VideoModel, tokens: list[str]):
    participants = cache.checkin_token(video, tokens)
    tournament_ids = {participant.tournament for participant in participants}
    if tournament_ids:
        video.ongoing_tournament = True
    return list(Tournament.objects.filter(id__in=tournament_ids))


def add_existing_videos_to_participant_tournament(participant: TournamentParticipant):
    if participant.tournament.subclass == Tournament_TextChoices.Subclass.GSC and participant.tournament.state == Tournament_TextChoices.State.AWARDED:
        return 0
    if participant.user_id is None or participant.start_time is None or participant.end_time is None:
        return 0

    identifier_filter = Q()
    if participant.arbiter_identifier is not None:
        identifier_filter = Q(
            software=MS_TextChoices.Software.AVF,
            video__identifier=participant.arbiter_identifier.identifier,
        )
    token_filter = (
        ~Q(software=MS_TextChoices.Software.AVF)
        & Q(video__tournament_identifier__contains=[participant.token])
    )

    video_ids = list(
        VideoModel.objects
        .filter(
            player_id=participant.user_id,
            upload_time__gte=participant.start_time,
            upload_time__lte=participant.end_time,
        )
        .filter(identifier_filter | token_filter)
        .values_list('id', flat=True),
    )
    if not video_ids:
        return 0

    participant.tournament.videos.add(*video_ids)
    return len(video_ids)


def ensure_tournament_users(tournament: Tournament):
    logger.info(f'比赛#{tournament.id} 检查 TournamentUser 开始')
    user_ids = tournament.participants.filter(user_id__isnull=False).values_list('user_id', flat=True).distinct()
    created_count = 0
    for user_id in user_ids:
        _, created = TournamentUser.objects.get_or_create(user_id=user_id)
        created_count += created
    logger.info(f'比赛#{tournament.id} 检查 TournamentUser 完成，补建 {created_count} 个')
    return created_count


def delete_participants_without_videos(tournament: Tournament):
    video_player_ids = tournament.videos.values('player_id')
    participants = (
        TournamentParticipant.objects
        .filter(tournament=tournament, user_id__isnull=False)
        .exclude(user_id__in=video_player_ids)
    )
    if tournament.subclass == Tournament_TextChoices.Subclass.GSC:
        participants = participants.exclude(pk__in=GSCParticipant.objects.filter(tournament=tournament, manual_scores=True).values('pk'))
    deleted_count = participants.count()
    participants.delete()
    return deleted_count


def _get_score_total_by_user(queryset):
    return {
        item['user_id']: item['score_total'] or 0
        for item in (
            queryset
            .filter(user_id__isnull=False, rank_score__gt=0)
            .values('user_id')
            .annotate(score_total=Sum('rank_score'))
        )
    }


def refresh_tournament_user_total_fields(*, batch_size=1000):
    score_total_by_user = _get_score_total_by_user(TournamentParticipant.objects)
    gsc_total_by_user = _get_score_total_by_user(GSCParticipant.objects)
    weekly_totals_by_format = {
        tournament_format: _get_score_total_by_user(WeeklyParticipant.objects.filter(tournament__weeklytournament__tournament_format=tournament_format))
        for tournament_format in WEEKLY_SCORE_CATEGORIES
    }
    weekly_eff_total_by_user = _get_score_total_by_user(WeeklyEffParticipant.objects)

    user_ids = (
        set(TournamentUser.objects.values_list('user_id', flat=True))
        | set(score_total_by_user)
    )
    existing_user_ids = set(TournamentUser.objects.filter(user_id__in=user_ids).values_list('user_id', flat=True))
    missing_user_ids = user_ids - existing_user_ids
    if missing_user_ids:
        TournamentUser.objects.bulk_create(
            [TournamentUser(user_id=user_id) for user_id in missing_user_ids],
            batch_size=batch_size,
        )

    tournament_users = list(TournamentUser.objects.filter(user_id__in=user_ids))
    for tournament_user in tournament_users:
        user_id = tournament_user.user_id
        tournament_user.score_total = score_total_by_user.get(user_id, 0)
        tournament_user.gsc_total = gsc_total_by_user.get(user_id, 0)
        for tournament_format, category in WEEKLY_SCORE_CATEGORIES.items():
            setattr(tournament_user, f'{category}_total', weekly_totals_by_format[tournament_format].get(user_id, 0))
        tournament_user.weekly_total = sum(getattr(tournament_user, field) for field in WEEKLY_TOTAL_FIELDS)
        tournament_user.weekly_eff_total = weekly_eff_total_by_user.get(user_id, 0)

    if tournament_users:
        TournamentUser.objects.bulk_update(
            tournament_users,
            ['score_total', 'gsc_total', 'weekly_total', *WEEKLY_TOTAL_FIELDS, 'weekly_eff_total'],
            batch_size=batch_size,
        )
        cache.update_tournament_users(
            tournament_users,
            fields=['score_total', 'gsc_total', 'weekly_total', *WEEKLY_TOTAL_FIELDS, 'weekly_eff_total'],
        )

    return len(tournament_users)


def get_participants_for_rank(tournament: Tournament):
    if tournament.subclass == Tournament_TextChoices.Subclass.GSC:
        return GSCParticipant.objects.filter(tournament=tournament)
    if tournament.subclass == Tournament_TextChoices.Subclass.WEEKLY_EFF:
        return WeeklyEffParticipant.objects.filter(tournament=tournament)
    return WeeklyParticipant.objects.filter(tournament=tournament)


def refresh_tournament_ranks(tournament: Tournament, *, batch_size=1000):
    order_by = tournament.order_by
    logger.info(f'比赛#{tournament.id} 排名刷新开始，类型 {tournament.subclass}，排序 {order_by}')

    participants = list(get_participants_for_rank(tournament).order_by(order_by))
    for rank, participant in enumerate(participants, start=1):
        participant.rank = rank

    TournamentParticipant.objects.bulk_update(participants, ['rank'], batch_size=batch_size)

    logger.info(f'比赛#{tournament.id} 排名刷新完成，更新参赛者 {len(participants)} 个')
    return len(participants)


def award_tournament_rank_scores(tournament: Tournament, *, batch_size=1000):
    # 以比赛结束时间计分，避免后台任务延迟执行影响积分衰减。
    award_time = tournament.end_time or timezone.now()
    logger.info(f'比赛#{tournament.id} 排名积分发放 开始 类型{tournament.subclass} 结算时间 {award_time}')

    logger.info(f'比赛#{tournament.id} 排名积分发放 获取选手列表')
    participants = list(get_participants_for_rank(tournament).filter(user_id__isnull=False, rank__isnull=False).select_related('user__tournamentuser'))
    logger.info(f'比赛#{tournament.id} 排名积分发放 人数 {len(participants)}')
    if not participants:
        logger.info(f'比赛#{tournament.id} 排名积分发放 结束')
        return 0

    logger.info(f'比赛#{tournament.id} 排名积分发放 数据整理 开始')

    tournament_users = []
    changed_tournament_user_fields = ['score_current', 'last_updated', 'score_total']
    if tournament.subclass == Tournament_TextChoices.Subclass.GSC:
        add_score_category = 'gsc'
        changed_tournament_user_fields.append('gsc_total')
    elif tournament.subclass == Tournament_TextChoices.Subclass.WEEKLY_EFF:
        add_score_category = 'weekly_eff'
        changed_tournament_user_fields.append('weekly_eff_total')
    elif tournament.subclass == Tournament_TextChoices.Subclass.WEEKLY:
        tournament: WeeklyTournament = tournament.select_subclass()
        add_score_category = WEEKLY_SCORE_CATEGORIES[tournament.tournament_format]
        changed_tournament_user_fields.extend(['weekly_total', f'{add_score_category}_total'])

    for participant in participants:
        target_rank_score = round(tournament.weight / participant.rank)
        # 只发放新旧排名积分的差额，重复结算不会再次累计整场积分。
        score_delta = target_rank_score - participant.rank_score

        tournament_user = participant.user.tournamentuser
        tournament_user.add_score(score_delta, award_time, category=add_score_category)
        tournament_users.append(tournament_user)

        participant.rank_score = target_rank_score

    logger.info(f'比赛#{tournament.id} 排名积分发放 更新选手分数 {len(participants)}')
    TournamentParticipant.objects.bulk_update(participants, ['rank_score'], batch_size=batch_size)

    logger.info(f'比赛#{tournament.id} 排名积分发放 更新用户总分 {len(tournament_users)}')
    TournamentUser.objects.bulk_update(tournament_users, changed_tournament_user_fields, batch_size=batch_size)
    # 写库后批量刷新排行；当前积分由缓存层统一换算时间基准，其他累计字段直接写入。
    transaction.on_commit(lambda: cache.update_tournament_users(tournament_users, fields=changed_tournament_user_fields))

    logger.info(f'比赛#{tournament.id} 排名积分发放 完成')
    return len(participants)


@transaction.atomic
def reset_participant_registration(participant: TournamentParticipant):
    if not participant.tournament.is_ongoing() or participant.end_time is None or timezone.now() <= participant.end_time:
        raise ExceptionToResponse('participant', 'reset_not_available', status_code=403)
    if participant.videos.exists():
        raise ExceptionToResponse('participant', 'has_videos', status_code=403)
    participant.delete()


@transaction.atomic
def disqualify_participant(participant_id: int, *, tournament_id: int):
    participant = TournamentParticipant.objects.select_related('tournament').filter(id=participant_id, tournament_id=tournament_id).first()
    if participant is None:
        return False
    if participant.tournament.state != Tournament_TextChoices.State.AWARDED:
        raise ValueError('Only awarded tournament participants can be disqualified.')
    if participant.user_id is not None:
        TournamentUser.objects.get_or_create(user_id=participant.user_id)
    logger.info(f'比赛#{participant.tournament_id} 取消参赛资格 participant#{participant.id}，撤销积分 {participant.rank_score}')
    participant.delete()
    return True


@ranking_access(operation='tournament.reveal_videos')
@transaction.atomic
def reveal_videos_for_tournament(tournament: Tournament):
    """批量恢复已颁奖比赛中不再属于其他未颁奖且未取消比赛的录像。"""
    logger.info(f'比赛#{tournament.id} 录像公开开始，状态 {tournament.state}')
    if tournament.state != Tournament_TextChoices.State.AWARDED:
        logger.info(f'比赛#{tournament.id} 录像公开跳过，状态不是 AWARDED')
        return 0

    current_video_ids = set(
        tournament.videos
        .filter(ongoing_tournament=True)
        .values_list('id', flat=True),
    )
    unrevealed_video_ids = set(
        Tournament.objects
        .exclude(state__in=[Tournament_TextChoices.State.AWARDED, Tournament_TextChoices.State.CANCELLED])
        .filter(videos__ongoing_tournament=True)
        .values_list('videos__id', flat=True)
        .distinct(),
    )
    video_ids = list(current_video_ids - unrevealed_video_ids)
    logger.info(
        f'比赛#{tournament.id} 录像公开候选计算完成，当前隐藏 {len(current_video_ids)}，'
        f'仍属于未公开比赛 {len(unrevealed_video_ids)}，待公开 {len(video_ids)}',
    )

    if not video_ids:
        logger.info(f'比赛#{tournament.id} 录像公开完成，没有需要公开的录像')
        return 0

    VideoModel.objects.filter(id__in=video_ids).update(ongoing_tournament=False)

    videos = (
        VideoModel.objects
        .filter(id__in=video_ids)
        .select_related('player', 'player__userms', 'video')
    )
    player_ids = list(videos.order_by().values_list('player_id', flat=True).distinct())
    videos_bulk_changed.send(sender=VideoModel, player_ids=player_ids)
    # Redis and custom-ranking save signals must only see committed reveals.
    # Keep each refresh independent so a failed cache cannot skip the others.
    transaction.on_commit(lambda: add_videos_to_state_queues_bulk(videos), robust=True)
    transaction.on_commit(lambda: add_videos_to_speed_ranks(videos), robust=True)
    transaction.on_commit(lambda: add_videos_to_custom_pluck_ranks(videos), robust=True)
    transaction.on_commit(lambda: add_videos_to_eff_ranks(videos), robust=True)

    logger.info(f'比赛#{tournament.id} 录像公开完成，公开录像 {len(video_ids)} 个')
    return len(video_ids)
