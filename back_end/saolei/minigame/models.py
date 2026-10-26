from django.db import models
from django.utils import timezone

from userprofile.models import UserProfile


class MiniGameBestScore(models.Model):
    player = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    ranking_key = models.CharField(max_length=64)
    score = models.BigIntegerField()
    achieved_at = models.DateTimeField(default=timezone.now)
    replay_archive = models.BinaryField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['player', 'ranking_key'], name='minigame_player_ranking_uniq')]
        indexes = [models.Index(fields=['ranking_key', 'score', 'id'], name='minigame_ranking_score_idx')]
