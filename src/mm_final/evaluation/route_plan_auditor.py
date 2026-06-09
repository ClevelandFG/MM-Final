"""B3 路线方案可行性审计器。"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Literal, Optional, Union

from mm_final.contracts import (
    AUXILIARY_NODES,
    DEPOT,
    REQUIRED_VISIT_NODES,
    SCHEMA_VERSION,
    AuditResult,
    Diagnostic,
    RoutePlan,
    ValidationResult,
    load_route_plan_json,
)
from mm_final.evaluation.route_plan_evaluator import EvaluationParameters, evaluate_route_plan
from mm_final.network import RoadNetwork


AuditMode = Literal["candidate", "final"]

_CANDIDATE_DOWNGRADED_CODES = {
    "missing_required_nodes",
    "duplicate_required_node",
    "empty_route",
    "route_distance_mismatch",
    "route_metric_mismatch",
    "plan_metric_mismatch",
}
_COVERAGE_CODES = {"missing_required_nodes", "duplicate_required_node"}
_ROUTE_CODES = {
    "invalid_depot",
    "depot_in_required_visit_order",
    "auxiliary_in_required_visit_order",
    "unknown_required_visit_node",
    "invalid_expanded_path",
    "expanded_path_edge_missing",
    "duplicate_route_id",
    "empty_route",
}
_METRIC_CODES = {
    "invalid_parameter",
    "evaluation_failed",
    "route_distance_mismatch",
    "route_metric_mismatch",
    "plan_metric_mismatch",
}
_SCHEMA_CODES = {"invalid_schema_version"}


def audit_route_plan(
    plan: RoutePlan,
    road_network: RoadNetwork,
    parameters: Optional[EvaluationParameters] = None,
    *,
    mode: AuditMode = "final",
) -> AuditResult:
    """审计已通过 B0 读取的路线方案。"""

    _validate_mode(mode)
    pre_diagnostics = list(_plan_diagnostics(plan))

    try:
        evaluation = evaluate_route_plan(plan, road_network, parameters)
        diagnostics = pre_diagnostics + list(evaluation.diagnostics)
        recomputed_metrics = evaluation.plan_metrics
    except Exception as exc:  # pragma: no cover - 具体异常由底层图实现决定
        diagnostics = pre_diagnostics + [
            Diagnostic(
                severity="error",
                code="evaluation_failed",
                path="$",
                message=f"RoutePlan evaluation failed: {exc}",
            )
        ]
        recomputed_metrics = None

    errors, warnings = _classify_diagnostics(diagnostics, mode)
    if mode == "candidate":
        warnings.insert(0, "candidate audit: this result is not a final legality proof.")

    invalid_codes = _invalid_codes(diagnostics, mode)
    schema_valid = not (invalid_codes & _SCHEMA_CODES)
    coverage_valid = not (invalid_codes & _COVERAGE_CODES)
    route_valid = not (invalid_codes & _ROUTE_CODES)
    metric_valid = not (invalid_codes & _METRIC_CODES)

    return AuditResult(
        plan_id=plan.plan_id,
        schema_valid=schema_valid,
        coverage_valid=coverage_valid,
        route_valid=route_valid,
        metric_valid=metric_valid,
        errors=errors,
        warnings=warnings,
        recomputed_metrics=recomputed_metrics,
    )


def audit_validation_result(
    validation_result: ValidationResult,
    road_network: RoadNetwork,
    parameters: Optional[EvaluationParameters] = None,
    *,
    mode: AuditMode = "final",
    plan_id: str = "invalid-route-plan",
) -> AuditResult:
    """将 B0 读取结果转换为 B3 审计结果。"""

    _validate_mode(mode)
    if validation_result.plan is None:
        errors, warnings = _classify_diagnostics(validation_result.diagnostics, mode)
        return AuditResult(
            plan_id=plan_id,
            schema_valid=False,
            coverage_valid=False,
            route_valid=False,
            metric_valid=False,
            errors=errors,
            warnings=warnings,
            recomputed_metrics=None,
        )

    result = audit_route_plan(validation_result.plan, road_network, parameters, mode=mode)
    if not validation_result.warnings:
        return result

    warnings = result.warnings + [diagnostic.to_text() for diagnostic in validation_result.warnings]
    return replace(result, warnings=warnings)


def audit_route_plan_json(
    path: Union[str, Path],
    road_network: RoadNetwork,
    parameters: Optional[EvaluationParameters] = None,
    *,
    mode: AuditMode = "final",
) -> AuditResult:
    """读取 JSON 路线方案并返回文件级审计结果。"""

    route_plan_path = Path(path)
    validation_result = load_route_plan_json(route_plan_path)
    return audit_validation_result(
        validation_result,
        road_network,
        parameters,
        mode=mode,
        plan_id=validation_result.plan.plan_id if validation_result.plan is not None else route_plan_path.stem,
    )


def audit_result_to_markdown(result: AuditResult, *, mode: AuditMode = "final") -> str:
    """将结构化审计结果渲染为人工阅读用 Markdown 摘要。"""

    _validate_mode(mode)
    mode_note = (
        "candidate audit is not a final legality proof."
        if mode == "candidate"
        else "final audit is intended for result discussion."
    )
    lines = [
        "# RoutePlan Audit Summary",
        "",
        f"- plan_id: {result.plan_id}",
        f"- mode: {mode}",
        f"- note: {mode_note}",
        f"- schema_valid: {result.schema_valid}",
        f"- coverage_valid: {result.coverage_valid}",
        f"- route_valid: {result.route_valid}",
        f"- metric_valid: {result.metric_valid}",
    ]

    if result.recomputed_metrics is not None:
        metrics = result.recomputed_metrics
        lines.extend(
            [
                "",
                "## Recomputed Metrics",
                "",
                f"- group_count: {metrics.group_count}",
                f"- total_distance_km: {metrics.total_distance_km}",
                f"- completion_time_hour: {metrics.completion_time_hour}",
                f"- is_within_time_limit: {metrics.is_within_time_limit}",
            ]
        )

    lines.extend(["", "## Errors", ""])
    if result.errors:
        lines.extend(f"- {error}" for error in result.errors)
    else:
        lines.append("- none")

    lines.extend(["", "## Warnings", ""])
    if result.warnings:
        lines.extend(f"- {warning}" for warning in result.warnings)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def _plan_diagnostics(plan: RoutePlan) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    if plan.schema_version != SCHEMA_VERSION:
        diagnostics.append(
            _error(
                "$.schema_version",
                "invalid_schema_version",
                f"schema_version must be {SCHEMA_VERSION!r}.",
            )
        )

    seen_route_ids: dict[str, int] = {}
    for index, route in enumerate(plan.routes):
        route_path = f"$.routes[{index}]"
        if route.route_id in seen_route_ids:
            diagnostics.append(
                _error(
                    f"{route_path}.route_id",
                    "duplicate_route_id",
                    f"Route id {route.route_id!r} duplicates $.routes[{seen_route_ids[route.route_id]}].route_id.",
                )
            )
        else:
            seen_route_ids[route.route_id] = index

        if route.depot != DEPOT:
            diagnostics.append(_error(f"{route_path}.depot", "invalid_depot", "depot must be 'O'."))
        diagnostics.extend(_required_visit_order_diagnostics(route.required_visit_order, route_path))
        diagnostics.extend(_expanded_path_diagnostics(route.expanded_node_path, route_path))

    return tuple(diagnostics)


def _required_visit_order_diagnostics(nodes: list[str], route_path: str) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for index, node in enumerate(nodes):
        node_path = f"{route_path}.required_visit_order[{index}]"
        if node == DEPOT:
            diagnostics.append(
                _error(
                    node_path,
                    "depot_in_required_visit_order",
                    "'O' must not appear in required_visit_order.",
                )
            )
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
    return tuple(diagnostics)


def _expanded_path_diagnostics(nodes: Optional[list[str]], route_path: str) -> tuple[Diagnostic, ...]:
    if nodes is None:
        return ()
    if not nodes or nodes[0] != DEPOT or nodes[-1] != DEPOT:
        return (
            _error(
                f"{route_path}.expanded_node_path",
                "invalid_expanded_path",
                "expanded_node_path must start and end with 'O' when provided.",
            ),
        )
    return ()


def _classify_diagnostics(diagnostics: list[Diagnostic], mode: AuditMode) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for diagnostic in diagnostics:
        if _is_error(diagnostic, mode):
            errors.append(diagnostic.to_text())
        else:
            warnings.append(diagnostic.to_text())
    return errors, warnings


def _invalid_codes(diagnostics: list[Diagnostic], mode: AuditMode) -> set[str]:
    return {diagnostic.code for diagnostic in diagnostics if _is_error(diagnostic, mode)}


def _is_error(diagnostic: Diagnostic, mode: AuditMode) -> bool:
    if mode == "candidate" and diagnostic.code in _CANDIDATE_DOWNGRADED_CODES:
        return False
    if mode == "final" and diagnostic.code in _CANDIDATE_DOWNGRADED_CODES:
        return True
    return diagnostic.severity == "error"


def _validate_mode(mode: AuditMode) -> None:
    if mode not in {"candidate", "final"}:
        raise ValueError("mode must be 'candidate' or 'final'.")


def _error(path: str, code: str, message: str) -> Diagnostic:
    return Diagnostic(severity="error", code=code, path=path, message=message)
