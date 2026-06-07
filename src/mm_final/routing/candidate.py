"""候选路线方案的中性内部表示。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence


RouteConstructor = Callable[[Sequence[str]], Sequence[str]]


@dataclass(frozen=True)
class CandidateRoute:
    route_id: str
    required_visit_order: tuple[str, ...]


@dataclass(frozen=True)
class CandidateSolution:
    routes: tuple[CandidateRoute, ...]
    method: str = "manual_candidate"
    parameters: Mapping[str, Any] = field(default_factory=dict)
    seed: Optional[int] = None
    runtime_seconds: Optional[float] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "routes", tuple(self.routes))
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


def build_candidate_from_groups(
    groups: Iterable[Sequence[str]],
    route_constructor: RouteConstructor,
    *,
    method: str = "grouped_candidate",
    parameters: Optional[Mapping[str, Any]] = None,
    seed: Optional[int] = None,
    runtime_seconds: Optional[float] = None,
) -> CandidateSolution:
    routes = []
    for index, group in enumerate(groups, start=1):
        visit_order = tuple(route_constructor(tuple(group)))
        routes.append(CandidateRoute(route_id=f"R{index}", required_visit_order=visit_order))

    return CandidateSolution(
        routes=tuple(routes),
        method=method,
        parameters={} if parameters is None else parameters,
        seed=seed,
        runtime_seconds=runtime_seconds,
    )
