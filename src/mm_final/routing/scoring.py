"""共享评分核心，供 A 线高频搜索与 B 线复算共同调用。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional

from mm_final.network import DEPOT, REQUIRED_VISIT_NODES, NodeType, classify_node
from mm_final.routing.candidate import CandidateSolution
from mm_final.routing.distance_matrix import DistanceMatrix


@dataclass(frozen=True)
class ScoreDiagnostic:
    code: str
    severity: str
    path: str
    message: str


@dataclass(frozen=True)
class ObjectiveSpec:
    T_hour: float = 2.0
    t_hour: float = 1.0
    speed_km_per_hour: float = 35.0
    time_limit_hour: float = 24.0
    required_visit_nodes: frozenset[str] = field(default_factory=lambda: frozenset(REQUIRED_VISIT_NODES))
    fixed_group_count: Optional[int] = None
    mode: str = "lexicographic"
    weights: Mapping[str, float] = field(default_factory=dict)
    empty_route_penalty: float = 1000.0
    missing_required_penalty: float = 1000.0
    duplicate_required_penalty: float = 1000.0
    group_count_mismatch_penalty: float = 1000.0
    time_limit_penalty_weight: float = 1000.0

    def validate(self) -> None:
        if self.fixed_group_count is not None and self.fixed_group_count <= 0:
            raise ValueError("fixed_group_count must be > 0 when provided.")
        if self.T_hour < 0:
            raise ValueError("T_hour must be >= 0.")
        if self.t_hour < 0:
            raise ValueError("t_hour must be >= 0.")
        if self.speed_km_per_hour <= 0:
            raise ValueError("speed_km_per_hour must be > 0.")
        if self.time_limit_hour <= 0:
            raise ValueError("time_limit_hour must be > 0.")
        if self.mode not in {"lexicographic", "weighted"}:
            raise ValueError("mode must be 'lexicographic' or 'weighted'.")


@dataclass(frozen=True)
class Score:
    total_distance_km: float
    max_route_distance_km: float
    min_route_distance_km: float
    distance_range_km: float
    total_time_hour: float
    max_route_time_hour: float
    min_route_time_hour: float
    time_range_hour: float
    penalty: float
    sort_key: tuple[float, ...]
    diagnostics: tuple[ScoreDiagnostic, ...] = ()


def score_candidate(
    solution: CandidateSolution,
    distance_matrix: DistanceMatrix,
    objective: Optional[ObjectiveSpec] = None,
) -> Score:
    spec = ObjectiveSpec() if objective is None else objective
    spec.validate()

    route_distances: list[float] = []
    route_times: list[float] = []
    diagnostics: list[ScoreDiagnostic] = []
    penalty = 0.0
    seen_nodes: dict[str, str] = {}
    duplicate_count = 0

    if spec.fixed_group_count is not None and len(solution.routes) != spec.fixed_group_count:
        penalty += spec.group_count_mismatch_penalty * abs(len(solution.routes) - spec.fixed_group_count)
        diagnostics.append(
            ScoreDiagnostic(
                code="group_count_mismatch",
                severity="warning",
                path="routes",
                message=(
                    f"Expected {spec.fixed_group_count} routes, got {len(solution.routes)}."
                ),
            )
        )

    for route_index, route in enumerate(solution.routes):
        route_path = f"routes[{route_index}]"
        visit_order = tuple(route.required_visit_order)

        if not visit_order:
            penalty += spec.empty_route_penalty
            diagnostics.append(
                ScoreDiagnostic(
                    code="empty_route",
                    severity="warning",
                    path=route_path,
                    message=f"Route {route.route_id!r} has no required visit nodes.",
                )
            )

        for node_index, node in enumerate(visit_order):
            node_path = f"{route_path}.required_visit_order[{node_index}]"
            if node in seen_nodes:
                duplicate_count += 1
                diagnostics.append(
                    ScoreDiagnostic(
                        code="duplicate_required_node",
                        severity="warning",
                        path=node_path,
                        message=f"Node {node!r} also appears in {seen_nodes[node]}.",
                    )
                )
            else:
                seen_nodes[node] = node_path

        route_distance = distance_matrix.route_path(visit_order, depot=DEPOT).distance_km
        route_time = route_distance / spec.speed_km_per_hour + _stop_time_hour(visit_order, spec)
        route_distances.append(route_distance)
        route_times.append(route_time)

        over_limit = max(0.0, route_time - spec.time_limit_hour)
        penalty += over_limit * spec.time_limit_penalty_weight

    missing_nodes = tuple(sorted(spec.required_visit_nodes - set(seen_nodes)))
    if missing_nodes:
        penalty += len(missing_nodes) * spec.missing_required_penalty
        diagnostics.append(
            ScoreDiagnostic(
                code="missing_required_nodes",
                severity="warning",
                path="required_visit_nodes",
                message=f"Missing required visit nodes: {', '.join(missing_nodes)}.",
            )
        )

    if duplicate_count:
        penalty += duplicate_count * spec.duplicate_required_penalty

    if not route_distances:
        route_distances = [0.0]
        route_times = [0.0]

    total_distance = sum(route_distances)
    max_distance = max(route_distances)
    min_distance = min(route_distances)
    total_time = sum(route_times)
    max_time = max(route_times)
    min_time = min(route_times)

    base_values = {
        "penalty": penalty,
        "total_distance_km": total_distance,
        "max_route_distance_km": max_distance,
        "distance_range_km": max_distance - min_distance,
        "total_time_hour": total_time,
        "max_route_time_hour": max_time,
        "time_range_hour": max_time - min_time,
    }
    sort_key = _sort_key(spec, base_values)

    return Score(
        total_distance_km=total_distance,
        max_route_distance_km=max_distance,
        min_route_distance_km=min_distance,
        distance_range_km=max_distance - min_distance,
        total_time_hour=total_time,
        max_route_time_hour=max_time,
        min_route_time_hour=min_time,
        time_range_hour=max_time - min_time,
        penalty=penalty,
        sort_key=sort_key,
        diagnostics=tuple(diagnostics),
    )


def _stop_time_hour(required_visit_order: Iterable[str], spec: ObjectiveSpec) -> float:
    total = 0.0
    for node in required_visit_order:
        node_type = classify_node(node)
        if node_type is NodeType.TOWN:
            total += spec.T_hour
        elif node_type is NodeType.VILLAGE:
            total += spec.t_hour
    return total


def _sort_key(spec: ObjectiveSpec, values: Mapping[str, float]) -> tuple[float, ...]:
    if spec.mode == "weighted":
        weights = {
            "penalty": 1.0,
            "total_distance_km": 1.0,
            "max_route_time_hour": 1.0,
            "time_range_hour": 1.0,
            "distance_range_km": 1.0,
            **dict(spec.weights),
        }
        weighted_value = sum(values[name] * weights.get(name, 0.0) for name in values)
        return (weighted_value,)

    return (
        values["penalty"],
        values["max_route_time_hour"],
        values["time_range_hour"],
        values["total_distance_km"],
        values["distance_range_km"],
    )
