from django.db import models

from config.text_choices import Medal_TextChoices
from tournament.models import Tournament, TournamentParticipant
from userprofile.models import UserProfile
from videomanager.models import VideoModel


class MedalDefinition(models.Model):
    """一个 code 一行。改档是改这行的阈值或名单，不复制旧定义。"""

    code = models.CharField(max_length=64, primary_key=True)
    series = models.CharField(max_length=64, choices=Medal_TextChoices.Series)
    subseries = models.CharField(max_length=64, blank=True, default='')
    kind = models.CharField(max_length=32, choices=Medal_TextChoices.Kind)
    metric = models.CharField(max_length=32)
    direction = models.CharField(max_length=8, choices=Medal_TextChoices.Direction)
    level = models.CharField(max_length=32, blank=True, default='', choices=Medal_TextChoices.Level)
    style = models.CharField(max_length=8, blank=True, default='', choices=Medal_TextChoices.Style)
    thresholds = models.JSONField(default=list)
    bv_min = models.PositiveIntegerField(null=True, blank=True)
    scope = models.JSONField(default=dict)
    hidden = models.BooleanField(default=False)
    score_by_stage = models.JSONField(default=list)
    active = models.BooleanField(default=False)
    depends_on = models.JSONField(default=list)
    annotation = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['series', 'subseries', 'code']


class PlayerProgress(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='medal_progress')
    definition = models.ForeignKey(MedalDefinition, on_delete=models.CASCADE, related_name='progress_rows')
    code = models.CharField(max_length=64)
    current_stage = models.PositiveIntegerField(default=0)
    current_value = models.BigIntegerField(null=True, blank=True)
    extra = models.JSONField(null=True, blank=True)
    best_video = models.ForeignKey(VideoModel, null=True, blank=True, on_delete=models.SET_NULL, related_name='medal_progress_best')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'code'], name='medal_progress_user_code_uniq'),
        ]


class MedalGrant(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='medal_grants')
    definition_code = models.CharField(max_length=64)
    stage = models.PositiveIntegerField()
    scope_key = models.CharField(max_length=128, blank=True, default='')
    stage_log = models.JSONField(default=list)
    video = models.ForeignKey(VideoModel, null=True, blank=True, on_delete=models.SET_NULL, related_name='medal_grants')
    participant = models.ForeignKey(TournamentParticipant, null=True, blank=True, on_delete=models.SET_NULL, related_name='medal_grants')
    evidence = models.JSONField(default=dict)
    granted_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'definition_code', 'scope_key'], name='medal_grant_identity_uniq'),
        ]
        indexes = [
            models.Index(fields=['user', 'definition_code'], name='medal_grant_user_code_idx'),
            models.Index(fields=['user', 'revoked_at'], name='medal_grant_user_revoked_idx'),
        ]


class MedalContribution(models.Model):
    """累计去重行。source_key 必填，用来在 MySQL 上保证 (user, code) 下的来源唯一。"""

    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='medal_contributions')
    code = models.CharField(max_length=64)
    video = models.ForeignKey(VideoModel, null=True, blank=True, on_delete=models.SET_NULL, related_name='medal_contributions')
    tournament = models.ForeignKey(Tournament, null=True, blank=True, on_delete=models.SET_NULL, related_name='medal_contributions')
    level = models.CharField(max_length=32, blank=True, default='')
    bv = models.PositiveIntegerField(null=True, blank=True)
    source_key = models.CharField(max_length=191)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'code', 'source_key'], name='medal_contribution_source_uniq'),
        ]
        indexes = [
            models.Index(fields=['user', 'code'], name='medal_contrib_user_code_idx'),
        ]


class MedalPins(models.Model):
    user = models.OneToOneField(UserProfile, on_delete=models.CASCADE, primary_key=True, related_name='medal_pins')
    grant_ids = models.JSONField(default=list)


class MedalScan(models.Model):
    """这名玩家的历史录像和资料已经扫描过。没有这一行时，摘要只入队，不在请求里计算。"""

    user = models.OneToOneField(UserProfile, on_delete=models.CASCADE, primary_key=True, related_name='medal_scan')
    scanned_at = models.DateTimeField()


class PlayerMedalSummary(models.Model):
    """按玩家保存读模型。与评估、人工决定和佩戴在同一事务内更新。"""

    user = models.OneToOneField(UserProfile, on_delete=models.CASCADE, primary_key=True, related_name='medal_summary')
    data = models.JSONField(default=dict)


class MedalOverride(models.Model):
    """管理员锁定同一授予身份，直到明确恢复自动判定。"""

    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='medal_overrides')
    definition_code = models.CharField(max_length=64)
    scope_key = models.CharField(max_length=128, blank=True, default='')
    mode = models.CharField(max_length=8, choices=[('grant', 'grant'), ('revoke', 'revoke')])
    stage = models.PositiveIntegerField(null=True, blank=True)
    granted_at = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=255)
    actor = models.ForeignKey(UserProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name='medal_overrides_made')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'definition_code', 'scope_key'], name='medal_override_identity_uniq'),
        ]


class MedalOverrideLog(models.Model):
    """人工决定的追加审计；恢复自动只删除覆盖，不删除这份记录。"""

    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='medal_override_logs')
    definition_code = models.CharField(max_length=64)
    scope_key = models.CharField(max_length=128, blank=True, default='')
    action = models.CharField(max_length=8, choices=[('grant', 'grant'), ('revoke', 'revoke'), ('auto', 'auto')])
    stage = models.PositiveIntegerField(null=True, blank=True)
    granted_at = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=255)
    actor = models.ForeignKey(UserProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name='medal_override_logs_made')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'definition_code', 'scope_key'], name='medal_override_log_ident_idx'),
        ]
