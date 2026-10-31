from .utils import LEVELS, NF_STAT, RANK_STATS
from ..cache import EfficiencyRankingCache


class ThrpRankingCache(EfficiencyRankingCache):
    ranking_name = 'thrp'
    stats = RANK_STATS
    record_fields = (*LEVELS, NF_STAT)
