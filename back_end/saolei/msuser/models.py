from django.db import models


def get_default_identifiers():
    return []


# 扫雷用户的标识、录像计数与上传额度
class UserMS(models.Model):
    # 用户的标识。管理员审核通过后可以自由使用该标识。
    identifiers = models.JSONField(default=get_default_identifiers)
    # 总录像数限制默认100，计划管理员可以修改。高水平玩家也可以增多。
    video_num_limit = models.IntegerField(null=False, default=100)

    # 录像总数，排除比赛录像
    video_num_total = models.IntegerField(null=False, default=0)

    def __str__(self):
        return 'identifiers: {}'.format(self.identifiers)
