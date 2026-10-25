from dataclasses import asdict, dataclass

from config.global_settings import MAX_SAFE_INTEGER


@dataclass(frozen=True)
class Ranking:
    key: str
    game: str
    level: str
    density: str | None = None
    order: str = 'asc'
    unit: str = 'ms'
    min_score: int = 1
    max_score: int = MAX_SAFE_INTEGER
    accept_submissions: bool = True

    def is_better(self, score, previous):
        return score < previous if self.order == 'asc' else score > previous


GAME_RANKINGS = {
    'left-click': tuple(Ranking(f'left-click-{level}-{density}-v1', 'left-click', level, density)
                        for level in ('b', 'i', 'e') for density in ('50', '75', '87.5')),
    'multi-touch': tuple(Ranking(f'multi-touch-{level}-{density}-v1', 'multi-touch', level, density)
                         for level in ('b', 'i', 'e') for density in ('50', '75', '87.5')),
    'flag-chord': tuple(Ranking(f'flag-chord-{level}-v1', 'flag-chord', level) for level in ('b', 'i')),
    'missing-cell': tuple(Ranking(f'missing-cell-{level}-v1', 'missing-cell', level) for level in ('b', 'i', 'e')),
}
RANKINGS = {ranking.key: ranking for rankings in GAME_RANKINGS.values() for ranking in rankings}


def ranking_definitions():
    return [{'game': game, 'rankings': [asdict(ranking) for ranking in rankings]} for game, rankings in GAME_RANKINGS.items()]


class MiniGameError(Exception):
    def __init__(self, status, code, detail):
        super().__init__(status, code, detail)
        self.status = status
        self.code = code
        self.detail = detail
