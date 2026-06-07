"""CandidateSolution 到 RoutePlan 契约的导出。"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from mm_final.contracts import DEPOT, SCHEMA_VERSION, Route, RoutePlan
from mm_final.routing.candidate import CandidateSolution
from mm_final.routing.distance_matrix import DistanceMatrix


def candidate_to_route_plan(
    solution: CandidateSolution,
    *,
    plan_id: str,
    source: Optional[str] = None,
    parameters: Optional[Mapping[str, Any]] = None,
    distance_matrix: Optional[DistanceMatrix] = None,
    include_expanded_paths: bool = False,
) -> RoutePlan:
    route_plan_parameters = dict(solution.parameters)
    if parameters:
        route_plan_parameters.update(parameters)
    if solution.seed is not None:
        route_plan_parameters.setdefault("seed", solution.seed)
    if solution.runtime_seconds is not None:
        route_plan_parameters.setdefault("runtime_seconds", solution.runtime_seconds)

    routes = []
    for candidate_route in solution.routes:
        expanded_node_path = None
        distance_km = None
        if include_expanded_paths:
            if distance_matrix is None:
                raise ValueError("distance_matrix is required when include_expanded_paths=True.")
            route_path = distance_matrix.route_path(candidate_route.required_visit_order, depot=DEPOT)
            expanded_node_path = list(route_path.expanded_node_path)
            distance_km = route_path.distance_km

        routes.append(
            Route(
                route_id=candidate_route.route_id,
                depot=DEPOT,
                required_visit_order=list(candidate_route.required_visit_order),
                expanded_node_path=expanded_node_path,
                distance_km=distance_km,
                metrics=None,
            )
        )

    return RoutePlan(
        schema_version=SCHEMA_VERSION,
        plan_id=plan_id,
        source=solution.method if source is None else source,
        parameters=route_plan_parameters,
        routes=routes,
        metrics=None,
    )
