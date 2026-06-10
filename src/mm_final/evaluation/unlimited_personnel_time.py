"""B6 人员足够时的最短完成时间分析。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Literal, Optional, Union

from mm_final.contracts import (
    DEPOT,
    REQUIRED_VISIT_NODES,
    SCHEMA_VERSION,
    AuditResult,
    Route,
    RoutePlan,
    load_route_plan_json,
)
from mm_final.evaluation.lower_bounds import LowerBoundParameters, LowerBoundReport, compute_lower_bound_report
from mm_final.evaluation.route_plan_auditor import audit_route_plan
from mm_final.evaluation.route_plan_evaluator import EvaluationParameters
from mm_final.network import RoadNetwork


ShortestTimeCandidateStatus = Literal[
    "optimal_time_candidate",
    "valid_slower_candidate",
    "candidate_invalid",
    "parse_failed",
    "singleton_certificate",
]
UnlimitedPersonnelConclusionStatus = Literal[
    "proven_shortest_time",
    "incumbent_shortest_time",
    "no_valid_candidate",
]


@dataclass(frozen=True)
class UnlimitedPersonnelParameters:
    """B6 统一分析参数；24 小时只作为审计指标，不作为 B6 门禁。"""

    T_hour: float = 2.0
    t_hour: float = 1.0
    speed_km_per_hour: float = 35.0
    time_limit_hour: float = 24.0
    required_visit_nodes: frozenset[str] = frozenset(REQUIRED_VISIT_NODES)
    distance_tolerance_km: float = 1e-6
    time_tolerance_hour: float = 1e-6

    def to_evaluation_parameters(self) -> EvaluationParameters:
        return EvaluationParameters(
            T_hour=self.T_hour,
            t_hour=self.t_hour,
            speed_km_per_hour=self.speed_km_per_hour,
            time_limit_hour=self.time_limit_hour,
            required_visit_nodes=self.required_visit_nodes,
            distance_tolerance_km=self.distance_tolerance_km,
            time_tolerance_hour=self.time_tolerance_hour,
        )

    def to_lower_bound_parameters(self) -> LowerBoundParameters:
        return LowerBoundParameters(
            T_hour=self.T_hour,
            t_hour=self.t_hour,
            speed_km_per_hour=self.speed_km_per_hour,
            time_limit_hour=self.time_limit_hour,
            required_visit_nodes=self.required_visit_nodes,
            time_tolerance_hour=self.time_tolerance_hour,
        )

    def to_route_plan_parameters(self) -> dict[str, float]:
        return {
            "T_hour": self.T_hour,
            "t_hour": self.t_hour,
            "speed_km_per_hour": self.speed_km_per_hour,
            "time_limit_hour": self.time_limit_hour,
        }


@dataclass(frozen=True)
class ShortestTimeCandidateRecord:
    candidate_index: int
    plan_id: str
    status: ShortestTimeCandidateStatus
    is_final_valid: bool
    is_optimal_time: bool
    group_count: Optional[int]
    is_within_time_limit: Optional[bool]
    completion_time_hour: Optional[float]
    total_distance_km: Optional[float]
    time_range_hour: Optional[float]
    distance_range_km: Optional[float]
    audit_result: Optional[AuditResult]
    source: str = "candidate"
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_index": self.candidate_index,
            "plan_id": self.plan_id,
            "status": self.status,
            "source": self.source,
            "is_final_valid": self.is_final_valid,
            "is_optimal_time": self.is_optimal_time,
            "group_count": self.group_count,
            "is_within_time_limit": self.is_within_time_limit,
            "completion_time_hour": self.completion_time_hour,
            "total_distance_km": self.total_distance_km,
            "time_range_hour": self.time_range_hour,
            "distance_range_km": self.distance_range_km,
            "audit_result": None if self.audit_result is None else _audit_result_to_dict(self.audit_result),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class UnlimitedPersonnelReport:
    parameters: UnlimitedPersonnelParameters
    conclusion_status: UnlimitedPersonnelConclusionStatus
    shortest_time_lower_bound_hour: float
    best_completion_time_hour: Optional[float]
    gap_hour: Optional[float]
    recommended_plan_id: Optional[str]
    recommended_candidate_index: Optional[int]
    recommended_status: Optional[str]
    candidate_records: tuple[ShortestTimeCandidateRecord, ...]
    lower_bound_report: LowerBoundReport
    singleton_plan_id: str
    bottleneck_node: Optional[str]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "parameters": _parameters_to_dict(self.parameters),
            "conclusion_status": self.conclusion_status,
            "shortest_time_lower_bound_hour": self.shortest_time_lower_bound_hour,
            "best_completion_time_hour": self.best_completion_time_hour,
            "gap_hour": self.gap_hour,
            "recommended_plan_id": self.recommended_plan_id,
            "recommended_candidate_index": self.recommended_candidate_index,
            "recommended_status": self.recommended_status,
            "candidate_records": [record.to_dict() for record in self.candidate_records],
            "lower_bound_report": self.lower_bound_report.to_dict(),
            "singleton_plan_id": self.singleton_plan_id,
            "bottleneck_node": self.bottleneck_node,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class _CandidateSource:
    plan: Optional[RoutePlan]
    plan_id: str
    source: str
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def build_singleton_certificate_plan(
    *,
    parameters: Optional[UnlimitedPersonnelParameters] = None,
    plan_id: str = "singleton-certificate",
) -> RoutePlan:
    params = UnlimitedPersonnelParameters() if parameters is None else parameters
    routes = [
        Route(
            route_id=f"R{index}",
            depot=DEPOT,
            required_visit_order=[node],
            expanded_node_path=None,
            distance_km=None,
            metrics=None,
        )
        for index, node in enumerate(sorted(params.required_visit_nodes, key=_node_sort_key), start=1)
    ]
    return RoutePlan(
        schema_version=SCHEMA_VERSION,
        plan_id=plan_id,
        source="singleton_certificate",
        parameters=params.to_route_plan_parameters(),
        routes=routes,
        metrics=None,
    )


def analyze_unlimited_personnel_time(
    road_network: RoadNetwork,
    *,
    candidate_plans: Iterable[RoutePlan] = (),
    parameters: Optional[UnlimitedPersonnelParameters] = None,
    lower_bound_report: Optional[LowerBoundReport] = None,
    singleton_plan_id: str = "singleton-certificate",
) -> UnlimitedPersonnelReport:
    sources = tuple(
        _CandidateSource(plan=plan, plan_id=plan.plan_id, source="candidate")
        for plan in candidate_plans
    )
    return _analyze_unlimited_personnel_time_from_sources(
        road_network,
        candidate_sources=sources,
        parameters=parameters,
        lower_bound_report=lower_bound_report,
        singleton_plan_id=singleton_plan_id,
    )


def analyze_unlimited_personnel_time_json_files(
    road_network: RoadNetwork,
    *,
    candidate_paths: Iterable[Union[str, Path]],
    parameters: Optional[UnlimitedPersonnelParameters] = None,
    lower_bound_report: Optional[LowerBoundReport] = None,
    singleton_plan_id: str = "singleton-certificate",
) -> UnlimitedPersonnelReport:
    sources: list[_CandidateSource] = []
    for raw_path in candidate_paths:
        path = Path(raw_path)
        try:
            validation = load_route_plan_json(path)
        except Exception as exc:
            sources.append(
                _CandidateSource(
                    plan=None,
                    plan_id=path.stem,
                    source="parse_failed",
                    errors=(f"json_load_failed: {exc}",),
                )
            )
            continue

        if validation.plan is None:
            errors = tuple(diagnostic.to_text() for diagnostic in validation.errors)
            warnings = tuple(diagnostic.to_text() for diagnostic in validation.warnings)
            sources.append(
                _CandidateSource(
                    plan=None,
                    plan_id=path.stem,
                    source="parse_failed",
                    errors=errors,
                    warnings=warnings,
                )
            )
        else:
            warnings = tuple(diagnostic.to_text() for diagnostic in validation.warnings)
            sources.append(
                _CandidateSource(
                    plan=validation.plan,
                    plan_id=validation.plan.plan_id,
                    source="candidate",
                    warnings=warnings,
                )
            )

    return _analyze_unlimited_personnel_time_from_sources(
        road_network,
        candidate_sources=tuple(sources),
        parameters=parameters,
        lower_bound_report=lower_bound_report,
        singleton_plan_id=singleton_plan_id,
    )


def unlimited_personnel_report_to_markdown(report: UnlimitedPersonnelReport) -> str:
    lines = [
        "## Unlimited Personnel Time Report",
        "",
        f"- conclusion_status: {report.conclusion_status}",
        f"- shortest_time_lower_bound_hour: {report.shortest_time_lower_bound_hour:.6g}",
        f"- best_completion_time_hour: {_format_optional_float(report.best_completion_time_hour)}",
        f"- gap_hour: {_format_optional_float(report.gap_hour)}",
        f"- recommended_plan_id: {_format_optional(report.recommended_plan_id)}",
        f"- recommended_status: {_format_optional(report.recommended_status)}",
        f"- bottleneck_node: {_format_optional(report.bottleneck_node)}",
        "",
        "### Candidate Records",
        "",
    ]
    for record in report.candidate_records:
        lines.append(
            f"- candidate[{record.candidate_index}] {record.plan_id}: {record.status}, "
            f"group_count={_format_optional(record.group_count)}, "
            f"completion_time_hour={_format_optional_float(record.completion_time_hour)}"
        )
    if report.warnings:
        lines.extend(["", "### Warnings", ""])
        lines.extend(f"- {warning}" for warning in report.warnings)
    return "\n".join(lines) + "\n"


def _analyze_unlimited_personnel_time_from_sources(
    road_network: RoadNetwork,
    *,
    candidate_sources: Iterable[_CandidateSource],
    parameters: Optional[UnlimitedPersonnelParameters],
    lower_bound_report: Optional[LowerBoundReport],
    singleton_plan_id: str,
) -> UnlimitedPersonnelReport:
    params = UnlimitedPersonnelParameters() if parameters is None else parameters
    lower_report = _lower_bound_report(road_network, params, lower_bound_report)
    lower_bound_hour = lower_report.unlimited_personnel_lower_bound_hour
    singleton_plan = build_singleton_certificate_plan(parameters=params, plan_id=singleton_plan_id)

    seen_plan_ids: set[str] = set()
    records = [
        _candidate_record(
            _CandidateSource(plan=singleton_plan, plan_id=singleton_plan.plan_id, source="singleton"),
            candidate_index=0,
            road_network=road_network,
            params=params,
            lower_bound_hour=lower_bound_hour,
            seen_plan_ids=seen_plan_ids,
        )
    ]
    records.extend(
        _candidate_record(
            source,
            candidate_index=index,
            road_network=road_network,
            params=params,
            lower_bound_hour=lower_bound_hour,
            seen_plan_ids=seen_plan_ids,
        )
        for index, source in enumerate(candidate_sources, start=1)
    )

    valid_records = [record for record in records if record.is_final_valid and record.completion_time_hour is not None]
    best_record = min(valid_records, key=_best_completion_sort_key, default=None)
    optimal_records = [record for record in valid_records if record.is_optimal_time]
    recommended_record = min(optimal_records, key=_recommendation_sort_key, default=best_record)
    best_completion = None if best_record is None else best_record.completion_time_hour
    gap = None if best_completion is None else best_completion - lower_bound_hour

    if best_record is None:
        conclusion_status: UnlimitedPersonnelConclusionStatus = "no_valid_candidate"
    elif best_completion <= lower_bound_hour + params.time_tolerance_hour:
        conclusion_status = "proven_shortest_time"
    else:
        conclusion_status = "incumbent_shortest_time"

    return UnlimitedPersonnelReport(
        parameters=params,
        conclusion_status=conclusion_status,
        shortest_time_lower_bound_hour=lower_bound_hour,
        best_completion_time_hour=best_completion,
        gap_hour=gap,
        recommended_plan_id=None if recommended_record is None else recommended_record.plan_id,
        recommended_candidate_index=None if recommended_record is None else recommended_record.candidate_index,
        recommended_status=None if recommended_record is None else recommended_record.status,
        candidate_records=tuple(records),
        lower_bound_report=lower_report,
        singleton_plan_id=singleton_plan_id,
        bottleneck_node=lower_report.max_single_node,
    )


def _candidate_record(
    source: _CandidateSource,
    *,
    candidate_index: int,
    road_network: RoadNetwork,
    params: UnlimitedPersonnelParameters,
    lower_bound_hour: float,
    seen_plan_ids: set[str],
) -> ShortestTimeCandidateRecord:
    warnings = list(source.warnings)
    errors = list(source.errors)
    if source.plan_id in seen_plan_ids:
        warnings.append(f"duplicate_plan_id: {source.plan_id}")
    seen_plan_ids.add(source.plan_id)

    if source.plan is None:
        return ShortestTimeCandidateRecord(
            candidate_index=candidate_index,
            plan_id=source.plan_id,
            status="parse_failed",
            source=source.source,
            is_final_valid=False,
            is_optimal_time=False,
            group_count=None,
            is_within_time_limit=None,
            completion_time_hour=None,
            total_distance_km=None,
            time_range_hour=None,
            distance_range_km=None,
            audit_result=None,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    warnings.extend(_parameter_warnings(source.plan, params))
    audit = audit_route_plan(source.plan, road_network, params.to_evaluation_parameters(), mode="final")
    metrics = audit.recomputed_metrics
    is_final_valid = audit.schema_valid and audit.coverage_valid and audit.route_valid and audit.metric_valid
    if metrics is None:
        is_final_valid = False

    group_count = None if metrics is None else metrics.group_count
    completion_time = None if metrics is None else metrics.completion_time_hour
    total_distance = None if metrics is None else metrics.total_distance_km
    time_range = None if metrics is None else metrics.time_range_hour
    distance_range = None if metrics is None else metrics.distance_range_km
    is_within_time_limit = None if metrics is None else metrics.is_within_time_limit
    is_optimal = (
        bool(is_final_valid)
        and completion_time is not None
        and completion_time <= lower_bound_hour + params.time_tolerance_hour
    )

    if not is_final_valid:
        status: ShortestTimeCandidateStatus = "candidate_invalid"
    elif source.source == "singleton":
        status = "singleton_certificate"
    elif is_optimal:
        status = "optimal_time_candidate"
    else:
        status = "valid_slower_candidate"

    return ShortestTimeCandidateRecord(
        candidate_index=candidate_index,
        plan_id=source.plan.plan_id,
        status=status,
        source=source.source,
        is_final_valid=is_final_valid,
        is_optimal_time=is_optimal,
        group_count=group_count,
        is_within_time_limit=is_within_time_limit,
        completion_time_hour=completion_time,
        total_distance_km=total_distance,
        time_range_hour=time_range,
        distance_range_km=distance_range,
        audit_result=audit,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _lower_bound_report(
    road_network: RoadNetwork,
    params: UnlimitedPersonnelParameters,
    lower_bound_report: Optional[LowerBoundReport],
) -> LowerBoundReport:
    if lower_bound_report is not None:
        return lower_bound_report
    return compute_lower_bound_report(
        road_network,
        k_values=(1,),
        parameters=params.to_lower_bound_parameters(),
    )


def _best_completion_sort_key(record: ShortestTimeCandidateRecord) -> tuple[float, int, float, float, float, str, int]:
    return (
        float("inf") if record.completion_time_hour is None else record.completion_time_hour,
        10**9 if record.group_count is None else record.group_count,
        float("inf") if record.total_distance_km is None else record.total_distance_km,
        float("inf") if record.time_range_hour is None else record.time_range_hour,
        float("inf") if record.distance_range_km is None else record.distance_range_km,
        record.plan_id,
        record.candidate_index,
    )


def _recommendation_sort_key(record: ShortestTimeCandidateRecord) -> tuple[int, float, float, float, str, int]:
    return (
        10**9 if record.group_count is None else record.group_count,
        float("inf") if record.total_distance_km is None else record.total_distance_km,
        float("inf") if record.time_range_hour is None else record.time_range_hour,
        float("inf") if record.distance_range_km is None else record.distance_range_km,
        record.plan_id,
        record.candidate_index,
    )


def _parameter_warnings(plan: RoutePlan, params: UnlimitedPersonnelParameters) -> tuple[str, ...]:
    expected = {
        "T_hour": params.T_hour,
        "t_hour": params.t_hour,
        "speed_km_per_hour": params.speed_km_per_hour,
        "time_limit_hour": params.time_limit_hour,
    }
    warnings = []
    for key, expected_value in expected.items():
        if key not in plan.parameters:
            continue
        try:
            actual_value = float(plan.parameters[key])
        except (TypeError, ValueError):
            warnings.append(f"parameter_mismatch: {key}={plan.parameters[key]!r}, expected {expected_value}")
            continue
        if abs(actual_value - expected_value) > params.time_tolerance_hour:
            warnings.append(f"parameter_mismatch: {key}={actual_value}, expected {expected_value}")
    return tuple(warnings)


def _audit_result_to_dict(result: AuditResult) -> dict[str, object]:
    return {
        "plan_id": result.plan_id,
        "schema_valid": result.schema_valid,
        "coverage_valid": result.coverage_valid,
        "route_valid": result.route_valid,
        "metric_valid": result.metric_valid,
        "errors": list(result.errors),
        "warnings": list(result.warnings),
        "recomputed_metrics": None if result.recomputed_metrics is None else asdict(result.recomputed_metrics),
    }


def _parameters_to_dict(params: UnlimitedPersonnelParameters) -> dict[str, object]:
    return {
        "T_hour": params.T_hour,
        "t_hour": params.t_hour,
        "speed_km_per_hour": params.speed_km_per_hour,
        "time_limit_hour": params.time_limit_hour,
        "required_visit_nodes": sorted(params.required_visit_nodes, key=_node_sort_key),
        "distance_tolerance_km": params.distance_tolerance_km,
        "time_tolerance_hour": params.time_tolerance_hour,
    }


def _format_optional(value: object) -> str:
    return "none" if value is None else str(value)


def _format_optional_float(value: Optional[float]) -> str:
    return "none" if value is None else f"{value:.6g}"


def _node_sort_key(node: str) -> tuple[int, int, str]:
    if node == DEPOT:
        return (0, 0, node)
    if node.isalpha():
        return (1, 0, node)
    if node.isdigit():
        return (2, int(node), node)
    if node.startswith("U") and node[1:].isdigit():
        return (3, int(node[1:]), node)
    return (4, 0, node)
