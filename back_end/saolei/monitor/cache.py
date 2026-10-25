from datetime import datetime, timezone
from itertools import islice
import logging
import time

from django_redis import get_redis_connection

from config.customranking import CUSTOM_PLUCK_LEVELS
from customranking.cache import get_custom_pluck_detail_key, get_custom_pluck_rank_key
from effranking.thrp.cache import ThrpRankingCache
from minigame.cache import MiniGameRankingCache
from speedranking.pb.cache import PBRankingCache
from speedranking.pb.utils import LEVELS, parse_field, record_field
from speedranking.saolei.cache import SpeedRankingCache
from speedranking.saolei.utils import RANK_STATS, RANKING_NAMES
from speedranking.top.cache import TopRankingCache
from tournament.cache import TOURNAMENT_USER_CACHE_KEYS, TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY
from videomanager.cache import newest_cache
from .server_metrics import check_deadline, CollectionError

logger = logging.getLogger(__name__)
MEMORY_BATCH_SIZE = 100
MAX_MEMORY_KEYS = 50_000
MEMORY_SAMPLES = 5


def _known_memory_keys(ranking, fields, player_ids):
    yield 'pb_rankings', ranking.counts_key
    for raw in fields:
        try:
            field = raw.decode() if isinstance(raw, bytes) else raw
            nf, level, bv = parse_field(field)
            if level not in LEVELS or bv <= 0 or record_field(nf, level, bv) != field:
                raise ValueError('Invalid PB field')
        except (ValueError, TypeError):
            raise CollectionError('metadata_unavailable')
        yield 'pb_rankings', ranking.rank_key(field)
    for name in RANKING_NAMES:
        for key in SpeedRankingCache(name, stats=RANK_STATS).keys:
            yield 'other_rankings', key
    for key in TopRankingCache().keys:
        yield 'other_rankings', key
    for key in ThrpRankingCache().keys:
        yield 'other_rankings', key
    for key in MiniGameRankingCache().keys:
        yield 'other_rankings', key
    for level in sorted(CUSTOM_PLUCK_LEVELS):
        yield 'other_rankings', get_custom_pluck_rank_key(level)
        yield 'other_rankings', get_custom_pluck_detail_key(level)
    for key in (*TOURNAMENT_USER_CACHE_KEYS.values(), TOURNAMENT_USER_SCORE_CURRENT_TIME_KEY):
        yield 'other_rankings', key
    yield 'latest_videos', newest_cache.key
    for player_id in player_ids:
        yield 'pb_rankings', ranking.player_key(player_id)


def collect_redis_memory(player_ids, deadline):
    started = time.monotonic()
    client = get_redis_connection('saolei_website')
    ranking = PBRankingCache()
    check_deadline(deadline)
    # Only read this fixed metadata hash; never discover keys from the keyspace.
    fields = client.hkeys(ranking.counts_key)
    if not fields:
        raise CollectionError('metadata_unavailable')
    if len(fields) > MAX_MEMORY_KEYS:
        raise CollectionError('budget_exceeded')
    keys = iter(_known_memory_keys(ranking, fields, player_ids))
    seen = set()
    groups = {'pb_rankings': 0, 'other_rankings': 0, 'latest_videos': 0}
    while batch := list(islice(keys, MEMORY_BATCH_SIZE)):
        check_deadline(deadline)
        unique = []
        for group, key in batch:
            if key in seen:
                continue
            seen.add(key)
            if len(seen) > MAX_MEMORY_KEYS:
                raise CollectionError('budget_exceeded')
            unique.append((group, key))
        if not unique:
            continue
        with client.pipeline(transaction=False) as pipe:
            for _, key in unique:
                pipe.memory_usage(key, samples=MEMORY_SAMPLES)
            results = pipe.execute()
        for (group, _), value in zip(unique, results, strict=True):
            if value is not None:
                if value < 0:
                    raise CollectionError('inconsistent_snapshot')
                groups[group] += value
    check_deadline(deadline)
    total = int(client.info('memory')['used_memory'])
    check_deadline(deadline)
    other = total - sum(groups.values())
    if other < 0:
        raise CollectionError('inconsistent_snapshot')
    groups['other'] = other
    logger.info('Redis memory collected: keys=%s elapsed=%.3fs', len(seen), time.monotonic() - started)
    return {
        'status': 'ready', 'reason': None, 'sampled_at': datetime.now(timezone.utc),
        'metric': 'redis_allocated', 'total_bytes': total, 'groups': groups,
        'estimated': True, 'samples': MEMORY_SAMPLES,
    }
