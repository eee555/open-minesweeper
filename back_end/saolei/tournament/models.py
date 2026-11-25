import secrets
import string
from typing import Literal

from django.db import models
from django.utils import timezone
from django_tasks_db.models import DBTaskResult
from model_utils.managers import InheritanceManager

from config.global_settings import MaxSizes
from config.text_choices import Tournament_TextChoices
from config.tournaments import GSC_Defaults
from identifier.models import Identifier
from tournament.utils import (
    default_weekly_classic_et,
    default_weekly_classic_it,
    generate_random_token,
    insert_to_id_value_list_asc,
    MAX_TOURNAMENT_BEST,
    tournament_score_decay_factor,
)
from tournament.weekly.utils import WEEKLY_FORMAT_NAMES, WEEKLY_SCORE_CATEGORIES
from tournament.weekly_eff.utils import default_weekly_eff_et, default_weekly_eff_it, WEEKLY_EFF_DEFAULT_SCORE
from userprofile.models import UserProfile
from videomanager.models import VideoModel


def generate_GSC_token(length=GSC_Defaults.TOKEN_LENGTH):
    return 'G' + ''.join(secrets.choice(string.digits) for _ in range(length))


class Tournament(models.Model):
    objects = InheritanceManager()
    subclass = models.CharField(max_length=1, choices=Tournament_TextChoices.Subclass.choices, default=Tournament_TextChoices.Subclass.GSC)  # 比赛子类
    start_time = models.DateTimeField(null=True)  # 比赛开始时间
    end_time = models.DateTimeField(null=True)  # 比赛结束时间
    state = models.CharField(max_length=1, choices=Tournament_TextChoices.State.choices, default=Tournament_TextChoices.State.PENDING)  # 比赛状态
    host = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, related_name='owned_tournaments')  # 主办方
    weight = models.PositiveIntegerField(default=0)  # 比赛总积分
    videos = models.ManyToManyField(VideoModel, related_name='tournaments')

    @property
    def name(self):
        raise NotImplementedError("Subclasses of Tournament must implement the 'name' property.")

    @property
    def description(self):
        raise NotImplementedError("Subclasses of Tournament must implement the 'description' property.")

    @property
    def participants(self):
        return TournamentParticipant.objects.filter(tournament=self)

    def can_validate(self):
        return self.start_time is not None and self.end_time is not None and self.start_time < self.end_time

    def is_ongoing(self):
        now = timezone.now()
        return (
            self.state == Tournament_TextChoices.State.NORMAL
            and self.start_time is not None
            and self.end_time is not None
            and self.start_time <= now < self.end_time
        )

    def is_ended(self):
        return self.state == Tournament_TextChoices.State.AWARDED or (self.end_time is not None and self.end_time < timezone.now())

    def validate(self) -> list[str]:
        if not self.can_validate():
            return []
        if self.state == Tournament_TextChoices.State.PENDING or self.state == Tournament_TextChoices.State.CANCELLED:
            self.state = Tournament_TextChoices.State.NORMAL
            return ['state']
        return []

    def invalidate(self):
        if self.state != Tournament_TextChoices.State.AWARDED:
            self.state = Tournament_TextChoices.State.CANCELLED
            self.save(update_fields=['state'])

    def add_participant(self, user: UserProfile):
        raise NotImplementedError("Subclasses of Tournament must implement the 'add_participant' method.")

    @property
    def data(self):
        return {}

    def select_subclass(self):
        if type(self) is not Tournament:
            return self
        if self.subclass == Tournament_TextChoices.Subclass.WEEKLY:
            return WeeklyTournament.objects.filter(tournament_ptr_id=self.id).first() or self
        if self.subclass == Tournament_TextChoices.Subclass.WEEKLY_EFF:
            return WeeklyEffTournament.objects.filter(tournament_ptr_id=self.id).first() or self
        return GSCTournament.objects.filter(tournament_ptr_id=self.id).first() or self


class GSCTournament(Tournament):
    order = models.PositiveSmallIntegerField(primary_key=True)  # 届数
    _token = models.CharField(max_length=6, default='', db_column='token', db_collation='utf8mb4_0900_as_cs')  # 比赛标识
    task = models.ForeignKey(DBTaskResult, on_delete=models.SET_NULL, null=True)

    @property
    def name(self):
        return {
            'zh': f'第{self.order}届金羊杯',
            'en': f'GSC#{self.order}',
        }

    @property
    def description(self):
        return ''

    @property
    def data(self):
        return {
            'order': self.order,
            'token': self.token,
        }

    @property
    def token(self):
        if self.start_time is None or timezone.now() < self.start_time:
            return ''
        return self._token

    @token.setter
    def token(self, value):
        self._token = value

    def new_token(self):
        self._token = self.generate_unique_token()

    @property
    def order_by(self):
        return 't37'

    @staticmethod
    def generate_unique_token():
        token = generate_GSC_token()
        while GSCTournament.objects.filter(_token=token).exists() or TournamentParticipant.objects.filter(token=token).exists():
            token = generate_GSC_token()
        return token

    def validate(self) -> list[str]:
        if not self.can_validate():
            return []
        if self.state == Tournament_TextChoices.State.PENDING or self.state == Tournament_TextChoices.State.CANCELLED:
            self.state = Tournament_TextChoices.State.NORMAL
            update_fields = ['state']
            if not self._token:
                self._token = self.generate_unique_token()
                update_fields.append('_token')
            return update_fields
        return []

    def add_participant(self, user: UserProfile):
        if not GSCParticipant.objects.filter(user=user, tournament=self).exists():
            GSCParticipant.objects.create(
                user=user,
                tournament=self,
                token=self._token,
                start_time=self.start_time,
                end_time=self.end_time,
            )


class WeeklyTournament(Tournament):
    year = models.PositiveSmallIntegerField()  # 年份
    week = models.PositiveSmallIntegerField()  # 期数
    tournament_format = models.CharField(max_length=1, choices=Tournament_TextChoices.WeeklyFormat.choices, default=Tournament_TextChoices.WeeklyFormat.CLASSIC)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['year', 'week'], name='weekly_year_week_unique')]

    @property
    def name(self):
        prefix = WEEKLY_FORMAT_NAMES[self.tournament_format]
        return {
            'zh': f'{prefix["zh"]}竞速打卡赛 {self.year}年第{self.week}周',
            'en': f'{prefix["en"]} Speed Weekly {self.year}#{self.week}',
            'es': f'{prefix["es"]} Velocidad Semanal {self.year}#{self.week}',
        }

    @property
    def description(self):
        return ''

    @property
    def data(self):
        return {
            'year': self.year,
            'week': self.week,
            'tournament_format': self.tournament_format,
        }

    @property
    def order_by(self):
        Tournament_TextChoices.WeeklyFormat(self.tournament_format)
        return 'classic_score'


class WeeklyEffTournament(Tournament):
    year = models.PositiveSmallIntegerField()
    week = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['year', 'week'], name='weekly_eff_year_week_unique')]

    @property
    def name(self):
        return {'zh': f'{self.year}年第{self.week}周效率打卡赛', 'en': f'Efficiency Weekly {self.year}#{self.week}'}

    @property
    def description(self):
        return ''

    @property
    def data(self):
        return {'year': self.year, 'week': self.week}

    @property
    def order_by(self):
        return 'score'


class GeneralTournament(Tournament):
    name = models.JSONField()
    description = models.JSONField()
    csv_head = models.JSONField()


class TournamentParticipant(models.Model):
    token = models.CharField(max_length=MaxSizes.IDENTIFIER, db_collation='utf8mb4_0900_as_cs')  # 比赛标识
    arbiter_identifier = models.ForeignKey(Identifier, null=True, on_delete=models.PROTECT)  # 阿比特标识
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)  # 比赛
    user = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True)  # 用户
    start_time = models.DateTimeField(default=timezone.now)  # 参赛时间
    end_time = models.DateTimeField(null=True, blank=True)  # 结束时间
    rank = models.PositiveSmallIntegerField(null=True, blank=True)  # 排名
    rank_score = models.PositiveSmallIntegerField(default=0)  # 比赛积分

    class Meta:
        unique_together = ('tournament', 'user')

    def save(self, *args, **kwargs):
        """创建参赛者时生成唯一的token"""
        if self._state.adding and not self.token:
            while True:
                token = generate_random_token()
                if not TournamentParticipant.objects.filter(token=token).exists():
                    self.token = token
                    break
        super().save(*args, **kwargs)  # noqa: DJM100

    @property
    def videos(self):
        return self.tournament.videos.filter(player=self.user)


class GeneralParticipant(TournamentParticipant):
    pass


class GSCParticipant(TournamentParticipant):
    manual_scores = models.BooleanField(default=False)
    bt1st = models.PositiveIntegerField(default=GSC_Defaults.BT)
    bt20th = models.PositiveIntegerField(default=GSC_Defaults.BT)
    bt20sum = models.PositiveIntegerField(default=GSC_Defaults.BT * 20)

    it1st = models.PositiveIntegerField(default=GSC_Defaults.IT)
    it12th = models.PositiveIntegerField(default=GSC_Defaults.IT)
    it12sum = models.PositiveIntegerField(default=GSC_Defaults.IT * 12)

    et1st = models.PositiveIntegerField(default=GSC_Defaults.ET)
    et5th = models.PositiveIntegerField(default=GSC_Defaults.ET)
    et5sum = models.PositiveIntegerField(default=GSC_Defaults.ET * 5)

    t37 = models.GeneratedField(
        expression=models.F('et5sum') + models.F('it12sum') + models.F('bt20sum'),
        output_field=models.PositiveIntegerField(),
        db_persist=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=['t37'], name='gsc_t37_idx'),
        ]

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name in {'bt20sum', 'it12sum', 'et5sum'}:
            bt20sum = self.__dict__.get('bt20sum', GSC_Defaults.BT * 20)
            it12sum = self.__dict__.get('it12sum', GSC_Defaults.IT * 12)
            et5sum = self.__dict__.get('et5sum', GSC_Defaults.ET * 5)
            self.t37 = bt20sum + it12sum + et5sum


class WeeklyParticipant(TournamentParticipant):
    classic_et = models.JSONField(default=default_weekly_classic_et)
    classic_it = models.JSONField(default=default_weekly_classic_it)
    classic_score = models.PositiveIntegerField(default=780000)

    class Meta:
        indexes = [
            models.Index(fields=['classic_score'], name='classic_score_idx'),
        ]

    def classic_add_e(self, video_id: int, timems: int):
        diff = self.classic_et[1][1] - timems
        if diff > 0:
            self.classic_score -= diff
            if timems < self.classic_et[0][1]:
                self.classic_et[1] = self.classic_et[0]
                self.classic_et[0] = (video_id, timems)
            else:
                self.classic_et[1] = (video_id, timems)
        return diff

    def classic_add_i(self, video_id: int, timems: int):
        diff = self.classic_it[4][1] - timems
        if diff > 0:
            self.classic_score -= diff
            insert_to_id_value_list_asc(self.classic_it, video_id, timems)
        return diff


class WeeklyEffParticipant(TournamentParticipant):
    et = models.JSONField(default=default_weekly_eff_et)
    it = models.JSONField(default=default_weekly_eff_it)
    score = models.FloatField(default=WEEKLY_EFF_DEFAULT_SCORE)

    class Meta:
        indexes = [models.Index(fields=['score'], name='weekly_eff_score_idx')]


class TournamentUser(models.Model):
    user = models.OneToOneField(UserProfile, on_delete=models.CASCADE, primary_key=True)
    score_current = models.FloatField(default=0)  # 当前积分
    last_updated = models.DateTimeField(default=timezone.now)  # 最后结束的比赛时间
    score_total = models.PositiveIntegerField(default=0)  # 所有比赛历史总积分
    gsc_total = models.PositiveIntegerField(default=0)  # gsc历史总积分
    gsc_best = models.PositiveBigIntegerField(default=MAX_TOURNAMENT_BEST)  # gsc历史最好成绩及届数（后三位）
    weekly_total = models.PositiveIntegerField(default=0)  # 历史周赛总积分
    weekly_classic_total = models.PositiveIntegerField(default=0)  # 历史周赛经典模式总积分
    weekly_classic_best = models.PositiveBigIntegerField(default=MAX_TOURNAMENT_BEST)  # 历史周赛经典模式最好成绩及届数（后五位）
    weekly_nf_total = models.PositiveIntegerField(default=0)
    weekly_nf_best = models.PositiveBigIntegerField(default=MAX_TOURNAMENT_BEST)
    weekly_qwc_total = models.PositiveIntegerField(default=0)
    weekly_qwc_best = models.PositiveBigIntegerField(default=MAX_TOURNAMENT_BEST)
    weekly_qwc_nf_total = models.PositiveIntegerField(default=0)
    weekly_qwc_nf_best = models.PositiveBigIntegerField(default=MAX_TOURNAMENT_BEST)
    weekly_eff_total = models.PositiveIntegerField(default=0)
    weekly_eff_best = models.FloatField(null=True, default=None)
    weekly_eff_best_year = models.PositiveSmallIntegerField(null=True, default=None)
    weekly_eff_best_week = models.PositiveSmallIntegerField(null=True, default=None)

    def add_score(self, score: float | int, updated=None, *, category: Literal['gsc', 'weekly_classic', 'weekly_nf', 'weekly_qwc', 'weekly_qwc_nf', 'weekly_eff']):
        # score 是本场新旧积分的差额，历史成绩变差时也可能为负数。
        updated = updated or timezone.now()
        if self.score_current == 0 and self.score_total == 0:
            # 无积分时，创建时间不能作为衰减基准；仍须保留已结束的零积分比赛时间。
            latest_end = TournamentParticipant.objects.filter(user_id=self.user_id, rank__isnull=False, tournament__state=Tournament_TextChoices.State.AWARDED).aggregate(latest=models.Max('tournament__end_time'))['latest']
            self.last_updated = max(updated, latest_end or updated)
        if updated < self.last_updated:
            # 历史比赛的积分修正只衰减差额，不回退最后结束的比赛时间。
            self.score_current += score * tournament_score_decay_factor(updated, self.last_updated)
        else:
            # 新比赛结束得更晚：先衰减原积分，再加入本场差额并推进用户的时间基准。
            self.score_current = self.score_current * tournament_score_decay_factor(self.last_updated, updated) + score
            self.last_updated = updated
        # 历史累计积分不衰减，只按差额修正总量和所属分类。
        self.score_total += score
        if category == 'gsc':
            self.gsc_total += score
        elif category in WEEKLY_SCORE_CATEGORIES.values():
            field = f'{category}_total'
            setattr(self, field, getattr(self, field) + score)
            self.weekly_total += score
        elif category == 'weekly_eff':
            self.weekly_eff_total += score
