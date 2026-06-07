"""B2 路线方案评价器。

评价器只复算指标并给出结构化诊断；最终合法性结论留给 B3 审计器。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional

from mm_final.contracts import Diagnostic, PlanMetrics, Route, RouteMetrics, RoutePlan
from mm_final.network import DEPOT, REQUIRED_VISIT_NODES, NodeType, RoadNetwork, classify_node
from mm_final.routing import DistanceMatrix


DISTANCE_TOLERANCE_KM = 1e-6
TIME_TOLERANCE_HOUR = 1e-6


@dataclass(frozen=True)
class EvaluationParameters:
    T_hour: float = 2.0
    t_hour: float = 1.0
    speed_km_per_hour: float = 35.0
    time_limit_hour: float = 24.0
    required_visit_nodes: frozenset[str] = frozenset(REQUIRED_VISIT_NODES)
    distance_tolerance_km: float = DISTANCE_TOLERANCE_KM
    time_tolerance_hour: float = TIME_TOLERANCE_HOUR

    @classmethod
    def from_route_plan(cls, plan: RoutePlan) -> "EvaluationParameters":
        raw = plan.parameters
        return cls(
            T_hour=float(raw.get("T_hour", cls.T_hour)),
            t_hour=float(raw.get("t_hour", cls.t_hour)),
            speed_km_per_hour=float(raw.get("speed_km_per_hour", cls.speed_km_per_hour)),
            time_limit_hour=float(raw.get("time_limit_hour", cls.time_limit_hour)),
        )

    def diagnostics(self) -> tuple[Diagnostic, ...]:
        diagnostics: list[Diagnostic] = []
        if self.T_hour < 0:
            diagnostics.append(_error("$.parameters.T_hour", "invalid_parameter", "T_hour must be >= 0."))
        if self.t_hour < 0:
            diagnostics.append(_error("$.parameters.t_hour", "invalid_parameter", "t_hour must be >= 0."))
        if self.speed_km_per_hour <= 0:
            diagnostics.append(
                _error("$.parameters.speed_km_per_hour", "invalid_parameter", "speed_km_per_hour must be > 0.")
            )
        if self.time_limit_hour <= 0:
            diagnostics.append(
                _error("$.parameters.time_limit_hour", "invalid_parameter", "time_limit_hour must be > 0.")
            )
        return tuple(diagnostics)


@dataclass(frozen=True)
class CoverageSummary:
    covered: tuple[str, ...]
    missing: tuple[str, ...]
    duplicated: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class DistanceBalanceSummary:
    longest_route_ids: tuple[str, ...]
    shortest_route_ids: tuple[str, ...]


@dataclass(frozen=True)
class EvaluationResult:
    plan_id: str
    route_metrics_by_id: Mapping[str, RouteMetrics]
    plan_metrics: Optional[PlanMetrics]
    diagnostics: tuple[Diagnostic, ...]
    expanded_paths_by_route_id: Mapping[str, tuple[str, ...]]
    coverage_summary: CoverageSummary
    bottleneck_route_ids: tuple[str, ...]
    distance_balance: DistanceBalanceSummary
    time_breakdown_by_route_id: Mapping[str, RouteMetrics]

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "route_metrics_by_id": {
                route_id: asdict(metrics) for route_id, metrics in self.route_metrics_by_id.items()
            },
            "plan_metrics": None if self.plan_metrics is None else asdict(self.plan_metrics),
            "diagnostics": [asdict(diagnostic) for diagnostic in self.diagnostics],
            "expanded_paths_by_route_id": {
                route_id: list(path) for route_id, path in self.expanded_paths_by_route_id.items()
            },
            "coverage_summary": {
                "covered": list(self.coverage_summary.covered),
                "missing": list(self.coverage_summary.missing),
                "duplicated": {
                    node: list(route_ids) for node, route_ids in self.coverage_summary.duplicated.items()
                },
            },
            "bottleneck_route_ids": list(self.bottleneck_route_ids),
            "distance_balance": {
                "longest_route_ids": list(self.distance_balance.longest_route_ids),
                "shortest_route_ids": list(self.distance_balance.shortest_route_ids),
            },
            "time_breakdown_by_route_id": {
                route_id: asdict(metrics) for route_id, metrics in self.time_breakdown_by_route_id.items()
            },
        }


def evaluate_route_plan(
    plan: RoutePlan,
    road_network: RoadNetwork,
    parameters: Optional[EvaluationParameters] = None,
) -> EvaluationResult:
    params = EvaluationParameters.from_route_plan(plan) if parameters is None else parameters
    diagnostics = list(params.diagnostics())
    if diagnostics:
        return _empty_result(plan.plan_id, tuple(diagnostics))

    matrix_nodes = params.required_visit_nodes | {
        node for route in plan.routes for node in route.required_visit_order
    }
    distance_matrix = DistanceMatrix.from_network(road_network, nodes=matrix_nodes)

    route_metrics_by_id: dict[str, RouteMetrics] = {}
    expanded_paths_by_route_id: dict[str, tuple[str, ...]] = {}
    visits_by_node: dict[str, list[str]] = {}

    for route_index, route in enumerate(plan.routes):
        route_path = f"$.routes[{route_index}]"
        metrics, expanded_path = _evaluate_route(route, distance_matrix, params)
        route_metrics_by_id[route.route_id] = metrics
        expanded_paths_by_route_id[route.route_id] = expanded_path

        if not route.required_visit_order:
            diagnostics.append(
                _warning(route_path, "empty_route", f"Route {route.route_id!r} has no required visit nodes.")
            )

        for node in route.required_visit_order:
            visits_by_node.setdefault(node, []).append(route.route_id)

        _compare_route_distance(route, metrics, route_path, params, diagnostics)
        _compare_route_metrics(route, metrics, route_path, params, diagnostics)
        _check_expanded_path(route, road_network, expanded_path, route_path, diagnostics)

    coverage_summary = _coverage_summary(visits_by_node, params.required_visit_nodes)
    _diagnose_coverage(coverage_summary, diagnostics)
    plan_metrics = _plan_metrics(route_metrics_by_id, params)
    _compare_plan_metrics(plan, plan_metrics, params, diagnostics)

    bottleneck_route_ids = _route_ids_with_value(
        route_metrics_by_id,
        lambda metrics: metrics.total_time_hour,
        plan_metrics.max_route_time_hour,
        params.time_tolerance_hour,
    )
    longest_route_ids = _route_ids_with_value(
        route_metrics_by_id,
        lambda metrics: metrics.distance_km,
        plan_metrics.max_route_distance_km,
        params.distance_tolerance_km,
    )
    shortest_route_ids = _route_ids_with_value(
        route_metrics_by_id,
        lambda metrics: metrics.distance_km,
        plan_metrics.min_route_distance_km,
        params.distance_tolerance_km,
    )

    return EvaluationResult(
        plan_id=plan.plan_id,
        route_metrics_by_id=route_metrics_by_id,
        plan_metrics=plan_metrics,
        diagnostics=tuple(diagnostics),
        expanded_paths_by_route_id=expanded_paths_by_route_id,
        coverage_summary=coverage_summary,
        bottleneck_route_ids=bottleneck_route_ids,
        distance_balance=DistanceBalanceSummary(
            longest_route_ids=longest_route_ids,
            shortest_route_ids=shortest_route_ids,
        ),
        time_breakdown_by_route_id=route_metrics_by_id,
    )


def _evaluate_route(
    route: Route,
    distance_matrix: DistanceMatrix,
    params: EvaluationParameters,
) -> tuple[RouteMetrics, tuple[str, ...]]:
    route_path = distance_matrix.route_path(route.required_visit_order, depot=DEPOT)
    travel_time = route_path.distance_km / params.speed_km_per_hour
    town_stop_time, village_stop_time = _stop_times(route.required_visit_order, params)
    total_stop_time = town_stop_time + village_stop_time
    metrics = RouteMetrics(
        distance_km=route_path.distance_km,
        travel_time_hour=travel_time,
        town_stop_time_hour=town_stop_time,
        village_stop_time_hour=village_stop_time,
        total_stop_time_hour=total_stop_time,
        total_time_hour=travel_time + total_stop_time,
    )
    return metrics, route_path.expanded_node_path


def _stop_times(route: list[str], params: EvaluationParameters) -> tuple[float, float]:
    town_stop_time = 0.0
    village_stop_time = 0.0
    for node in route:
        node_type = classify_node(node)
        if node_type is NodeType.TOWN:
            town_stop_time += params.T_hour
        elif node_type is NodeType.VILLAGE:
            village_stop_time += params.t_hour
    return town_stop_time, village_stop_time


def _plan_metrics(
    route_metrics_by_id: Mapping[str, RouteMetrics],
    params: EvaluationParameters,
) -> PlanMetrics:
    distances = [metrics.distance_km for metrics in route_metrics_by_id.values()]
    times = [metrics.total_time_hour for metrics in route_metrics_by_id.values()]
    if not distances:
        distances = [0.0]
        times = [0.0]

    max_distance = max(distances)
    min_distance = min(distances)
    max_time = max(times)
    min_time = min(times)
    return PlanMetrics(
        group_count=len(route_metrics_by_id),
        total_distance_km=sum(distances),
        max_route_distance_km=max_distance,
        min_route_distance_km=min_distance,
        distance_range_km=max_distance - min_distance,
        completion_time_hour=max_time,
        max_route_time_hour=max_time,
        time_range_hour=max_time - min_time,
        is_within_time_limit=max_time <= params.time_limit_hour,
    )


def _compare_route_distance(
    route: Route,
    metrics: RouteMetrics,
    route_path: str,
    params: EvaluationParameters,
    diagnostics: list[Diagnostic],
) -> None:
    if route.distance_km is None:
        return
    if abs(route.distance_km - metrics.distance_km) > params.distance_tolerance_km:
        diagnostics.append(
            _warning(
                f"{route_path}.distance_km",
                "route_distance_mismatch",
                f"Provided distance {route.distance_km} differs from recomputed {metrics.distance_km}.",
            )
        )


def _compare_route_metrics(
    route: Route,
    metrics: RouteMetrics,
    route_path: str,
    params: EvaluationParameters,
    diagnostics: list[Diagnostic],
) -> None:
    if route.metrics is None:
        return
    _compare_metric_mapping(
        route.metrics,
        asdict(metrics),
        route_path + ".metrics",
        params,
        diagnostics,
        code="route_metric_mismatch",
    )


def _compare_plan_metrics(
    plan: RoutePlan,
    metrics: PlanMetrics,
    params: EvaluationParameters,
    diagnostics: list[Diagnostic],
) -> None:
    if plan.metrics is None:
        return
    _compare_metric_mapping(
        plan.metrics,
        asdict(metrics),
        "$.metrics",
        params,
        diagnostics,
        code="plan_metric_mismatch",
    )


def _compare_metric_mapping(
    provided: Mapping[str, Any],
    recomputed: Mapping[str, Any],
    path: str,
    params: EvaluationParameters,
    diagnostics: list[Diagnostic],
    *,
    code: str,
) -> None:
    for field_name, recomputed_value in recomputed.items():
        if field_name not in provided or provided[field_name] is None:
            continue
        provided_value = provided[field_name]
        tolerance = params.time_tolerance_hour
        if field_name.endswith("_km"):
            tolerance = params.distance_tolerance_km
        if isinstance(recomputed_value, bool):
            mismatch = bool(provided_value) != recomputed_value
        elif isinstance(recomputed_value, int):
            mismatch = int(provided_value) != recomputed_value
        else:
            mismatch = abs(float(provided_value) - float(recomputed_value)) > tolerance
        if mismatch:
            diagnostics.append(
                _warning(
                    f"{path}.{field_name}",
                    code,
                    f"Provided {provided_value!r} differs from recomputed {recomputed_value!r}.",
                )
            )


def _check_expanded_path(
    route: Route,
    road_network: RoadNetwork,
    recomputed_path: tuple[str, ...],
    route_path: str,
    diagnostics: list[Diagnostic],
) -> None:
    if route.expanded_node_path is None:
        return

    provided_path = tuple(route.expanded_node_path)
    for index, (source, target) in enumerate(zip(provided_path, provided_path[1:])):
        if not road_network.has_edge(source, target):
            diagnostics.append(
                _error(
                    f"{route_path}.expanded_node_path[{index}:{index + 2}]",
                    "expanded_path_edge_missing",
                    f"Expanded path edge {source!r}-{target!r} does not exist in road network.",
                )
            )

    if provided_path != recomputed_path:
        diagnostics.append(
            _warning(
                f"{route_path}.expanded_node_path",
                "expanded_path_mismatch",
                "Provided expanded_node_path differs from shortest-path expansion.",
            )
        )


def _coverage_summary(
    visits_by_node: Mapping[str, list[str]],
    required_visit_nodes: frozenset[str],
) -> CoverageSummary:
    covered = tuple(sorted(required_visit_nodes & set(visits_by_node)))
    missing = tuple(sorted(required_visit_nodes - set(visits_by_node)))
    duplicated = {
        node: tuple(route_ids)
        for node, route_ids in sorted(visits_by_node.items())
        if node in required_visit_nodes and len(route_ids) > 1
    }
    return CoverageSummary(covered=covered, missing=missing, duplicated=duplicated)


def _diagnose_coverage(summary: CoverageSummary, diagnostics: list[Diagnostic]) -> None:
    if summary.missing:
        diagnostics.append(
            _warning(
                "$.routes",
                "missing_required_nodes",
                f"Missing required visit nodes: {', '.join(summary.missing)}.",
            )
        )
    for node, route_ids in summary.duplicated.items():
        diagnostics.append(
            _warning(
                "$.routes",
                "duplicate_required_node",
                f"Required node {node!r} appears in routes: {', '.join(route_ids)}.",
            )
        )


def _route_ids_with_value(
    route_metrics_by_id: Mapping[str, RouteMetrics],
    getter,
    target_value: float,
    tolerance: float,
) -> tuple[str, ...]:
    return tuple(
        route_id
        for route_id, metrics in route_metrics_by_id.items()
        if abs(getter(metrics) - target_value) <= tolerance
    )


def _empty_result(plan_id: str, diagnostics: tuple[Diagnostic, ...]) -> EvaluationResult:
    return EvaluationResult(
        plan_id=plan_id,
        route_metrics_by_id={},
        plan_metrics=None,
        diagnostics=diagnostics,
        expanded_paths_by_route_id={},
        coverage_summary=CoverageSummary(covered=(), missing=(), duplicated={}),
        bottleneck_route_ids=(),
        distance_balance=DistanceBalanceSummary(longest_route_ids=(), shortest_route_ids=()),
        time_breakdown_by_route_id={},
    )


def _warning(path: str, code: str, message: str) -> Diagnostic:
    return Diagnostic(severity="warning", code=code, path=path, message=message)


def _error(path: str, code: str, message: str) -> Diagnostic:
    return Diagnostic(severity="error", code=code, path=path, message=message)
