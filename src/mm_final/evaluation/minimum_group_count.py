"""B5 24 小时最少组数判定。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Literal, Mapping, Optional, Union

from mm_final.contracts import AuditResult, RoutePlan, load_route_plan_json
from mm_final.evaluation.lower_bounds import (
    GroupLowerBound,
    LowerBoundParameters,
    LowerBoundReport,
    compute_lower_bound_report,
    default_k_values,
)
from mm_final.evaluation.route_plan_auditor import audit_route_plan
from mm_final.evaluation.route_plan_evaluator import EvaluationParameters
from mm_final.network import REQUIRED_VISIT_NODES, RoadNetwork


CandidateStatus = Literal[
    "candidate_feasible",
    "candidate_invalid",
    "candidate_over_time",
    "candidate_group_count_mismatch",
]
GroupDecisionStatus = Literal[
    "lower_bound_impossible",
    "candidate_feasible",
    "candidate_not_found",
    "candidate_invalid",
    "insufficient_evidence",
]
ConclusionStatus = Literal["proven_minimum", "incumbent_minimum", "no_feasible_candidate"]


@dataclass(frozen=True)
class MinimumGroupParameters:
    """B5 统一判定参数，避免不同候选方案自带参数改变同批口径。"""

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


@dataclass(frozen=True)
class CandidateDecisionRecord:
    group_count: int
    candidate_index: int
    plan_id: str
    status: CandidateStatus
    is_final_valid: bool
    group_count_matches: bool
    route_count: Optional[int]
    is_within_time_limit: Optional[bool]
    completion_time_hour: Optional[float]
    total_distance_km: Optional[float]
    time_range_hour: Optional[float]
    distance_range_km: Optional[float]
    audit_result: Optional[AuditResult]
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "group_count": self.group_count,
            "candidate_index": self.candidate_index,
            "plan_id": self.plan_id,
            "status": self.status,
            "is_final_valid": self.is_final_valid,
            "group_count_matches": self.group_count_matches,
            "route_count": self.route_count,
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
class GroupDecisionRecord:
    group_count: int
    status: GroupDecisionStatus
    lower_bound_status: Optional[str]
    lower_bound_hour: Optional[float]
    active_bound_codes: tuple[str, ...]
    candidate_records: tuple[CandidateDecisionRecord, ...]
    best_candidate_plan_id: Optional[str]
    best_candidate_index: Optional[int]
    best_candidate_time_hour: Optional[float]
    feasible_upper_bound_hour: Optional[float]
    gap_hour: Optional[float]
    search_complete: Optional[bool] = None
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "group_count": self.group_count,
            "status": self.status,
            "lower_bound_status": self.lower_bound_status,
            "lower_bound_hour": self.lower_bound_hour,
            "active_bound_codes": list(self.active_bound_codes),
            "candidate_count": len(self.candidate_records),
            "feasible_candidate_count": len(
                [record for record in self.candidate_records if record.status == "candidate_feasible"]
            ),
            "candidate_records": [record.to_dict() for record in self.candidate_records],
            "best_candidate_plan_id": self.best_candidate_plan_id,
            "best_candidate_index": self.best_candidate_index,
            "best_candidate_time_hour": self.best_candidate_time_hour,
            "feasible_upper_bound_hour": self.feasible_upper_bound_hour,
            "gap_hour": self.gap_hour,
            "search_complete": self.search_complete,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class MinimumGroupReport:
    parameters: MinimumGroupParameters
    k_values: tuple[int, ...]
    conclusion_status: ConclusionStatus
    minimum_feasible_k: Optional[int]
    recommended_plan_id: Optional[str]
    recommended_candidate_index: Optional[int]
    group_decisions: tuple[GroupDecisionRecord, ...]
    lower_bound_report: LowerBoundReport
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "parameters": _parameters_to_dict(self.parameters),
            "k_values": list(self.k_values),
            "conclusion_status": self.conclusion_status,
            "minimum_feasible_k": self.minimum_feasible_k,
            "recommended_plan_id": self.recommended_plan_id,
            "recommended_candidate_index": self.recommended_candidate_index,
            "group_decisions": [decision.to_dict() for decision in self.group_decisions],
            "lower_bound_report": self.lower_bound_report.to_dict(),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class _CandidateSource:
    plan: Optional[RoutePlan]
    plan_id: str
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def default_minimum_group_k_values(required_visit_nodes: Iterable[str] = REQUIRED_VISIT_NODES) -> tuple[int, ...]:
    return default_k_values(required_visit_nodes)


def decide_minimum_group_count(
    road_network: RoadNetwork,
    *,
    k_values: Iterable[int],
    candidate_plans_by_k: Mapping[int, Iterable[RoutePlan]],
    parameters: Optional[MinimumGroupParameters] = None,
    lower_bound_report: Optional[LowerBoundReport] = None,
    search_complete_by_k: Optional[Mapping[int, bool]] = None,
) -> MinimumGroupReport:
    sources_by_k = {
        group_count: tuple(_CandidateSource(plan=plan, plan_id=plan.plan_id) for plan in plans)
        for group_count, plans in candidate_plans_by_k.items()
    }
    return _decide_minimum_group_count_from_sources(
        road_network,
        k_values=k_values,
        candidate_sources_by_k=sources_by_k,
        parameters=parameters,
        lower_bound_report=lower_bound_report,
        search_complete_by_k=search_complete_by_k,
    )


def decide_minimum_group_count_json_files(
    road_network: RoadNetwork,
    *,
    k_values: Iterable[int],
    candidate_paths_by_k: Mapping[int, Iterable[Union[str, Path]]],
    parameters: Optional[MinimumGroupParameters] = None,
    lower_bound_report: Optional[LowerBoundReport] = None,
    search_complete_by_k: Optional[Mapping[int, bool]] = None,
) -> MinimumGroupReport:
    sources_by_k: dict[int, tuple[_CandidateSource, ...]] = {}
    for group_count, paths in candidate_paths_by_k.items():
        sources: list[_CandidateSource] = []
        for raw_path in paths:
            path = Path(raw_path)
            try:
                validation = load_route_plan_json(path)
            except Exception as exc:
                sources.append(
                    _CandidateSource(
                        plan=None,
                        plan_id=path.stem,
                        errors=(f"json_load_failed: {exc}",),
                    )
                )
                continue
            if validation.plan is None:
                errors = tuple(diagnostic.to_text() for diagnostic in validation.errors)
                warnings = tuple(diagnostic.to_text() for diagnostic in validation.warnings)
                sources.append(_CandidateSource(plan=None, plan_id=path.stem, errors=errors, warnings=warnings))
            else:
                warnings = tuple(diagnostic.to_text() for diagnostic in validation.warnings)
                sources.append(_CandidateSource(plan=validation.plan, plan_id=validation.plan.plan_id, warnings=warnings))
        sources_by_k[group_count] = tuple(sources)

    return _decide_minimum_group_count_from_sources(
        road_network,
        k_values=k_values,
        candidate_sources_by_k=sources_by_k,
        parameters=parameters,
        lower_bound_report=lower_bound_report,
        search_complete_by_k=search_complete_by_k,
    )


def minimum_group_report_to_markdown(report: MinimumGroupReport) -> str:
    lines = [
        "## Minimum Group Report",
        "",
        f"- conclusion_status: {report.conclusion_status}",
        f"- minimum_feasible_k: {_format_optional(report.minimum_feasible_k)}",
        f"- recommended_plan_id: {_format_optional(report.recommended_plan_id)}",
        "",
        "### Group Decisions",
        "",
        "| k | status | lower_bound_hour | best_candidate_time_hour | gap_hour | best_plan |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for decision in report.group_decisions:
        lines.append(
            f"| {decision.group_count} | {decision.status} | {_format_optional_float(decision.lower_bound_hour)} | "
            f"{_format_optional_float(decision.best_candidate_time_hour)} | "
            f"{_format_optional_float(decision.gap_hour)} | "
            f"{_format_optional(decision.best_candidate_plan_id)} |"
        )

    lines.extend(["", "### Candidate Records", ""])
    for decision in report.group_decisions:
        if not decision.candidate_records:
            lines.append(f"- k={decision.group_count}: none")
            continue
        for record in decision.candidate_records:
            lines.append(
                f"- k={decision.group_count} candidate[{record.candidate_index}] "
                f"{record.plan_id}: {record.status}, "
                f"completion_time_hour={_format_optional_float(record.completion_time_hour)}"
            )
    if report.warnings:
        lines.extend(["", "### Warnings", ""])
        lines.extend(f"- {warning}" for warning in report.warnings)
    return "\n".join(lines) + "\n"


def _decide_minimum_group_count_from_sources(
    road_network: RoadNetwork,
    *,
    k_values: Iterable[int],
    candidate_sources_by_k: Mapping[int, Iterable[_CandidateSource]],
    parameters: Optional[MinimumGroupParameters],
    lower_bound_report: Optional[LowerBoundReport],
    search_complete_by_k: Optional[Mapping[int, bool]],
) -> MinimumGroupReport:
    params = MinimumGroupParameters() if parameters is None else parameters
    k_tuple = _validate_k_values(k_values)
    lower_report = _lower_bound_report(road_network, k_tuple, params, lower_bound_report)
    lower_bounds_by_k = _lower_bounds_by_k(lower_report, k_tuple)
    search_flags = {} if search_complete_by_k is None else dict(search_complete_by_k)

    seen_plan_ids: set[str] = set()
    group_decisions: list[GroupDecisionRecord] = []
    for group_count in k_tuple:
        lower_bound = lower_bounds_by_k[group_count]
        sources = tuple(candidate_sources_by_k.get(group_count, ()))
        if lower_bound.status == "lower_bound_impossible":
            group_decisions.append(
                GroupDecisionRecord(
                    group_count=group_count,
                    status="lower_bound_impossible",
                    lower_bound_status=lower_bound.status,
                    lower_bound_hour=lower_bound.lower_bound_hour,
                    active_bound_codes=lower_bound.active_bound_codes,
                    candidate_records=(),
                    best_candidate_plan_id=None,
                    best_candidate_index=None,
                    best_candidate_time_hour=None,
                    feasible_upper_bound_hour=None,
                    gap_hour=None,
                    search_complete=search_flags.get(group_count),
                )
            )
            continue

        candidate_records = tuple(
            _candidate_record(
                source,
                group_count,
                index,
                road_network,
                params,
                seen_plan_ids,
            )
            for index, source in enumerate(sources, start=1)
        )
        group_decisions.append(
            _group_decision(
                group_count,
                lower_bound,
                candidate_records,
                search_flags.get(group_count),
            )
        )

    conclusion_status, minimum_feasible_k, recommended = _conclusion(group_decisions)
    return MinimumGroupReport(
        parameters=params,
        k_values=k_tuple,
        conclusion_status=conclusion_status,
        minimum_feasible_k=minimum_feasible_k,
        recommended_plan_id=None if recommended is None else recommended.best_candidate_plan_id,
        recommended_candidate_index=None if recommended is None else recommended.best_candidate_index,
        group_decisions=tuple(group_decisions),
        lower_bound_report=lower_report,
    )


def _candidate_record(
    source: _CandidateSource,
    group_count: int,
    candidate_index: int,
    road_network: RoadNetwork,
    params: MinimumGroupParameters,
    seen_plan_ids: set[str],
) -> CandidateDecisionRecord:
    warnings = list(source.warnings)
    errors = list(source.errors)

    if source.plan_id in seen_plan_ids:
        warnings.append(f"duplicate_plan_id: {source.plan_id}")
    seen_plan_ids.add(source.plan_id)

    if source.plan is None:
        return CandidateDecisionRecord(
            group_count=group_count,
            candidate_index=candidate_index,
            plan_id=source.plan_id,
            status="candidate_invalid",
            is_final_valid=False,
            group_count_matches=False,
            route_count=None,
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
    route_count = None if metrics is None else metrics.group_count
    group_count_matches = route_count == group_count
    is_within_time_limit = None if metrics is None else metrics.is_within_time_limit
    completion_time = None if metrics is None else metrics.completion_time_hour
    total_distance = None if metrics is None else metrics.total_distance_km
    time_range = None if metrics is None else metrics.time_range_hour
    distance_range = None if metrics is None else metrics.distance_range_km

    if not is_final_valid or metrics is None:
        status: CandidateStatus = "candidate_invalid"
    elif not group_count_matches:
        status = "candidate_group_count_mismatch"
        warnings.append("candidate_group_count_mismatch")
    elif not metrics.is_within_time_limit:
        status = "candidate_over_time"
    else:
        status = "candidate_feasible"

    return CandidateDecisionRecord(
        group_count=group_count,
        candidate_index=candidate_index,
        plan_id=source.plan.plan_id,
        status=status,
        is_final_valid=is_final_valid,
        group_count_matches=group_count_matches,
        route_count=route_count,
        is_within_time_limit=is_within_time_limit,
        completion_time_hour=completion_time,
        total_distance_km=total_distance,
        time_range_hour=time_range,
        distance_range_km=distance_range,
        audit_result=audit,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _group_decision(
    group_count: int,
    lower_bound: GroupLowerBound,
    candidate_records: tuple[CandidateDecisionRecord, ...],
    search_complete: Optional[bool],
) -> GroupDecisionRecord:
    if not candidate_records:
        status: GroupDecisionStatus = (
            "insufficient_evidence" if lower_bound.status == "insufficient_evidence" else "candidate_not_found"
        )
    elif any(record.status == "candidate_feasible" for record in candidate_records):
        status = "candidate_feasible"
    elif any(record.status == "candidate_over_time" for record in candidate_records):
        status = "insufficient_evidence"
    else:
        status = "candidate_invalid"

    best_observed = _best_observed_candidate(candidate_records)
    best_feasible = _best_feasible_candidate(candidate_records)
    feasible_upper_bound = None if best_feasible is None else best_feasible.completion_time_hour
    gap = (
        None
        if feasible_upper_bound is None or lower_bound.lower_bound_hour is None
        else feasible_upper_bound - lower_bound.lower_bound_hour
    )
    return GroupDecisionRecord(
        group_count=group_count,
        status=status,
        lower_bound_status=lower_bound.status,
        lower_bound_hour=lower_bound.lower_bound_hour,
        active_bound_codes=lower_bound.active_bound_codes,
        candidate_records=candidate_records,
        best_candidate_plan_id=None if best_observed is None else best_observed.plan_id,
        best_candidate_index=None if best_observed is None else best_observed.candidate_index,
        best_candidate_time_hour=None if best_observed is None else best_observed.completion_time_hour,
        feasible_upper_bound_hour=feasible_upper_bound,
        gap_hour=gap,
        search_complete=search_complete,
    )


def _best_observed_candidate(
    records: tuple[CandidateDecisionRecord, ...]
) -> Optional[CandidateDecisionRecord]:
    observed = [
        record
        for record in records
        if record.is_final_valid and record.group_count_matches and record.completion_time_hour is not None
    ]
    return min(observed, key=_candidate_sort_key, default=None)


def _best_feasible_candidate(
    records: tuple[CandidateDecisionRecord, ...]
) -> Optional[CandidateDecisionRecord]:
    feasible = [record for record in records if record.status == "candidate_feasible"]
    return min(feasible, key=_candidate_sort_key, default=None)


def _candidate_sort_key(record: CandidateDecisionRecord) -> tuple[float, float, float, float, str, int]:
    return (
        float("inf") if record.completion_time_hour is None else record.completion_time_hour,
        float("inf") if record.total_distance_km is None else record.total_distance_km,
        float("inf") if record.time_range_hour is None else record.time_range_hour,
        float("inf") if record.distance_range_km is None else record.distance_range_km,
        record.plan_id,
        record.candidate_index,
    )


def _conclusion(
    group_decisions: list[GroupDecisionRecord],
) -> tuple[ConclusionStatus, Optional[int], Optional[GroupDecisionRecord]]:
    feasible_decisions = [decision for decision in group_decisions if decision.status == "candidate_feasible"]
    if not feasible_decisions:
        return "no_feasible_candidate", None, None

    minimum_decision = min(feasible_decisions, key=lambda decision: decision.group_count)
    minimum_k = minimum_decision.group_count
    decisions_by_k = {decision.group_count: decision for decision in group_decisions}
    smaller_k_values = range(1, minimum_k)
    is_proven = all(
        k in decisions_by_k and decisions_by_k[k].status == "lower_bound_impossible"
        for k in smaller_k_values
    )
    return (
        "proven_minimum" if is_proven else "incumbent_minimum",
        minimum_k,
        minimum_decision,
    )


def _lower_bound_report(
    road_network: RoadNetwork,
    k_values: tuple[int, ...],
    params: MinimumGroupParameters,
    lower_bound_report: Optional[LowerBoundReport],
) -> LowerBoundReport:
    if lower_bound_report is not None:
        return lower_bound_report
    return compute_lower_bound_report(
        road_network,
        k_values=k_values,
        parameters=params.to_lower_bound_parameters(),
    )


def _lower_bounds_by_k(
    report: LowerBoundReport,
    k_values: tuple[int, ...],
) -> dict[int, GroupLowerBound]:
    lower_bounds = {item.group_count: item for item in report.group_bounds}
    missing = [k for k in k_values if k not in lower_bounds]
    if missing:
        missing_text = ", ".join(str(k) for k in missing)
        raise ValueError(f"LowerBoundReport is missing k values: {missing_text}.")
    return lower_bounds


def _validate_k_values(k_values: Iterable[int]) -> tuple[int, ...]:
    k_tuple = tuple(k_values)
    if not k_tuple:
        raise ValueError("k_values must not be empty.")
    if len(set(k_tuple)) != len(k_tuple):
        raise ValueError("k_values must not contain duplicates.")
    for group_count in k_tuple:
        if group_count <= 0:
            raise ValueError("Every k value must be a positive integer.")
    return k_tuple


def _parameter_warnings(plan: RoutePlan, params: MinimumGroupParameters) -> tuple[str, ...]:
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


def _parameters_to_dict(params: MinimumGroupParameters) -> dict[str, object]:
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
    if node == "O":
        return (0, 0, node)
    if node.isalpha():
        return (1, 0, node)
    if node.isdigit():
        return (2, int(node), node)
    if node.startswith("U") and node[1:].isdigit():
        return (3, int(node[1:]), node)
    return (4, 0, node)
