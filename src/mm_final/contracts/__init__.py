"""路线方案契约模型。"""

from mm_final.contracts.route_plan import (
    AUXILIARY_NODES,
    DEPOT,
    REQUIRED_VISIT_NODES,
    SCHEMA_VERSION,
    TOWN_NODES,
    VILLAGE_NODES,
    AuditResult,
    Diagnostic,
    PlanMetrics,
    Route,
    RouteMetrics,
    RoutePlan,
    ValidationResult,
    load_route_plan_json,
    validate_route_plan_dict,
)

__all__ = [
    "AUXILIARY_NODES",
    "DEPOT",
    "REQUIRED_VISIT_NODES",
    "SCHEMA_VERSION",
    "TOWN_NODES",
    "VILLAGE_NODES",
    "AuditResult",
    "Diagnostic",
    "PlanMetrics",
    "Route",
    "RouteMetrics",
    "RoutePlan",
    "ValidationResult",
    "load_route_plan_json",
    "validate_route_plan_dict",
]
