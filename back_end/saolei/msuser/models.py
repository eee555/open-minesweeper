from django.db import models


def get_default_identifiers():
    return []


# 扫雷用户的标识、录像计数与上传额度
class UserMS(models.Model):
    # 用户的标识。管理员审核通过后可以自由使用该标识。
    identifiers = models.JSONField(default=get_default_identifiers)
    # 总录像数限制默认100，计划管理员可以修改。高水平玩家也可以增多。
    video_num_limit = models.IntegerField(null=False, default=100)

    # 非比赛录像数量，沿用历史字段名，供上传额度检查使用
    video_num_total = models.IntegerField(null=False, default=0)
    video_num_tournament = models.IntegerField(default=0)
    video_num_all = models.GeneratedField(
        expression=models.F('video_num_total') + models.F('video_num_tournament'),
        output_field=models.BigIntegerField(),
        db_persist=True,
    )

    # 按 VideoModel.file_size 求和，单位为字节
    video_size_total = models.BigIntegerField(default=0)
    video_size_tournament = models.BigIntegerField(default=0)
    video_size_all = models.GeneratedField(
        expression=models.F('video_size_total') + models.F('video_size_tournament'),
        output_field=models.BigIntegerField(),
        db_persist=True,
    )

    def __str__(self):
        return 'identifiers: {}'.format(self.identifiers)
