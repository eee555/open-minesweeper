from django.core.cache import cache

# 扫雷网绑定确认凭据：仅证明指定令牌由指定本站用户确认，24h 后自然失效。
SAOLEI_BIND_EVIDENCE_TTL = 24 * 3600


def _bind_evidence_key(token: str) -> str:
    return f'accountlink:saolei:bind:{token}'


def save_bind_evidence(token: str, *, confirmer_id: int, uid: int, username: str, sync: bool):
    cache.set(_bind_evidence_key(token), {
        'confirmer_id': confirmer_id,
        'uid': uid,
        'username': username,
        'sync': sync,
    }, timeout=SAOLEI_BIND_EVIDENCE_TTL)


def load_bind_evidence(token: str) -> dict | None:
    return cache.get(_bind_evidence_key(token))
