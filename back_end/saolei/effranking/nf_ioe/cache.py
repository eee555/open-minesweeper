from .utils import LEVELS, RANK_STATS
from ..cache import EfficiencyRankingCache


class NFIOERankingCache(EfficiencyRankingCache):
    ranking_name = 'nf_ioe'
    stats = RANK_STATS
    record_fields = LEVELS
