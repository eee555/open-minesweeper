# -*- coding: utf-8 -*-
import logging

from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models.functions import Power

from config.global_settings import MaxSizes
from config.text_choices import MS_TextChoices
from userprofile.models import UserProfile
from utils.parser import MSVideoParser
from .fields import RestrictedFileField

logger = logging.getLogger('videomanager')
MAX_TIMEMS = 99_999_999
STNB_COEFFICIENTS = {
    MS_TextChoices.Level.BEGINNER: 36,
    MS_TextChoices.Level.INTERMEDIATE: 162,
    MS_TextChoices.Level.EXPERT: 435,
}


class ExpandVideoModel(models.Model):
    # video = models.OneToOneField(VideoModel, on_delete=models.CASCADE)
    identifier = models.CharField(max_length=MaxSizes.IDENTIFIER, default='')
    tournament_identifier = models.JSONField(default=list)


# 其他类：checksum_ok, mode

# @receiver(post_save, sender=VideoModel)
# def create_expand_video(sender, instance, created, **kwargs):
#    if created:
#        ExpandVideoModel.objects.create(user=instance)

# @receiver(post_save, sender=VideoModel)
# def save_expand_video(sender, instance, **kwargs):
#     instance.profile.save()


# class File(models.Model):
#     file = RestrictedFileField(upload_to=user_directory_path, max_length=100,
# content_types=['application/pdf', 'application/excel', 'application/msword',
# 'text/plain', 'text/csv', 'application/zip',
# max_upload_size=5242880,)


# class Image(models.Model):
#     file = RestrictedFileField(upload_to=user_directory_path, max_length=100,
# content_types=['image/jpeg', 'image/gif', 'image/gif', 'image/bmp', 'image/tiff'],
# max_upload_size=5242880,)

def divideByTimeExpression(expr: models.Expression):
    return models.Case(models.When(timems=0, then=models.Value(0.0)), default=expr / models.F('timems') * models.Value(1000), output_field=models.FloatField())


# 基本的录像模型，最小限度展示录像信息
class VideoModel(models.Model):
    # 用户
    player = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    # 服务器端文件相对路径
    file = RestrictedFileField(
        upload_to='videos/%Y%m%d/', max_length=100, max_upload_size=MaxSizes.VIDEOFILE)
    file_size = models.PositiveIntegerField(default=0)
    original_hash = models.CharField(max_length=24, null=True, blank=True, unique=True)
    video = models.OneToOneField(
        ExpandVideoModel, on_delete=models.CASCADE, related_name='+')
    # file = models.FileField(upload_to='/assets/videos')
    # 上传时间，兼最近状态变化时间、更新时间（冻结后会刷新）
    upload_time = models.DateTimeField(auto_now_add=True, verbose_name='上传时间')
    # 录像自带时间戳，可被用户篡改，用于用户自用。实际上无时区，因为Django限制，固定时区为UTC。
    end_time = models.DateTimeField(null=True, blank=True)
    # 审核状态
    state = models.CharField(
        max_length=1, choices=MS_TextChoices.State.choices, default=MS_TextChoices.State.PLAIN)
    ongoing_tournament = models.BooleanField(default=False)
    # 软件: "a"->avf; "e"->evf; "u" ->url(未下载);
    software = models.CharField(max_length=MaxSizes.SOFTWARE, choices=MS_TextChoices.Software.choices)
    # 难度
    level = models.CharField(
        max_length=MaxSizes.GAMELEVEL, choices=MS_TextChoices.Level.choices)
    # 游戏模式，evf标准
    # https://github.com/eee555/ms_toollib/tree/main/base#readme
    is_lucky = models.BooleanField(default=False)
    mode = models.CharField(
        max_length=MaxSizes.GAMEMODE, choices=MS_TextChoices.Mode.choices, default=MS_TextChoices.Mode.STD)
    # 0.000-999.999
    timems = models.PositiveIntegerField(
        default=999999,
        validators=[MaxValueValidator(MAX_TIMEMS)],
    )  # 整数形式存储的毫秒数。
    # 0-32767
    bv = models.PositiveSmallIntegerField(null=True)
    bvs = models.GeneratedField(expression=models.Case(models.When(timems=0, then=models.Value(0.0)), default=models.F(
        'bv') / models.F('timems') * models.Value(1000), output_field=models.FloatField()), output_field=models.FloatField(), db_persist=True)
    iqg = models.GeneratedField(expression=models.Case(models.When(timems=0, then=models.Value(0.0)), default=models.F(
        'bv') / Power(models.F('timems') / models.Value(1000.0), models.Value(1.7)), output_field=models.FloatField()), output_field=models.FloatField(), db_persist=True)

    left = models.PositiveSmallIntegerField(null=True)
    right = models.PositiveSmallIntegerField(null=True)
    double = models.PositiveSmallIntegerField(null=True)
    cl = models.GeneratedField(expression=models.F('left') + models.F('right') + models.F(
        'double'), output_field=models.PositiveSmallIntegerField(), db_persist=True)

    left_ce = models.PositiveSmallIntegerField(null=True)
    right_ce = models.PositiveSmallIntegerField(null=True)
    double_ce = models.PositiveSmallIntegerField(null=True)
    ce = models.GeneratedField(expression=models.F('left_ce') + models.F('right_ce') + models.F(
        'double_ce'), output_field=models.PositiveSmallIntegerField(), db_persist=True)

    # 需要处理除零错误
    left_s = models.GeneratedField(expression=divideByTimeExpression(
        models.F('left')), output_field=models.FloatField(), db_persist=True)
    right_s = models.GeneratedField(expression=divideByTimeExpression(
        models.F('right')), output_field=models.FloatField(), db_persist=True)
    double_s = models.GeneratedField(expression=divideByTimeExpression(
        models.F('double')), output_field=models.FloatField(), db_persist=True)
    cl_s = models.GeneratedField(expression=divideByTimeExpression(
        models.F('cl')), output_field=models.FloatField(), db_persist=True)

    left_ces = models.GeneratedField(expression=divideByTimeExpression(
        models.F('left_ce')), output_field=models.FloatField(), db_persist=True)
    right_ces = models.GeneratedField(expression=divideByTimeExpression(
        models.F('right_ce')), output_field=models.FloatField(), db_persist=True)
    double_ces = models.GeneratedField(expression=divideByTimeExpression(
        models.F('double_ce')), output_field=models.FloatField(), db_persist=True)
    ce_s = models.GeneratedField(expression=divideByTimeExpression(
        models.F('ce')), output_field=models.FloatField(), db_persist=True)

    path = models.FloatField(null=True)
    pluck = models.FloatField(null=True, default=None)
    flag = models.PositiveSmallIntegerField(null=True)
    op = models.PositiveSmallIntegerField(null=True)
    isl = models.PositiveSmallIntegerField(null=True)

    flag_s = models.GeneratedField(expression=divideByTimeExpression(
        models.F('flag')), output_field=models.FloatField(), db_persist=True)
    ioe = models.GeneratedField(expression=models.F(
        'bv') / models.F('cl'), output_field=models.FloatField(), db_persist=True)
    thrp = models.GeneratedField(expression=models.F(
        'bv') / models.F('ce'), output_field=models.FloatField(), db_persist=True)
    corr = models.GeneratedField(expression=models.F(
        'ce') / models.F('cl'), output_field=models.FloatField(), db_persist=True)

    cell0 = models.PositiveSmallIntegerField(null=True)
    cell1 = models.PositiveSmallIntegerField(null=True)
    cell2 = models.PositiveSmallIntegerField(null=True)
    cell3 = models.PositiveSmallIntegerField(null=True)
    cell4 = models.PositiveSmallIntegerField(null=True)
    cell5 = models.PositiveSmallIntegerField(null=True)
    cell6 = models.PositiveSmallIntegerField(null=True)
    cell7 = models.PositiveSmallIntegerField(null=True)
    cell8 = models.PositiveSmallIntegerField(null=True)

    @property
    def stnb(self):
        coefficient = STNB_COEFFICIENTS.get(self.level)
        if coefficient is None or self.iqg is None:
            return None
        return coefficient * self.iqg

    def __str__(self):
        return f'level: {self.level}, timems: {self.timems}, 3BV: {self.bv}'

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(timems__lte=MAX_TIMEMS),
                name='videomodel_timems_max',
            ),
        ]
        indexes = [
            models.Index(fields=['level'], name='level_idx'),
            models.Index(fields=['mode'], name='mode_idx'),
            models.Index(fields=['bv'], name='bv_idx'),
            models.Index(fields=['bvs'], name='bvs_idx'),
            models.Index(fields=['iqg'], name='iqg_idx'),
            models.Index(fields=['thrp'], name='thrp_idx'),
            models.Index(fields=['timems'], name='timems_idx'),
            models.Index(fields=['state'], name='state_idx'),
            models.Index(fields=['level', 'mode', 'player', 'pluck'], name='video_lmp_pluck_idx'),
            models.Index(fields=['player', 'state', 'level'], name='video_player_state_level_idx'),
        ]

    @staticmethod
    def create_from_parser(parser: MSVideoParser, user: UserProfile, *, original_hash: str, upload_time=None):
        """
        注意：
        - 执行之前：
          - 检查录像数量
          - 检查identifier
          - 检查用户是否匿名
        - 执行之后：
          - 检查比赛标识
          - 刷新排行
        """
        e_video = ExpandVideoModel.objects.create(
            identifier=parser.identifier,
            tournament_identifier=parser.tournament_identifier,
        )
        video = VideoModel(
            player=user,
            upload_time=upload_time,
            file=parser.file, file_size=parser.file.size, original_hash=original_hash,
            video=e_video,
            end_time=parser.end_time,
            state=parser.state, software=parser.software,
            level=parser.level, mode=parser.mode,
            timems=parser.timems, bv=parser.bv,
            left=parser.left, right=parser.right, double=parser.double,
            left_ce=parser.left_ce, right_ce=parser.right_ce, double_ce=parser.double_ce,
            path=parser.path, pluck=parser.pluck, flag=parser.flag,
            op=parser.op, isl=parser.isl,
            cell0=parser.cell0, cell1=parser.cell1, cell2=parser.cell2,
            cell3=parser.cell3, cell4=parser.cell4, cell5=parser.cell5,
            cell6=parser.cell6, cell7=parser.cell7, cell8=parser.cell8,
        )
        video.save()  # noqa: DJM100
        return video

    def update_redis(self):
        user: UserProfile = self.player
        if self.state == MS_TextChoices.State.PLAIN:
            logger.info(f'用户 {user.username}#{user.id} 录像#{self.id} 机审失败')
        elif self.state == MS_TextChoices.State.IDENTIFIER:
            logger.info(f'用户 {user.username}#{user.id} 录像#{self.id} 标识不匹配')
        elif self.state == MS_TextChoices.State.FROZEN:
            logger.info(f'用户 {user.username}#{user.id} 录像#{self.id} 不合法')
        elif self.state == MS_TextChoices.State.OFFICIAL:  # 合法
            logger.info(f'用户 {user.username}#{user.id} 录像#{self.id} 机审成功')
