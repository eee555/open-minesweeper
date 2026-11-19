from .utils import RANK_STATS, RECORD_FIELDS
from ..cache import EfficiencyRankingCache


class TPERankingCache(EfficiencyRankingCache):
    ranking_name = 'tpe'
    stats = RANK_STATS
    record_fields = RECORD_FIELDS
