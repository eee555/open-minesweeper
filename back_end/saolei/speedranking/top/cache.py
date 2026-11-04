import json
import uuid

from django.utils import timezone

from .utils import ANCHOR_SIZE, LEVEL_WEIGHTS, MINIMUM_BV, original_value, parse_field, RANK_FIELDS, soft_coefficients, SOFT_FIELDS
from ..cache import cache, pipeline


class TopRankingCache:
    def __init__(self, namespace: str = 'speedranking'):
        self.prefix = f'{namespace}:top'
        self.detail_key = f'{self.prefix}:records'
        self.anchors_key = f'{self.prefix}:anchors'
        self.publication_key = f'{self.prefix}:soft:published'

    def rank_key(self, field: str) -> str:
        return f'{self.prefix}:{field}'

    def soft_key(self, field: str) -> str:
        return f'{self.prefix}:soft:{field}'

    def lsf_snapshot(self, player_ids):
        """读取一批玩家当前已发布的 LSF 值与名次（0 起），缺失返回 None。"""
        player_ids = list(player_ids)
        if not player_ids:
            return {}
        key = self.soft_key('lsf')
        with pipeline() as pipe:
            for player_id in player_ids:
                pipe.zscore(key, player_id)
            for player_id in player_ids:
                pipe.zrevrank(key, player_id)
            rows = pipe.execute()
        size = len(player_ids)
        return {
            player_id: (value, rank)
            for player_id, value, rank in zip(player_ids, rows[:size], rows[size:])
        }

    @property
    def keys(self):
        return [self.detail_key, self.anchors_key, self.publication_key, *[self.rank_key(field) for field in RANK_FIELDS], *[self.soft_key(field) for field in SOFT_FIELDS]]

    def read_records(self, pipe, player_ids):
        """将用户明细批量读取加入共享 pipeline。"""
        pipe.hmget(self.detail_key, player_ids)

    @staticmethod
    def unpack_records(rows, player_ids):
        return {player_id: json.loads(raw) if raw else {} for player_id, raw in zip(player_ids, rows)}

    def get_record(self, player_id: int):
        raw = cache.hget(self.detail_key, player_id)
        return json.loads(raw) if raw else {}

    def write_record(self, pipe, player_id: int, record: dict):
        """保存用户真实前五明细，空纪录删除。"""
        if record:
            pipe.hset(self.detail_key, player_id, json.dumps(record, allow_nan=False))
        else:
            pipe.hdel(self.detail_key, player_id)

    def write_score(self, pipe, player_id: int, field: str, value: float | None):
        if value is None:
            pipe.zrem(self.rank_key(field), player_id)
        else:
            pipe.zadd(self.rank_key(field), {str(player_id): value})

    def get_range(self, field: str, start: int, end: int, *, soft=False):
        """按小榜索引取用户，返回该页各用户的完整 hash 纪录，不回源。"""
        with pipeline() as pipe:
            key = self.soft_key(field) if soft else self.rank_key(field)
            pipe.zcard(key)
            if end > start:
                pipe.zrevrange(key, start, end - 1)
            results = pipe.execute()
        player_ids = [int(member) for member in results[1]] if end > start else []
        rows = cache.hmget(self.detail_key, player_ids) if player_ids else []
        players = []
        for player_id, raw in zip(player_ids, rows):
            if raw is not None:
                players.append({'player_id': player_id, 'records': json.loads(raw)})
        return {'count': results[0], 'players': players}

    def refresh_anchors(self, fields: set[str]):
        """每个变动小榜最多读取二十个 score，批量更新锚点。"""
        if not fields:
            return False
        fields = sorted(fields)
        with pipeline() as pipe:
            for field in fields:
                pipe.zrevrange(self.rank_key(field), 0, ANCHOR_SIZE - 1, withscores=True)
            pipe.hmget(self.anchors_key, fields)
            rows = pipe.execute()
        anchors = {}
        changed = False
        for field, entries, previous in zip(fields, rows[:-1], rows[-1]):
            stat = parse_field(field)[2]
            value = sum(original_value(stat, value) for member, value in entries) / len(entries) if entries else 0
            changed |= previous is None or json.loads(previous)['value'] != value
            anchors[field] = json.dumps({'value': value, 'sample_count': len(entries)}, allow_nan=False)
        cache.hset(self.anchors_key, mapping=anchors)
        return changed

    def get_publication(self):
        """读取正式软实力索引采用的锚点快照。"""
        raw = cache.get(self.publication_key)
        return json.loads(raw) if raw else None

    def rebuild_soft(self):
        """九次加权合并构建临时派生榜，成功后统一发布。"""
        anchors = self.get_anchors()
        prefix = f'{self.prefix}:soft:build:{uuid.uuid4().hex}'
        temporary = {field: f'{prefix}:{field}' for field in SOFT_FIELDS}
        try:
            with pipeline() as pipe:
                for mode in ('std', 'nf'):
                    for level in MINIMUM_BV:
                        coefficients = soft_coefficients(anchors, mode, level)
                        sources = {self.rank_key(f'{mode}:{level}{stat}'): weight for stat, weight in coefficients.items()}
                        pipe.zunionstore(temporary[f'{mode}:{level}'], sources)
                    pipe.zunionstore(temporary[f'{mode}:sum'], {temporary[f'{mode}:{level}']: weight for level, weight in LEVEL_WEIGHTS.items()})
                pipe.zunionstore(temporary['lsf'], {temporary['std:sum']: 0.97, temporary['nf:sum']: 0.03})
                pipe.execute()
            publication = {'anchors': anchors, 'version': uuid.uuid4().hex, 'updated_at': timezone.now().isoformat()}
            existing = cache.exists(*temporary.values())
            # 所有派生榜成员相同，因此要么全部为空，要么全部存在。
            if existing not in (0, len(SOFT_FIELDS)):
                raise RuntimeError('Incomplete temporary top soft rankings')
            with pipeline() as pipe:
                for field, source in temporary.items():
                    if existing:
                        pipe.rename(source, self.soft_key(field))
                    else:
                        pipe.delete(self.soft_key(field))
                pipe.set(self.publication_key, json.dumps(publication, allow_nan=False))
                pipe.execute()
            return cache.zcard(self.soft_key('lsf'))
        finally:
            cache.delete(*temporary.values())

    def get_anchors(self):
        """一次读取完整锚点 hash，不筛选字段或补齐缺项。"""
        return {field.decode() if isinstance(field, bytes) else field: json.loads(raw) for field, raw in cache.hgetall(self.anchors_key).items()}

    def flush(self):
        cache.delete(*self.keys)

    def publish_to(self, target):
        """将临时明细、十八个索引及锚点一并原子发布。"""
        with pipeline() as pipe:
            for source, destination in zip(self.keys, target.keys):
                if cache.exists(source):
                    pipe.rename(source, destination)
                else:
                    pipe.delete(destination)
            pipe.execute()
