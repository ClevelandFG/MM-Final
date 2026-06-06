"""RoutePlan 契约数据模型与 B0 读取校验。

B0 只负责字段结构和基础节点语义校验，不复算距离、耗时或指标。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
from typing import Any, Mapping, Optional, Union

from mm_final.network.nodes import (
    AUXILIARY_NODES,
    DEPOT,
    REQUIRED_VISIT_NODES,
    TOWN_NODES,
    VILLAGE_NODES,
)

SCHEMA_VERSION = "route-plan-v1"


@dataclass(frozen=True)
class Diagnostic:
    """契约读取诊断，最终可转换为 AuditResult 的字符串错误或警告。"""

    severity: str
    code: str
    path: str
    message: str

    def to_text(self) -> str:
        return f"{self.code} at {self.path}: {self.message}"


@dataclass(frozen=True)
class RouteMetrics:
    distance_km: float
    travel_time_hour: float
    town_stop_time_hour: float
    village_stop_time_hour: float
    total_stop_time_hour: float
    total_time_hour: float


@dataclass(frozen=True)
class PlanMetrics:
    group_count: int
    total_distance_km: float
    max_route_distance_km: float
    min_route_distance_km: float
    distance_range_km: float
    completion_time_hour: float
    max_route_time_hour: float
    time_range_hour: float
    is_within_time_limit: bool


@dataclass(frozen=True)
class Route:
    route_id: str
    depot: str
    required_visit_order: list[str]
    expanded_node_path: Optional[list[str]]
    distance_km: Optional[float]
    metrics: Optional[Mapping[str, Any]]
    extra_fields: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RoutePlan:
    schema_version: str
    plan_id: str
    source: str
    parameters: Mapping[str, Any]
    routes: list[Route]
    metrics: Optional[Mapping[str, Any]]
    extra_fields: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditResult:
    plan_id: str
    schema_valid: bool
    coverage_valid: bool
    route_valid: bool
    metric_valid: bool
    errors: list[str]
    warnings: list[str]
    recomputed_metrics: Optional[PlanMetrics]


@dataclass(frozen=True)
class ValidationResult:
    plan: Optional[RoutePlan]
    diagnostics: list[Diagnostic]

    @property
    def errors(self) -> list[Diagnostic]:
        return [item for item in self.diagnostics if item.severity == "error"]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [item for item in self.diagnostics if item.severity == "warning"]

    @property
    def is_valid(self) -> bool:
        return not self.errors and self.plan is not None


PLAN_FIELDS = {
    "schema_version",
    "plan_id",
    "source",
    "parameters",
    "routes",
    "metrics",
}
ROUTE_FIELDS = {
    "route_id",
    "depot",
    "required_visit_order",
    "expanded_node_path",
    "distance_km",
    "metrics",
}


def load_route_plan_json(path: Union[str, Path]) -> ValidationResult:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return validate_route_plan_dict(data)


def validate_route_plan_dict(data: Any) -> ValidationResult:
    diagnostics: list[Diagnostic] = []

    if not isinstance(data, Mapping):
        diagnostics.append(_error("$", "type_error", "RoutePlan root must be an object."))
        return ValidationResult(plan=None, diagnostics=diagnostics)

    _diagnose_fields(data, PLAN_FIELDS, "$", diagnostics)

    if data.get("schema_version") != SCHEMA_VERSION:
        diagnostics.append(
            _error(
                "$.schema_version",
                "invalid_schema_version",
                f"schema_version must be {SCHEMA_VERSION!r}.",
            )
        )

    if "parameters" in data and not isinstance(data["parameters"], Mapping):
        diagnostics.append(_error("$.parameters", "type_error", "parameters must be an object."))

    raw_routes = data.get("routes")
    routes: list[Route] = []
    if not isinstance(raw_routes, list):
        diagnostics.append(_error("$.routes", "type_error", "routes must be a list."))
    else:
        for index, raw_route in enumerate(raw_routes):
            route = _parse_route(raw_route, f"$.routes[{index}]", diagnostics)
            if route is not None:
                routes.append(route)

    plan: Optional[RoutePlan] = None
    if not [item for item in diagnostics if item.severity == "error"]:
        plan = RoutePlan(
            schema_version=str(data["schema_version"]),
            plan_id=str(data["plan_id"]),
            source=str(data["source"]),
            parameters=data["parameters"],
            routes=routes,
            metrics=data["metrics"],
            extra_fields={key: data[key] for key in data.keys() - PLAN_FIELDS},
        )

    return ValidationResult(plan=plan, diagnostics=diagnostics)


def _parse_route(
    data: Any,
    path: str,
    diagnostics: list[Diagnostic],
) -> Optional[Route]:
    if not isinstance(data, Mapping):
        diagnostics.append(_error(path, "type_error", "Route must be an object."))
        return None

    _diagnose_fields(data, ROUTE_FIELDS, path, diagnostics)

    if data.get("depot") != DEPOT:
        diagnostics.append(_error(f"{path}.depot", "invalid_depot", "depot must be 'O'."))

    required_visit_order = data.get("required_visit_order")
    if not isinstance(required_visit_order, list):
        diagnostics.append(
            _error(
                f"{path}.required_visit_order",
                "type_error",
                "required_visit_order must be a list.",
            )
        )
        required_visit_order = []
    else:
        _validate_required_visit_order(required_visit_order, path, diagnostics)

    expanded_node_path = data.get("expanded_node_path")
    if expanded_node_path is not None:
        if not isinstance(expanded_node_path, list):
            diagnostics.append(
                _error(f"{path}.expanded_node_path", "type_error", "expanded_node_path must be null or a list.")
            )
        elif expanded_node_path and (expanded_node_path[0] != DEPOT or expanded_node_path[-1] != DEPOT):
            diagnostics.append(
                _error(
                    f"{path}.expanded_node_path",
                    "invalid_expanded_path",
                    "expanded_node_path must start and end with 'O' when provided.",
                )
            )

    if "distance_km" in data and data["distance_km"] is not None and not _is_number(data["distance_km"]):
        diagnostics.append(_error(f"{path}.distance_km", "type_error", "distance_km must be null or a number."))

    if "metrics" in data and data["metrics"] is not None and not isinstance(data["metrics"], Mapping):
        diagnostics.append(_error(f"{path}.metrics", "type_error", "metrics must be null or an object."))

    if [item for item in diagnostics if item.severity == "error"]:
        return None

    return Route(
        route_id=str(data["route_id"]),
        depot=str(data["depot"]),
        required_visit_order=list(required_visit_order),
        expanded_node_path=None if expanded_node_path is None else list(expanded_node_path),
        distance_km=None if data["distance_km"] is None else float(data["distance_km"]),
        metrics=data["metrics"],
        extra_fields={key: data[key] for key in data.keys() - ROUTE_FIELDS},
    )


def _validate_required_visit_order(
    values: list[Any],
    route_path: str,
    diagnostics: list[Diagnostic],
) -> None:
    for index, node in enumerate(values):
        node_path = f"{route_path}.required_visit_order[{index}]"
        if not isinstance(node, str):
            diagnostics.append(_error(node_path, "type_error", "required visit node must be a string."))
            continue
        if node == DEPOT:
            diagnostics.append(_error(node_path, "depot_in_required_visit_order", "'O' must not appear in required_visit_order."))
        elif node in AUXILIARY_NODES:
            diagnostics.append(
                _error(
                    node_path,
                    "auxiliary_in_required_visit_order",
                    f"Auxiliary node {node!r} must not appear in required_visit_order.",
                )
            )
        elif node not in REQUIRED_VISIT_NODES:
            diagnostics.append(
                _error(
                    node_path,
                    "unknown_required_visit_node",
                    f"Unknown required visit node {node!r}.",
                )
            )


def _diagnose_fields(
    data: Mapping[str, Any],
    allowed_fields: set[str],
    path: str,
    diagnostics: list[Diagnostic],
) -> None:
    for field_name in sorted(allowed_fields - data.keys()):
        diagnostics.append(_error(f"{path}.{field_name}", "missing_field", f"Missing required field {field_name!r}."))

    for field_name in sorted(data.keys() - allowed_fields):
        diagnostics.append(
            Diagnostic(
                severity="warning",
                code="unknown_field",
                path=f"{path}.{field_name}",
                message=f"Unknown field {field_name!r} is preserved but not interpreted in B0.",
            )
        )


def _error(path: str, code: str, message: str) -> Diagnostic:
    return Diagnostic(severity="error", code=code, path=path, message=message)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
