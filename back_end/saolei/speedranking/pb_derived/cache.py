import json

from .utils import FIELDS, RANKINGS, score
from ..cache import cache, pipeline


class PBDerivedCache:
    """三个成绩 hash 与 132 个独立小榜 zset；member 直接为用户 id。"""

    def __init__(self, namespace: str = 'speedranking:pb_derived'):
        self.prefix = namespace

    def record_key(self, ranking: str):
        return f'{self.prefix}:{ranking}:records'

    def rank_key(self, ranking: str, field: str):
        return f'{self.prefix}:{ranking}:{field}'

    def keys(self):
        for ranking in RANKINGS:
            yield self.record_key(ranking)
            for field in FIELDS[ranking]:
                yield self.rank_key(ranking, field)

    def read_records(self, pipe, player_ids):
        ids = [str(player_id) for player_id in player_ids]
        for ranking in RANKINGS:
            pipe.hmget(self.record_key(ranking), ids)

    def unpack_records(self, results, player_ids):
        output = {player_id: {} for player_id in player_ids}
        for ranking, rows in zip(RANKINGS, results):
            for player_id, raw in zip(player_ids, rows):
                output[player_id][ranking] = json.loads(raw) if raw else {}
        return output

    def get_records(self, player_id: int):
        with pipeline() as pipe:
            for ranking in RANKINGS:
                pipe.hget(self.record_key(ranking), str(player_id))
            rows = pipe.execute()
        return {ranking: json.loads(raw) if raw else {} for ranking, raw in zip(RANKINGS, rows)}

    def write_changes(self, pipe, previous, changes, force=False):
        """只把发生变化的 hash 与 zset 写入共享 pipeline。"""
        for player_id, new in changes.items():
            old = {} if force else previous.get(player_id, {})
            for ranking in RANKINGS:
                new_values = new[ranking]
                old_values = {} if force else old.get(ranking, {})
                if not force and new_values == old_values:
                    continue
                if new_values:
                    pipe.hset(self.record_key(ranking), str(player_id), json.dumps(new_values))
                else:
                    pipe.hdel(self.record_key(ranking), str(player_id))
                for field in FIELDS[ranking]:
                    value = new_values.get(field)
                    if not force and value == old_values.get(field):
                        continue
                    key = self.rank_key(ranking, field)
                    if value is None:
                        pipe.zrem(key, str(player_id))
                    else:
                        pipe.zadd(key, {str(player_id): score(ranking, value)})

    def remove_player(self, pipe, player_id: int):
        for ranking in RANKINGS:
            pipe.hdel(self.record_key(ranking), str(player_id))
            for field in FIELDS[ranking]:
                pipe.zrem(self.rank_key(ranking, field), str(player_id))

    def get_range(self, rankings, ranking: str, field: str, start: int, end: int):
        key = self.rank_key(ranking, field)
        with pipeline() as pipe:
            pipe.zcard(key)
            if end > start:
                pipe.zrange(key, start, end - 1)
            results = pipe.execute()
        players = [int(value) for value in (results[1] if end > start else [])]
        ids = [str(player_id) for player_id in players]
        records = {name: {} for name in rankings}
        if ids:
            with pipeline() as pipe:
                for name in rankings:
                    pipe.hmget(self.record_key(name), ids)
                rows = pipe.execute()
            records = {name: {player_id: json.loads(raw) if raw else {} for player_id, raw in zip(players, values)} for name, values in zip(rankings, rows)}
        return {'count': results[0], 'players': players, 'records': records}

    def get_player_ranks(self, player_id: int):
        """一次 pipeline 读取 132 项 ZRANK，结果从 1 起，未入榜为 None。"""
        with pipeline() as pipe:
            for ranking in RANKINGS:
                for field in FIELDS[ranking]:
                    pipe.zrank(self.rank_key(ranking, field), str(player_id))
            results = pipe.execute()
        ranks = {ranking: {} for ranking in RANKINGS}
        index = 0
        for ranking in RANKINGS:
            for field in FIELDS[ranking]:
                rank = results[index]
                ranks[ranking][field] = rank + 1 if rank is not None else None
                index += 1
        return ranks

    def flush(self):
        keys = []
        for key in cache.scan_iter(match=f'{self.prefix}:*'):
            keys.append(key)
            if len(keys) >= 1000:
                cache.delete(*keys)
                keys.clear()
        if keys:
            cache.delete(*keys)
