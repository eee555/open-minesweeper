# -*- coding: utf-8 -*-
from django.db import models
from django_tasks_db.models import DBTaskResult

from config.text_choices import MS_TextChoices, Saolei_TextChoices
from userprofile.models import UserProfile
from videomanager.models import VideoModel
from .msgames.utils import supports_replay
from .wom.utils import ENDURANCE_BASE_MS


class Platform(models.TextChoices):
    BILIBILI = 'B', ('Bilibili')
    MSGAMES = 'a', ('Authoritative Minesweeper')
    MINERACER = 'm', ('Mineracer')
    QQ = 'q', ('腾讯QQ')
    SAOLEI = 'c', ('扫雷网')
    WOM = 'w', ('Minesweeper.Online')


MINERACER_USERID_MAX_LENGTH = 64


# 用于验证的队列
class AccountLinkQueue(models.Model):
    platform = models.CharField(max_length=1, null=False, choices=Platform.choices)
    identifier = models.CharField(max_length=128, null=False)
    userprofile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    verified = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=['platform', 'identifier'], name='accountlink_platform_id_idx')]


# 扫雷网账号信息
class AccountSaolei(models.Model):
    id = models.PositiveIntegerField(primary_key=True)
    parent = models.OneToOneField(UserProfile, on_delete=models.CASCADE, related_name='account_saolei')
    update_time = models.DateTimeField(auto_now_add=True)

    video_import_task = models.ForeignKey(DBTaskResult, on_delete=models.SET_NULL, null=True)

    name = models.CharField(max_length=10, default='')  # 姓名，10应该够了吧
    total_views = models.PositiveIntegerField(default=0)  # 综合人气

    beg_count = models.PositiveSmallIntegerField(default=0)  # 初级录像数量
    int_count = models.PositiveSmallIntegerField(default=0)  # 中级录像数量
    exp_count = models.PositiveSmallIntegerField(default=0)  # 高级录像数量

    # time纪录，单位毫秒
    b_t_ms = models.PositiveIntegerField(null=True)
    i_t_ms = models.PositiveIntegerField(null=True)
    e_t_ms = models.PositiveIntegerField(null=True)
    s_t_ms = models.PositiveIntegerField(null=True)

    # bvs纪录，单位0.01。大概不会有人bvs超过300吧？大概吧？
    b_b_cent = models.PositiveSmallIntegerField(null=True)
    i_b_cent = models.PositiveSmallIntegerField(null=True)
    e_b_cent = models.PositiveSmallIntegerField(null=True)
    s_b_cent = models.PositiveSmallIntegerField(null=True)


class VideoSaolei(models.Model):
    id = models.PositiveIntegerField(primary_key=True)
    user = models.ForeignKey(AccountSaolei, on_delete=models.DO_NOTHING, related_name='videos')
    upload_time = models.DateTimeField()
    level = models.CharField(
        max_length=1,
        choices=[
            (MS_TextChoices.Level.BEGINNER, MS_TextChoices.Level.BEGINNER.label),
            (MS_TextChoices.Level.INTERMEDIATE, MS_TextChoices.Level.INTERMEDIATE.label),
            (MS_TextChoices.Level.EXPERT, MS_TextChoices.Level.EXPERT.label),
        ],
    )
    bv = models.PositiveSmallIntegerField(default=0)
    timems = models.PositiveIntegerField(default=0)
    nf = models.BooleanField(default=False)
    state = models.CharField(max_length=1, choices=Saolei_TextChoices.SaoleiVideoState.choices)
    import_video = models.OneToOneField(VideoModel, on_delete=models.SET_NULL, null=True)
    import_task = models.ForeignKey(DBTaskResult, on_delete=models.SET_NULL, null=True)

    @property
    def url(self):
        return f'http://saolei.wang/Video/Show.asp?Id={self.id}'


class AccountMinesweeperGames(models.Model):
    id = models.PositiveIntegerField(primary_key=True)
    parent = models.OneToOneField(UserProfile, on_delete=models.CASCADE, related_name='account_msgames')
    update_time = models.DateTimeField(auto_now=True)

    name = models.CharField(max_length=128, default='')
    local_name = models.CharField(max_length=128, default='')
    country = models.TextField(default='', blank=True, help_text='Public country text as displayed by MSGames, without an enum.')
    state = models.TextField(default='', blank=True, help_text='Public region text as displayed by MSGames, without an enum.')
    joined = models.DateField(null=True)
    hand = models.TextField(default='', blank=True, help_text='Public handedness text as displayed by MSGames.')
    mouse = models.TextField(default='', blank=True, help_text='Public mouse text as displayed by MSGames.')
    video_update_time = models.DateTimeField(null=True)


class VideoMSGames(models.Model):
    user = models.ForeignKey(AccountMinesweeperGames, on_delete=models.CASCADE, related_name='videos')
    source_key = models.CharField(max_length=64, unique=True, help_text='SHA-256 of the original replay URL, used for deduplication.')
    url = models.TextField(help_text='Original replay URL published by MSGames.')
    filename = models.TextField()
    upload_date = models.DateField(null=True, help_text='Public upload date; imports use the following midnight UTC as its upper bound.')
    category = models.TextField(default='', help_text='Displayed metric, groups, style and category, merged across score histories.')
    score = models.TextField(default='', help_text='Displayed score strings, preserving source precision.')
    density_levels = models.JSONField(default=list, help_text='Density custom levels; null entries denote unsupported or unknown configurations.')
    import_video = models.ForeignKey(VideoModel, on_delete=models.SET_NULL, null=True, related_name='+')

    @property
    def can_import(self):
        return supports_replay(self.filename, self.category, self.density_levels)


class AccountBilibili(models.Model):
    id = models.PositiveBigIntegerField(primary_key=True, verbose_name='Bilibili UID', help_text='Numeric Bilibili user ID from space.bilibili.com/{uid}.')
    parent = models.OneToOneField(UserProfile, on_delete=models.CASCADE, related_name='account_bilibili', verbose_name='OpenMS user', help_text='OpenMS user linked to this Bilibili account.')
    update_time = models.DateTimeField(auto_now=True, verbose_name='Update time', help_text='Time when public Bilibili profile data was last synchronized.')

    name = models.CharField(max_length=128, default='', verbose_name='Display name', help_text='Public Bilibili display name.')
    face = models.URLField(max_length=500, default='', verbose_name='Avatar URL', help_text='Public Bilibili avatar URL.')
    sign = models.TextField(default='', verbose_name='Signature', help_text='Public Bilibili profile signature.')
    level = models.PositiveSmallIntegerField(default=0, help_text='Bilibili user level.')
    following = models.PositiveIntegerField(default=0, verbose_name='Following count')
    follower = models.PositiveIntegerField(default=0, verbose_name='Follower count')
    video_count = models.PositiveIntegerField(default=0, help_text='Number of public video submissions by this Bilibili account.')
    article_count = models.PositiveIntegerField(default=0, help_text='Number of public article submissions by this Bilibili account.')
    opus_count = models.PositiveIntegerField(default=0, help_text='Number of public opus/dynamic posts by this Bilibili account.')
    official_title = models.CharField(max_length=128, default='', verbose_name='Official title', help_text='Bilibili official verification title, or an empty string when unverified.')


class AccountWorldOfMinesweeper(models.Model):
    id = models.PositiveIntegerField(primary_key=True)
    parent = models.OneToOneField(UserProfile, on_delete=models.CASCADE, related_name='account_wom')
    update_time = models.DateTimeField(auto_now=True)

    # name 有的用户名过不了审
    # country 有争议
    trophy = models.PositiveSmallIntegerField(null=True)

    experience = models.PositiveIntegerField(null=True)

    arena_point = models.PositiveSmallIntegerField(null=True)  # 最高80
    max_difficulty = models.PositiveIntegerField(null=True)
    win = models.PositiveIntegerField(null=True)
    last_season = models.PositiveSmallIntegerField(null=True)

    b_t_ms = models.PositiveIntegerField(null=True)
    i_t_ms = models.PositiveIntegerField(null=True)
    e_t_ms = models.PositiveIntegerField(null=True)

    b_ioe = models.FloatField(null=True)
    i_ioe = models.FloatField(null=True)
    e_ioe = models.FloatField(null=True)

    b_mastery = models.PositiveSmallIntegerField(null=True)
    i_mastery = models.PositiveSmallIntegerField(null=True)
    e_mastery = models.PositiveSmallIntegerField(null=True)

    b_winstreak = models.PositiveSmallIntegerField(null=True)
    i_winstreak = models.PositiveSmallIntegerField(null=True)
    e_winstreak = models.PositiveSmallIntegerField(null=True)

    b_endurance_ms = models.PositiveIntegerField(default=ENDURANCE_BASE_MS, null=False, help_text='Best beginner endurance time in milliseconds; 86400000 when no record.')
    i_endurance_ms = models.PositiveIntegerField(default=ENDURANCE_BASE_MS, null=False, help_text='Best intermediate endurance time in milliseconds; 86400000 when no record.')
    e_endurance_ms = models.PositiveIntegerField(default=ENDURANCE_BASE_MS, null=False, help_text='Best expert endurance time in milliseconds; 86400000 when no record.')

    b_ng_t_ms = models.PositiveIntegerField(null=True, help_text='Beginner no-guess personal-best time in milliseconds.')
    i_ng_t_ms = models.PositiveIntegerField(null=True, help_text='Intermediate no-guess personal-best time in milliseconds.')
    e_ng_t_ms = models.PositiveIntegerField(null=True, help_text='Expert no-guess personal-best time in milliseconds.')

    b_win = models.PositiveIntegerField(null=True, help_text='Total beginner wins.')
    i_win = models.PositiveIntegerField(null=True, help_text='Total intermediate wins.')
    e_win = models.PositiveIntegerField(null=True, help_text='Total expert wins.')
    b_ng_win = models.PositiveIntegerField(null=True, help_text='Total beginner no-guess wins.')
    i_ng_win = models.PositiveIntegerField(null=True, help_text='Total intermediate no-guess wins.')
    e_ng_win = models.PositiveIntegerField(null=True, help_text='Total expert no-guess wins.')

    experience_total = models.PositiveIntegerField(null=True, help_text='Lifetime experience earned (expAll), distinct from current experience.')
    minecoin_total = models.PositiveIntegerField(null=True, help_text='Lifetime minecoins earned (coinsAll), not current inventory.')
    gem_total = models.PositiveIntegerField(null=True, help_text='Lifetime gems earned (gemsAll), not current inventory.')
    arena_coin_total = models.PositiveIntegerField(null=True, help_text='Lifetime arena coins earned (arenaCoinsAll), not current inventory.')
    game_count = models.PositiveIntegerField(null=True, help_text='Public game count (games).')
    win_nf = models.PositiveIntegerField(null=True, help_text='Lifetime wins without flags (winsNf); no-flag and no-guess are different modes.')
    play_time_ms = models.PositiveBigIntegerField(null=True, help_text='Lifetime play time in milliseconds (timeAll).')
    arena_play_time_ms = models.PositiveBigIntegerField(null=True, help_text='Lifetime arena play time in milliseconds (arenaDuration).')
    bbbv_total = models.PositiveIntegerField(null=True, help_text='Lifetime 3BV total (bbbvAll).')
    season_count = models.PositiveSmallIntegerField(null=True, help_text='Number of seasons played (seasons), with one season per month.')


class AccountMineracer(models.Model):
    id = models.CharField(max_length=MINERACER_USERID_MAX_LENGTH, primary_key=True, verbose_name='Mineracer Userid', help_text='Up to 64-character Mineracer Userid.')
    parent = models.OneToOneField(UserProfile, on_delete=models.CASCADE, related_name='account_mineracer', verbose_name='OpenMS user', help_text='OpenMS user linked to this Mineracer account.')
    update_time = models.DateTimeField(auto_now=True, verbose_name='Update time', help_text='Time when this Mineracer account link was last updated.')


# 使用QQ互联提供的登录接口需要开发者注册，步骤繁琐，不利于去中心化
class AccountQQ(models.Model):
    id = models.PositiveBigIntegerField(primary_key=True)
    parent = models.OneToOneField(UserProfile, on_delete=models.CASCADE, related_name='account_qq')


PLATFORM_CONFIG = {
    Platform.BILIBILI: {
        'model': AccountBilibili,
        'related_name': 'account_bilibili',
    },
    Platform.MSGAMES: {
        'model': AccountMinesweeperGames,
        'related_name': 'account_msgames',
    },
    Platform.MINERACER: {
        'model': AccountMineracer,
        'related_name': 'account_mineracer',
    },
    Platform.SAOLEI: {
        'model': AccountSaolei,
        'related_name': 'account_saolei',
    },
    Platform.WOM: {
        'model': AccountWorldOfMinesweeper,
        'related_name': 'account_wom',
    },
    Platform.QQ: {
        'model': AccountQQ,
        'related_name': 'account_qq',
    },
}
