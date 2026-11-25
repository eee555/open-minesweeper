from .utils import RANK_STATS, RECORD_FIELDS
from ..cache import EfficiencyRankingCache


class PathRankingCache(EfficiencyRankingCache):
    ranking_name = 'path'
    stats = RANK_STATS
    record_fields = RECORD_FIELDS
