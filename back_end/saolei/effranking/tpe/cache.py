from .utils import LEVELS, RANK_STATS
from ..cache import EfficiencyRankingCache


class TPERankingCache(EfficiencyRankingCache):
    ranking_name = 'tpe'
    stats = RANK_STATS
    record_fields = LEVELS
