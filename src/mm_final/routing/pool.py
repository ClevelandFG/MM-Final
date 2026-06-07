"""候选方案池。"""

from __future__ import annotations

from dataclasses import dataclass

from mm_final.routing.candidate import CandidateSolution
from mm_final.routing.scoring import Score


@dataclass(frozen=True)
class ScoredCandidate:
    solution: CandidateSolution
    score: Score


class SolutionPool:
    def __init__(self, max_size: int = 5) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be > 0.")
        self.max_size = max_size
        self._items: list[ScoredCandidate] = []

    @property
    def items(self) -> tuple[ScoredCandidate, ...]:
        return tuple(self._items)

    @property
    def best(self) -> ScoredCandidate:
        if not self._items:
            raise ValueError("SolutionPool is empty.")
        return self._items[0]

    def add(self, solution: CandidateSolution, score: Score) -> None:
        self._items.append(ScoredCandidate(solution=solution, score=score))
        self._items.sort(key=lambda item: item.score.sort_key)
        del self._items[self.max_size :]
