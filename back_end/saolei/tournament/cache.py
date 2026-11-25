from dataclasses import dataclass
from datetime import datetime
import json
from typing import Iterable, Literal

from dataclasses_json import dataclass_json
from django_redis import get_redis_connection

from config.text_choices import Tournament_TextChoices
from utils.cache import maybe_bytes_to_str
from videomanager.models import VideoModel
from .models import GSCTournament, Tournament, TournamentParticipant, TournamentUser, WeeklyEffTournament
from .utils import MAX_TOURNAMENT_BEST, tournament_score_decay_factor, tournament_score_reference_time
from .weekly.utils import WEEKLY_BEST_FIELDS, WEEKLY_TOTAL_FIELDS

cache = get_redis_connection('saolei_website')

NORMAL_TOURNAMENT_CACHE_KEY = 'tournament:normal'
NORMAL_PARTICIPANT_CACHE_KEY = 'tournament:normal:participants'
TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY = 'tournament:user:score_current:last_updated'

TOURNAMENT_USER_CACHE_KEYS = {
    'score_current': 'tournament:user:score_current',
    'score_total': 'tournament:user:score_total',
    'gsc_total': 'tournament:user:gsc_total',
    'gsc_best': 'tournament:user:gsc_best',
    'weekly_total': 'tournament:user:weekly_total',
    'weekly_classic_total': 'tournament:user:weekly_classic_total',
    'weekly_classic_best': 'tournament:user:weekly_classic_best',
    'weekly_nf_total': 'tournament:user:weekly_nf_total',
    'weekly_nf_best': 'tournament:user:weekly_nf_best',
    'weekly_qwc_total': 'tournament:user:weekly_qwc_total',
    'weekly_qwc_best': 'tournament:user:weekly_qwc_best',
    'weekly_qwc_nf_total': 'tournament:user:weekly_qwc_nf_total',
    'weekly_qwc_nf_best': 'tournament:user:weekly_qwc_nf_best',
    'weekly_eff_total': 'tournament:user:weekly_eff_total',
    'weekly_eff_best': 'tournament:user:weekly_eff_best',
}
TOURNAMENT_USER_RANK_FIELDS = (
    'score_current', 'score_total',
    'gsc_total', 'gsc_best',
    'weekly_total', *WEEKLY_TOTAL_FIELDS, *WEEKLY_BEST_FIELDS,
    'weekly_eff_total', 'weekly_eff_best',
)
TOURNAMENT_USER_ASC_FIELDS = ('gsc_best', *WEEKLY_BEST_FIELDS, 'weekly_eff_best')
TOURNAMENT_USER_DEFAULT_VALUES = {
    'score_current': 0,
    'score_total': 0,
    'gsc_total': 0,
    'gsc_best': MAX_TOURNAMENT_BEST,
    'weekly_total': 0,
    **dict.fromkeys(WEEKLY_TOTAL_FIELDS, 0),
    **dict.fromkeys(WEEKLY_BEST_FIELDS, MAX_TOURNAMENT_BEST),
    'weekly_eff_total': 0,
    'weekly_eff_best': None,
}


@dataclass_json
@dataclass
class CachedTournament:
    id: int
    state: Tournament_TextChoices.State
    subclass: Tournament_TextChoices.Subclass
    host_id: int | None
    start_time: datetime
    end_time: datetime


@dataclass_json
@dataclass
class CachedGSCTournamentData:
    order: int
    token: str


@dataclass_json
@dataclass
class CachedWeeklyTournamentData:
    year: int
    week: int
    tournament_format: str


@dataclass_json
@dataclass
class CachedWeeklyEffTournamentData:
    year: int
    week: int


@dataclass_json
@dataclass
class CachedGSCTournament(CachedTournament):
    subclass: Literal[Tournament_TextChoices.Subclass.GSC]
    data: CachedGSCTournamentData


@dataclass_json
@dataclass
class CachedWeeklyTournament(CachedTournament):
    subclass: Literal[Tournament_TextChoices.Subclass.WEEKLY]
    data: CachedWeeklyTournamentData


@dataclass_json
@dataclass
class CachedWeeklyEffTournament(CachedTournament):
    subclass: Literal[Tournament_TextChoices.Subclass.WEEKLY_EFF]
    data: CachedWeeklyEffTournamentData


@dataclass_json
@dataclass
class CachedNormalParticipant:
    id: int
    token: str
    arbiter_identifier: str | None
    tournament: int
    start_time: datetime
    end_time: datetime


class TournamentCache:
    def update_tournament(self, tournament: Tournament):
        tournament = tournament.select_subclass()
        if tournament.state == Tournament_TextChoices.State.NORMAL:
            cache.hset(
                NORMAL_TOURNAMENT_CACHE_KEY,
                tournament.id,
                serialize_normal_tournament(tournament).to_json(),
            )
        else:
            self.remove_tournament(tournament.id)

    def remove_tournament(self, tournament_id: int):
        cache.hdel(NORMAL_TOURNAMENT_CACHE_KEY, tournament_id)
        self.remove_tournament_participants(tournament_id)

    def remove_tournament_participants(self, tournament_id: int):
        for user_id, _ in cache.hscan_iter(NORMAL_PARTICIPANT_CACHE_KEY):
            self.remove_participant(user_id, tournament_id)

    def get_tournament(self, tournament_id: int):
        data = cache.hget(NORMAL_TOURNAMENT_CACHE_KEY, tournament_id)
        if data is None:
            return None
        return deserialize_cached_tournament(data)

    def get_tournament_all(self):
        data = cache.hgetall(NORMAL_TOURNAMENT_CACHE_KEY)
        return [
            deserialize_cached_tournament(value)
            for value in data.values()
        ]

    def get_gsc(self):
        data = self.get_tournament_all()
        for tournament in data:
            if tournament.subclass == Tournament_TextChoices.Subclass.GSC:
                return tournament
        return None

    def get_participant_list(self, user_id: int) -> list[CachedNormalParticipant]:
        data = cache.hget(NORMAL_PARTICIPANT_CACHE_KEY, user_id)
        if data is None:
            return []
        return CachedNormalParticipant.schema().loads(data, many=True)

    def set_participant_list(self, user_id: int, participants: list[CachedNormalParticipant]):
        if participants:
            cache.hset(NORMAL_PARTICIPANT_CACHE_KEY, user_id, CachedNormalParticipant.schema().dumps(participants, many=True))
        else:
            cache.hdel(NORMAL_PARTICIPANT_CACHE_KEY, user_id)

    def _modify_participant_list(self, user_id, modify):
        def update(pipe):
            value = pipe.hget(NORMAL_PARTICIPANT_CACHE_KEY, user_id)
            participants = CachedNormalParticipant.schema().loads(value, many=True) if value else []
            participants = modify(participants, pipe)
            pipe.multi()
            if participants:
                pipe.hset(NORMAL_PARTICIPANT_CACHE_KEY, user_id, CachedNormalParticipant.schema().dumps(participants, many=True))
            else:
                pipe.hdel(NORMAL_PARTICIPANT_CACHE_KEY, user_id)

        # 必须监视读改写全过程；普通 pipeline 无法防止另一场报名被旧列表覆盖。
        cache.transaction(update, NORMAL_PARTICIPANT_CACHE_KEY, NORMAL_TOURNAMENT_CACHE_KEY)

    def remove_participant(self, user_id: int, tournament_id: int, participant_id=None):
        self._modify_participant_list(user_id, lambda participants, pipe: [
            participant for participant in participants
            if participant.tournament != tournament_id or (participant_id is not None and participant.id != participant_id)
        ])

    def update_participant(self, participant: TournamentParticipant):
        cached = serialize_normal_participant(participant)

        def modify(participants, pipe):
            participants = [item for item in participants if item.tournament != participant.tournament_id]
            if participant.tournament.state == Tournament_TextChoices.State.NORMAL and pipe.hexists(NORMAL_TOURNAMENT_CACHE_KEY, participant.tournament_id):
                participants.append(cached)
            return participants

        self._modify_participant_list(participant.user_id, modify)

    def checkin_arbiter(self, video: VideoModel, arbiter_identifier: str) -> list[CachedNormalParticipant]:
        return [
            participant
            for participant in self.get_participant_list(video.player_id)
            if (
                participant.arbiter_identifier == arbiter_identifier
                and participant.start_time <= video.upload_time <= participant.end_time
            )
        ]

    def checkin_token(self, video: VideoModel, tokens: list[str]) -> list[CachedNormalParticipant]:
        return [
            participant
            for participant in self.get_participant_list(video.player_id)
            if (
                participant.token in tokens
                and participant.start_time <= video.upload_time <= participant.end_time
            )
        ]

    def clear_tournament_user_cache(self):
        cache.delete(*TOURNAMENT_USER_CACHE_KEYS.values(), TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY)

    def update_tournament_user(self, tournament_user: TournamentUser, fields=None):
        self.update_tournament_users([tournament_user], fields=fields)

    def update_tournament_users(self, tournament_users: Iterable[TournamentUser], fields=None):
        fields = self._normalize_tournament_user_fields(fields)
        if not fields:
            return
        # 年度锚点更新可能导致事务重试，先展开迭代器，保留同一批用户。
        tournament_users = list(tournament_users)
        if not tournament_users:
            return

        if 'score_current' in fields:
            # 只监视锚点；普通结算不推进锚点，也不整体衰减已有成员。
            cache.transaction(
                lambda pipe: self._update_tournament_users_with_score_current(pipe, tournament_users, fields),
                TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY,
            )
            return

        pipe = cache.pipeline()
        self._update_tournament_users_in_pipeline(pipe, tournament_users, fields)
        pipe.execute()

    def rebuild_tournament_user_cache(self, *, batch_size=1000):
        self.clear_tournament_user_cache()
        self.refresh_tournament_score_reference()
        batch = []
        count = 0
        for tournament_user in TournamentUser.objects.iterator(chunk_size=batch_size):
            batch.append(tournament_user)
            count += 1
            if count % batch_size == 0:
                self.update_tournament_users(batch)
                batch = []
        self.update_tournament_users(batch)
        return count

    def _get_tournament_score_reference(self, pipe):
        value = pipe.get(TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY)
        if value is not None:
            return datetime.fromisoformat(maybe_bytes_to_str(value))
        if pipe.exists(TOURNAMENT_USER_CACHE_KEYS['score_current']):
            raise RuntimeError('Current score cache has no time reference; run rebuild_tournament_current_score_cache.')
        return None

    def _update_tournament_users_with_score_current(self, pipe, tournament_users, fields):
        previous_time = self._get_tournament_score_reference(pipe)
        score_time = previous_time or tournament_score_reference_time()
        pipe.multi()
        if previous_time is None:
            pipe.set(TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY, score_time.isoformat())
        self._update_tournament_users_in_pipeline(pipe, tournament_users, fields, score_time=score_time)

    def refresh_tournament_score_reference(self):
        """年度切换统一锚点，不修改数据库；同一年重复执行不衰减第二次。"""
        score_time = tournament_score_reference_time()

        def refresh(pipe):
            previous_time = self._get_tournament_score_reference(pipe)
            pipe.multi()
            if previous_time == score_time:
                return False
            if previous_time is not None:
                key = TOURNAMENT_USER_CACHE_KEYS['score_current']
                pipe.zunionstore(key, {key: tournament_score_decay_factor(previous_time, score_time)})
            pipe.set(TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY, score_time.isoformat())
            return True

        return cache.transaction(refresh, TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY, value_from_callable=True)

    def rebuild_tournament_current_score_cache(self, *, batch_size=1000):
        """从数据库重算当前积分 zset，并原子替换为当年年初锚点。"""
        if batch_size < 1:
            raise ValueError('batch_size must be positive')
        score_time = tournament_score_reference_time()
        key = TOURNAMENT_USER_CACHE_KEYS['score_current']

        def rebuild(pipe):
            # 重建期间仍可读取旧排行；并发缓存写入会令整个重建重试。
            pipe.multi()
            pipe.delete(key)
            pipe.set(TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY, score_time.isoformat())
            batch = []
            count = 0
            users = TournamentUser.objects.only('user_id', 'score_current', 'last_updated')
            for tournament_user in users.iterator(chunk_size=batch_size):
                batch.append(tournament_user)
                count += 1
                if len(batch) == batch_size:
                    self._update_tournament_users_in_pipeline(pipe, batch, ['score_current'], score_time=score_time)
                    batch = []
            self._update_tournament_users_in_pipeline(pipe, batch, ['score_current'], score_time=score_time)
            return count

        return cache.transaction(rebuild, TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY, key, value_from_callable=True)

    def get_tournament_user_ranking(self, field: str, *, start=0, end=20) -> tuple[list[TournamentUser], int]:
        """读取缓存内的左闭右开排行区间。"""
        key = TOURNAMENT_USER_CACHE_KEYS[field]
        total = cache.zcard(key)
        if total == 0 or start >= end:
            return [], total

        if field in TOURNAMENT_USER_ASC_FIELDS:
            user_ids = [int(user_id) for user_id in cache.zrange(key, start, end - 1)]
        else:
            user_ids = [int(user_id) for user_id in cache.zrevrange(key, start, end - 1)]

        tournament_users_by_id: dict[int, TournamentUser] = TournamentUser.objects.in_bulk(user_ids, field_name='user_id')
        return [tournament_users_by_id[user_id] for user_id in user_ids], total

    def _normalize_tournament_user_fields(self, fields):
        if fields is None:
            return TOURNAMENT_USER_RANK_FIELDS
        return tuple(field for field in fields if field in TOURNAMENT_USER_CACHE_KEYS)

    def _update_tournament_users_in_pipeline(self, pipe, tournament_users, fields, *, score_time=None):
        # 按字段汇总，每个 zset 每批最多一条 ZADD 和一条 ZREM。
        for field in fields:
            key = TOURNAMENT_USER_CACHE_KEYS[field]
            values = {}
            removed = set()
            for tournament_user in tournament_users:
                value = getattr(tournament_user, field)
                if value == TOURNAMENT_USER_DEFAULT_VALUES[field]:
                    values.pop(tournament_user.user_id, None)
                    removed.add(tournament_user.user_id)
                    continue
                if field == 'score_current':
                    # 数据库保留用户自己的时间基准，仅缓存分数换算到统一基准。
                    value *= tournament_score_decay_factor(tournament_user.last_updated, score_time)
                removed.discard(tournament_user.user_id)
                values[tournament_user.user_id] = value
            if removed:
                pipe.zrem(key, *removed)
            if values:
                pipe.zadd(key, values)


def serialize_normal_tournament(tournament: Tournament):
    if isinstance(tournament, GSCTournament):
        return CachedGSCTournament(
            id=tournament.id,
            state=tournament.state,
            subclass=Tournament_TextChoices.Subclass.GSC,
            host_id=tournament.host_id,
            start_time=tournament.start_time,
            end_time=tournament.end_time,
            data=CachedGSCTournamentData(
                order=tournament.order,
                token=tournament.token,
            ),
        )
    if isinstance(tournament, WeeklyEffTournament):
        return CachedWeeklyEffTournament(
            id=tournament.id, state=tournament.state,
            subclass=Tournament_TextChoices.Subclass.WEEKLY_EFF,
            host_id=tournament.host_id, start_time=tournament.start_time, end_time=tournament.end_time,
            data=CachedWeeklyEffTournamentData(year=tournament.year, week=tournament.week),
        )
    return CachedWeeklyTournament(
        id=tournament.id,
        state=tournament.state,
        subclass=Tournament_TextChoices.Subclass.WEEKLY,
        host_id=tournament.host_id,
        start_time=tournament.start_time,
        end_time=tournament.end_time,
        data=CachedWeeklyTournamentData(
            year=tournament.year,
            week=tournament.week,
            tournament_format=tournament.tournament_format,
        ),
    )


def deserialize_cached_tournament(value):
    json_value = maybe_bytes_to_str(value)
    raw_value = json.loads(json_value)
    if raw_value['subclass'] == Tournament_TextChoices.Subclass.GSC:
        return CachedGSCTournament.from_json(json_value)
    if raw_value['subclass'] == Tournament_TextChoices.Subclass.WEEKLY_EFF:
        return CachedWeeklyEffTournament.from_json(json_value)
    return CachedWeeklyTournament.from_json(json_value)


def serialize_normal_participant(participant: TournamentParticipant):
    return CachedNormalParticipant(
        id=participant.id,
        token=participant.token,
        arbiter_identifier=participant.arbiter_identifier.identifier if participant.arbiter_identifier else None,
        tournament=participant.tournament_id,
        start_time=participant.start_time,
        end_time=participant.end_time,
    )


def invalidate_normal_participant_cache():
    cache.delete(NORMAL_PARTICIPANT_CACHE_KEY)
