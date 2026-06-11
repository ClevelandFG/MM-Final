"""B7 参数敏感性分析。

本模块只评估给定候选路线在不同参数情景下的表现，不做路线重优化。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
from typing import Iterable, Literal, Mapping, Optional, Union

from mm_final.contracts import AuditResult, REQUIRED_VISIT_NODES, RouteMetrics, RoutePlan, load_route_plan_json
from mm_final.evaluation.minimum_group_count import (
    MinimumGroupParameters,
    MinimumGroupReport,
    decide_minimum_group_count,
)
from mm_final.evaluation.route_plan_auditor import audit_route_plan
from mm_final.evaluation.route_plan_evaluator import EvaluationParameters, evaluate_route_plan
from mm_final.evaluation.unlimited_personnel_time import (
    UnlimitedPersonnelParameters,
    UnlimitedPersonnelReport,
    analyze_unlimited_personnel_time,
)
from mm_final.network import RoadNetwork


ScenarioCandidateStatus = Literal["valid_candidate", "candidate_invalid", "parse_failed"]
ScenarioConclusionStatus = Literal[
    "best_in_pool",
    "needs_reoptimization",
    "proven_by_b5_or_b6",
    "no_valid_candidate",
]


@dataclass(frozen=True)
class ParameterScenario:
    """一组 B7 参数情景。"""

    scenario_id: str
    T_hour: float = 2.0
    t_hour: float = 1.0
    speed_km_per_hour: float = 35.0
    time_limit_hour: float = 24.0
    required_visit_nodes: frozenset[str] = frozenset(REQUIRED_VISIT_NODES)
    label: str = ""
    description: str = ""
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

    def to_unlimited_personnel_parameters(self) -> UnlimitedPersonnelParameters:
        return UnlimitedPersonnelParameters(
            T_hour=self.T_hour,
            t_hour=self.t_hour,
            speed_km_per_hour=self.speed_km_per_hour,
            time_limit_hour=self.time_limit_hour,
            required_visit_nodes=self.required_visit_nodes,
            distance_tolerance_km=self.distance_tolerance_km,
            time_tolerance_hour=self.time_tolerance_hour,
        )

    def to_minimum_group_parameters(self) -> MinimumGroupParameters:
        return MinimumGroupParameters(
            T_hour=self.T_hour,
            t_hour=self.t_hour,
            speed_km_per_hour=self.speed_km_per_hour,
            time_limit_hour=self.time_limit_hour,
            required_visit_nodes=self.required_visit_nodes,
            distance_tolerance_km=self.distance_tolerance_km,
            time_tolerance_hour=self.time_tolerance_hour,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "label": self.label,
            "description": self.description,
            "T_hour": self.T_hour,
            "t_hour": self.t_hour,
            "speed_km_per_hour": self.speed_km_per_hour,
            "time_limit_hour": self.time_limit_hour,
            "required_visit_nodes": sorted(self.required_visit_nodes, key=_node_sort_key),
            "distance_tolerance_km": self.distance_tolerance_km,
            "time_tolerance_hour": self.time_tolerance_hour,
        }


@dataclass(frozen=True)
class RouteComponentBreakdown:
    route_id: str
    distance_km: float
    travel_time_hour: float
    town_stop_time_hour: float
    village_stop_time_hour: float
    total_stop_time_hour: float
    total_time_hour: float
    travel_share: float
    town_stop_share: float
    village_stop_share: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ScenarioEvaluationRecord:
    scenario_id: str
    candidate_index: int
    plan_id: str
    status: ScenarioCandidateStatus
    is_final_valid: bool
    rank: Optional[int]
    baseline_rank: Optional[int]
    rank_delta: Optional[int]
    group_count: Optional[int]
    is_within_time_limit: Optional[bool]
    completion_time_hour: Optional[float]
    completion_delta_hour: Optional[float]
    completion_delta_ratio: Optional[float]
    total_distance_km: Optional[float]
    total_distance_delta_km: Optional[float]
    time_range_hour: Optional[float]
    distance_range_km: Optional[float]
    bottleneck_route_ids: tuple[str, ...]
    bottleneck_changed_from_baseline: Optional[bool]
    route_breakdowns: tuple[RouteComponentBreakdown, ...]
    audit_result: Optional[AuditResult]
    source: str = "candidate"
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "candidate_index": self.candidate_index,
            "plan_id": self.plan_id,
            "status": self.status,
            "source": self.source,
            "is_final_valid": self.is_final_valid,
            "rank": self.rank,
            "baseline_rank": self.baseline_rank,
            "rank_delta": self.rank_delta,
            "group_count": self.group_count,
            "is_within_time_limit": self.is_within_time_limit,
            "completion_time_hour": self.completion_time_hour,
            "completion_delta_hour": self.completion_delta_hour,
            "completion_delta_ratio": self.completion_delta_ratio,
            "total_distance_km": self.total_distance_km,
            "total_distance_delta_km": self.total_distance_delta_km,
            "time_range_hour": self.time_range_hour,
            "distance_range_km": self.distance_range_km,
            "bottleneck_route_ids": list(self.bottleneck_route_ids),
            "bottleneck_changed_from_baseline": self.bottleneck_changed_from_baseline,
            "route_breakdowns": [item.to_dict() for item in self.route_breakdowns],
            "audit_result": None if self.audit_result is None else _audit_result_to_dict(self.audit_result),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ScenarioSummary:
    scenario_id: str
    conclusion_status: ScenarioConclusionStatus
    recommended_plan_id: Optional[str]
    recommended_candidate_index: Optional[int]
    valid_candidate_count: int
    best_completion_time_hour: Optional[float]
    best_total_distance_km: Optional[float]
    baseline_completion_delta_hour: Optional[float]
    bottleneck_route_ids: tuple[str, ...]
    bottleneck_changed_from_baseline: Optional[bool]
    requires_reoptimization: bool
    reoptimization_reasons: tuple[str, ...]
    unlimited_personnel_report: Optional[UnlimitedPersonnelReport] = None
    minimum_group_report: Optional[MinimumGroupReport] = None
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "conclusion_status": self.conclusion_status,
            "recommended_plan_id": self.recommended_plan_id,
            "recommended_candidate_index": self.recommended_candidate_index,
            "valid_candidate_count": self.valid_candidate_count,
            "best_completion_time_hour": self.best_completion_time_hour,
            "best_total_distance_km": self.best_total_distance_km,
            "baseline_completion_delta_hour": self.baseline_completion_delta_hour,
            "bottleneck_route_ids": list(self.bottleneck_route_ids),
            "bottleneck_changed_from_baseline": self.bottleneck_changed_from_baseline,
            "requires_reoptimization": self.requires_reoptimization,
            "reoptimization_reasons": list(self.reoptimization_reasons),
            "unlimited_personnel_report": (
                None if self.unlimited_personnel_report is None else self.unlimited_personnel_report.to_dict()
            ),
            "minimum_group_report": None if self.minimum_group_report is None else self.minimum_group_report.to_dict(),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class SensitivityReport:
    baseline_scenario_id: str
    scenarios: tuple[ParameterScenario, ...]
    scenario_summaries: tuple[ScenarioSummary, ...]
    candidate_records: tuple[ScenarioEvaluationRecord, ...]
    completion_delta_ratio_threshold: float
    time_range_threshold_hour: float
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "baseline_scenario_id": self.baseline_scenario_id,
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
            "scenario_summaries": [summary.to_dict() for summary in self.scenario_summaries],
            "candidate_records": [record.to_dict() for record in self.candidate_records],
            "completion_delta_ratio_threshold": self.completion_delta_ratio_threshold,
            "time_range_threshold_hour": self.time_range_threshold_hour,
            "warnings": list(self.warnings),
        }

    def to_table_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        summaries_by_id = {summary.scenario_id: summary for summary in self.scenario_summaries}
        for record in self.candidate_records:
            summary = summaries_by_id[record.scenario_id]
            rows.append(
                {
                    "scenario_id": record.scenario_id,
                    "plan_id": record.plan_id,
                    "candidate_index": record.candidate_index,
                    "status": record.status,
                    "rank": record.rank,
                    "baseline_rank": record.baseline_rank,
                    "rank_delta": record.rank_delta,
                    "group_count": record.group_count,
                    "completion_time_hour": record.completion_time_hour,
                    "completion_delta_hour": record.completion_delta_hour,
                    "completion_delta_ratio": record.completion_delta_ratio,
                    "total_distance_km": record.total_distance_km,
                    "total_distance_delta_km": record.total_distance_delta_km,
                    "time_range_hour": record.time_range_hour,
                    "distance_range_km": record.distance_range_km,
                    "bottleneck_route_ids": ",".join(record.bottleneck_route_ids),
                    "scenario_conclusion_status": summary.conclusion_status,
                    "requires_reoptimization": summary.requires_reoptimization,
                    "reoptimization_reasons": ",".join(summary.reoptimization_reasons),
                }
            )
        return rows


@dataclass(frozen=True)
class _CandidateSource:
    plan: Optional[RoutePlan]
    plan_id: str
    source: str
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _RawScenarioRecord:
    scenario: ParameterScenario
    candidate_index: int
    plan_id: str
    status: ScenarioCandidateStatus
    source: str
    is_final_valid: bool
    group_count: Optional[int]
    is_within_time_limit: Optional[bool]
    completion_time_hour: Optional[float]
    total_distance_km: Optional[float]
    time_range_hour: Optional[float]
    distance_range_km: Optional[float]
    bottleneck_route_ids: tuple[str, ...]
    route_breakdowns: tuple[RouteComponentBreakdown, ...]
    audit_result: Optional[AuditResult]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def default_parameter_scenarios(
    *,
    required_visit_nodes: frozenset[str] = frozenset(REQUIRED_VISIT_NODES),
    time_limit_hour: float = 24.0,
) -> tuple[ParameterScenario, ...]:
    """生成 B7 第一版默认代表性情景。"""

    base = {
        "time_limit_hour": time_limit_hour,
        "required_visit_nodes": required_visit_nodes,
    }
    return (
        ParameterScenario("baseline", T_hour=2.0, t_hour=1.0, speed_km_per_hour=35.0, label="Baseline", **base),
        ParameterScenario("T_low", T_hour=1.5, t_hour=1.0, speed_km_per_hour=35.0, label="Lower town stop", **base),
        ParameterScenario("T_high", T_hour=2.5, t_hour=1.0, speed_km_per_hour=35.0, label="Higher town stop", **base),
        ParameterScenario("t_low", T_hour=2.0, t_hour=0.5, speed_km_per_hour=35.0, label="Lower village stop", **base),
        ParameterScenario("t_high", T_hour=2.0, t_hour=1.5, speed_km_per_hour=35.0, label="Higher village stop", **base),
        ParameterScenario("v_low", T_hour=2.0, t_hour=1.0, speed_km_per_hour=25.0, label="Lower speed", **base),
        ParameterScenario("v_high", T_hour=2.0, t_hour=1.0, speed_km_per_hour=45.0, label="Higher speed", **base),
    )


def load_parameter_scenarios_json(path: Union[str, Path]) -> tuple[ParameterScenario, ...]:
    """从独立 JSON 配置读取参数情景。

    支持根对象为数组，或根对象包含 ``scenarios`` 数组。
    """

    scenario_path = Path(path)
    with scenario_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    raw_scenarios = raw.get("scenarios") if isinstance(raw, Mapping) else raw
    if not isinstance(raw_scenarios, list):
        raise ValueError("Scenario JSON must be a list or an object with a 'scenarios' list.")
    scenarios = tuple(_parameter_scenario_from_mapping(item, index) for index, item in enumerate(raw_scenarios))
    _validate_scenarios(scenarios)
    return scenarios


def analyze_parameter_sensitivity(
    road_network: RoadNetwork,
    *,
    candidate_plans: Iterable[RoutePlan] = (),
    scenarios: Optional[Iterable[ParameterScenario]] = None,
    baseline_scenario_id: Optional[str] = None,
    include_unlimited_personnel_summary: bool = True,
    minimum_group_k_values: Optional[Iterable[int]] = None,
    completion_delta_ratio_threshold: float = 0.10,
    time_range_threshold_hour: float = 1.0,
) -> SensitivityReport:
    sources = tuple(
        _CandidateSource(plan=plan, plan_id=plan.plan_id, source="candidate")
        for plan in candidate_plans
    )
    return _analyze_parameter_sensitivity_from_sources(
        road_network,
        candidate_sources=sources,
        scenarios=scenarios,
        baseline_scenario_id=baseline_scenario_id,
        include_unlimited_personnel_summary=include_unlimited_personnel_summary,
        minimum_group_k_values=minimum_group_k_values,
        completion_delta_ratio_threshold=completion_delta_ratio_threshold,
        time_range_threshold_hour=time_range_threshold_hour,
    )


def analyze_parameter_sensitivity_json_files(
    road_network: RoadNetwork,
    *,
    candidate_paths: Iterable[Union[str, Path]],
    scenarios: Optional[Iterable[ParameterScenario]] = None,
    baseline_scenario_id: Optional[str] = None,
    include_unlimited_personnel_summary: bool = True,
    minimum_group_k_values: Optional[Iterable[int]] = None,
    completion_delta_ratio_threshold: float = 0.10,
    time_range_threshold_hour: float = 1.0,
) -> SensitivityReport:
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
            sources.append(
                _CandidateSource(
                    plan=None,
                    plan_id=path.stem,
                    source="parse_failed",
                    errors=tuple(diagnostic.to_text() for diagnostic in validation.errors),
                    warnings=tuple(diagnostic.to_text() for diagnostic in validation.warnings),
                )
            )
        else:
            sources.append(
                _CandidateSource(
                    plan=validation.plan,
                    plan_id=validation.plan.plan_id,
                    source="candidate",
                    warnings=tuple(diagnostic.to_text() for diagnostic in validation.warnings),
                )
            )

    return _analyze_parameter_sensitivity_from_sources(
        road_network,
        candidate_sources=tuple(sources),
        scenarios=scenarios,
        baseline_scenario_id=baseline_scenario_id,
        include_unlimited_personnel_summary=include_unlimited_personnel_summary,
        minimum_group_k_values=minimum_group_k_values,
        completion_delta_ratio_threshold=completion_delta_ratio_threshold,
        time_range_threshold_hour=time_range_threshold_hour,
    )


def sensitivity_report_to_markdown(report: SensitivityReport) -> str:
    lines = [
        "## Parameter Sensitivity Report",
        "",
        f"- baseline_scenario_id: {report.baseline_scenario_id}",
        f"- completion_delta_ratio_threshold: {report.completion_delta_ratio_threshold:.6g}",
        f"- time_range_threshold_hour: {report.time_range_threshold_hour:.6g}",
        "",
        "### Scenario Summary",
        "",
        "| scenario | status | best_plan | best_completion_hour | bottleneck_routes | reoptimization | reasons |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for summary in report.scenario_summaries:
        reasons = ", ".join(summary.reoptimization_reasons) if summary.reoptimization_reasons else "-"
        bottlenecks = ", ".join(summary.bottleneck_route_ids) if summary.bottleneck_route_ids else "-"
        lines.append(
            f"| {summary.scenario_id} | {summary.conclusion_status} | "
            f"{_format_optional(summary.recommended_plan_id)} | "
            f"{_format_optional_float(summary.best_completion_time_hour)} | {bottlenecks} | "
            f"{summary.requires_reoptimization} | {reasons} |"
        )

    lines.extend(
        [
            "",
            "### Candidate Records",
            "",
            "| scenario | rank | plan_id | status | completion_hour | delta_hour | rank_delta | bottleneck_routes |",
            "| --- | ---: | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for record in report.candidate_records:
        bottlenecks = ", ".join(record.bottleneck_route_ids) if record.bottleneck_route_ids else "-"
        lines.append(
            f"| {record.scenario_id} | {_format_optional(record.rank)} | {record.plan_id} | {record.status} | "
            f"{_format_optional_float(record.completion_time_hour)} | "
            f"{_format_optional_float(record.completion_delta_hour)} | "
            f"{_format_optional(record.rank_delta)} | {bottlenecks} |"
        )

    if report.warnings:
        lines.extend(["", "### Warnings", ""])
        lines.extend(f"- {warning}" for warning in report.warnings)
    return "\n".join(lines) + "\n"


def _analyze_parameter_sensitivity_from_sources(
    road_network: RoadNetwork,
    *,
    candidate_sources: Iterable[_CandidateSource],
    scenarios: Optional[Iterable[ParameterScenario]],
    baseline_scenario_id: Optional[str],
    include_unlimited_personnel_summary: bool,
    minimum_group_k_values: Optional[Iterable[int]],
    completion_delta_ratio_threshold: float,
    time_range_threshold_hour: float,
) -> SensitivityReport:
    scenario_tuple = tuple(default_parameter_scenarios() if scenarios is None else scenarios)
    _validate_scenarios(scenario_tuple)
    baseline_id = scenario_tuple[0].scenario_id if baseline_scenario_id is None else baseline_scenario_id
    if baseline_id not in {scenario.scenario_id for scenario in scenario_tuple}:
        raise ValueError(f"baseline_scenario_id {baseline_id!r} is not present in scenarios.")
    if completion_delta_ratio_threshold < 0:
        raise ValueError("completion_delta_ratio_threshold must be non-negative.")
    if time_range_threshold_hour < 0:
        raise ValueError("time_range_threshold_hour must be non-negative.")

    sources = tuple(candidate_sources)
    minimum_group_k_tuple = None if minimum_group_k_values is None else tuple(minimum_group_k_values)
    raw_records = tuple(
        _evaluate_source_for_scenario(
            source,
            scenario,
            candidate_index=index,
            road_network=road_network,
        )
        for scenario in scenario_tuple
        for index, source in enumerate(sources, start=1)
    )
    raw_records = _with_duplicate_warnings(raw_records)
    ranked_records = _rank_and_delta_records(raw_records, baseline_id)
    summaries = tuple(
        _scenario_summary(
            scenario,
            ranked_records,
            baseline_id=baseline_id,
            road_network=road_network,
            candidate_sources=sources,
            include_unlimited_personnel_summary=include_unlimited_personnel_summary,
            minimum_group_k_values=minimum_group_k_tuple,
            completion_delta_ratio_threshold=completion_delta_ratio_threshold,
            time_range_threshold_hour=time_range_threshold_hour,
        )
        for scenario in scenario_tuple
    )

    warnings: list[str] = []
    if not sources:
        warnings.append("candidate_pool_empty")
    if not any(record.scenario_id == baseline_id and record.is_final_valid for record in ranked_records):
        warnings.append("baseline_has_no_valid_candidate")

    return SensitivityReport(
        baseline_scenario_id=baseline_id,
        scenarios=scenario_tuple,
        scenario_summaries=summaries,
        candidate_records=ranked_records,
        completion_delta_ratio_threshold=completion_delta_ratio_threshold,
        time_range_threshold_hour=time_range_threshold_hour,
        warnings=tuple(warnings),
    )


def _evaluate_source_for_scenario(
    source: _CandidateSource,
    scenario: ParameterScenario,
    *,
    candidate_index: int,
    road_network: RoadNetwork,
) -> _RawScenarioRecord:
    errors = list(source.errors)
    warnings = list(source.warnings)

    if source.plan is None:
        return _RawScenarioRecord(
            scenario=scenario,
            candidate_index=candidate_index,
            plan_id=source.plan_id,
            status="parse_failed",
            source=source.source,
            is_final_valid=False,
            group_count=None,
            is_within_time_limit=None,
            completion_time_hour=None,
            total_distance_km=None,
            time_range_hour=None,
            distance_range_km=None,
            bottleneck_route_ids=(),
            route_breakdowns=(),
            audit_result=None,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    warnings.extend(_parameter_warnings(source.plan, scenario))
    audit = audit_route_plan(source.plan, road_network, scenario.to_evaluation_parameters(), mode="final")
    is_final_valid = audit.schema_valid and audit.coverage_valid and audit.route_valid and audit.metric_valid
    metrics = audit.recomputed_metrics
    if metrics is None:
        is_final_valid = False

    try:
        evaluation = evaluate_route_plan(source.plan, road_network, scenario.to_evaluation_parameters())
        route_breakdowns = tuple(
            _route_component_breakdown(route_id, metrics)
            for route_id, metrics in evaluation.time_breakdown_by_route_id.items()
        )
        bottleneck_route_ids = evaluation.bottleneck_route_ids
    except Exception as exc:  # pragma: no cover - 底层图异常种类由 NetworkX 决定
        errors.append(f"evaluation_failed: {exc}")
        route_breakdowns = ()
        bottleneck_route_ids = ()

    if metrics is None:
        return _RawScenarioRecord(
            scenario=scenario,
            candidate_index=candidate_index,
            plan_id=source.plan.plan_id,
            status="candidate_invalid",
            source=source.source,
            is_final_valid=False,
            group_count=None,
            is_within_time_limit=None,
            completion_time_hour=None,
            total_distance_km=None,
            time_range_hour=None,
            distance_range_km=None,
            bottleneck_route_ids=bottleneck_route_ids,
            route_breakdowns=route_breakdowns,
            audit_result=audit,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    return _RawScenarioRecord(
        scenario=scenario,
        candidate_index=candidate_index,
        plan_id=source.plan.plan_id,
        status="valid_candidate" if is_final_valid else "candidate_invalid",
        source=source.source,
        is_final_valid=is_final_valid,
        group_count=metrics.group_count,
        is_within_time_limit=metrics.is_within_time_limit,
        completion_time_hour=metrics.completion_time_hour,
        total_distance_km=metrics.total_distance_km,
        time_range_hour=metrics.time_range_hour,
        distance_range_km=metrics.distance_range_km,
        bottleneck_route_ids=bottleneck_route_ids,
        route_breakdowns=route_breakdowns,
        audit_result=audit,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _with_duplicate_warnings(records: tuple[_RawScenarioRecord, ...]) -> tuple[_RawScenarioRecord, ...]:
    seen: dict[str, set[str]] = {}
    updated: list[_RawScenarioRecord] = []
    for record in records:
        scenario_seen = seen.setdefault(record.scenario.scenario_id, set())
        warnings = list(record.warnings)
        if record.plan_id in scenario_seen:
            warnings.append(f"duplicate_plan_id: {record.plan_id}")
        scenario_seen.add(record.plan_id)
        updated.append(_replace_raw_warnings(record, tuple(warnings)))
    return tuple(updated)


def _rank_and_delta_records(
    raw_records: tuple[_RawScenarioRecord, ...],
    baseline_scenario_id: str,
) -> tuple[ScenarioEvaluationRecord, ...]:
    ranks: dict[tuple[str, int], int] = {}
    for scenario_id in {record.scenario.scenario_id for record in raw_records}:
        valid_records = [
            record
            for record in raw_records
            if record.scenario.scenario_id == scenario_id
            and record.is_final_valid
            and record.completion_time_hour is not None
        ]
        for rank, record in enumerate(sorted(valid_records, key=_raw_record_sort_key), start=1):
            ranks[(scenario_id, record.candidate_index)] = rank

    baseline_by_plan_id = {
        record.plan_id: record
        for record in raw_records
        if record.scenario.scenario_id == baseline_scenario_id and record.is_final_valid
    }
    baseline_rank_by_plan_id = {
        record.plan_id: ranks[(baseline_scenario_id, record.candidate_index)]
        for record in raw_records
        if record.scenario.scenario_id == baseline_scenario_id
        and record.is_final_valid
        and (baseline_scenario_id, record.candidate_index) in ranks
    }

    records: list[ScenarioEvaluationRecord] = []
    for raw in raw_records:
        rank = ranks.get((raw.scenario.scenario_id, raw.candidate_index))
        baseline = baseline_by_plan_id.get(raw.plan_id)
        baseline_rank = baseline_rank_by_plan_id.get(raw.plan_id)
        completion_delta = _optional_delta(raw.completion_time_hour, None if baseline is None else baseline.completion_time_hour)
        distance_delta = _optional_delta(raw.total_distance_km, None if baseline is None else baseline.total_distance_km)
        completion_ratio = _optional_ratio(
            completion_delta,
            None if baseline is None else baseline.completion_time_hour,
        )
        bottleneck_changed = None if baseline is None else raw.bottleneck_route_ids != baseline.bottleneck_route_ids
        rank_delta = None if rank is None or baseline_rank is None else rank - baseline_rank
        records.append(
            ScenarioEvaluationRecord(
                scenario_id=raw.scenario.scenario_id,
                candidate_index=raw.candidate_index,
                plan_id=raw.plan_id,
                status=raw.status,
                source=raw.source,
                is_final_valid=raw.is_final_valid,
                rank=rank,
                baseline_rank=baseline_rank,
                rank_delta=rank_delta,
                group_count=raw.group_count,
                is_within_time_limit=raw.is_within_time_limit,
                completion_time_hour=raw.completion_time_hour,
                completion_delta_hour=completion_delta,
                completion_delta_ratio=completion_ratio,
                total_distance_km=raw.total_distance_km,
                total_distance_delta_km=distance_delta,
                time_range_hour=raw.time_range_hour,
                distance_range_km=raw.distance_range_km,
                bottleneck_route_ids=raw.bottleneck_route_ids,
                bottleneck_changed_from_baseline=bottleneck_changed,
                route_breakdowns=raw.route_breakdowns,
                audit_result=raw.audit_result,
                errors=raw.errors,
                warnings=raw.warnings,
            )
        )
    return tuple(records)


def _scenario_summary(
    scenario: ParameterScenario,
    records: tuple[ScenarioEvaluationRecord, ...],
    *,
    baseline_id: str,
    road_network: RoadNetwork,
    candidate_sources: tuple[_CandidateSource, ...],
    include_unlimited_personnel_summary: bool,
    minimum_group_k_values: Optional[Iterable[int]],
    completion_delta_ratio_threshold: float,
    time_range_threshold_hour: float,
) -> ScenarioSummary:
    scenario_records = tuple(record for record in records if record.scenario_id == scenario.scenario_id)
    valid_records = [
        record
        for record in scenario_records
        if record.is_final_valid and record.completion_time_hour is not None
    ]
    best_record = min(valid_records, key=_record_sort_key, default=None)
    baseline_summary_record = _baseline_best_record(records, baseline_id)

    unlimited_report = (
        _unlimited_personnel_report(road_network, candidate_sources, scenario)
        if include_unlimited_personnel_summary
        else None
    )
    minimum_group_report = (
        _minimum_group_report(road_network, candidate_sources, scenario, minimum_group_k_values)
        if minimum_group_k_values is not None
        else None
    )

    if best_record is None:
        return ScenarioSummary(
            scenario_id=scenario.scenario_id,
            conclusion_status="no_valid_candidate",
            recommended_plan_id=None,
            recommended_candidate_index=None,
            valid_candidate_count=0,
            best_completion_time_hour=None,
            best_total_distance_km=None,
            baseline_completion_delta_hour=None,
            bottleneck_route_ids=(),
            bottleneck_changed_from_baseline=None,
            requires_reoptimization=False,
            reoptimization_reasons=(),
            unlimited_personnel_report=unlimited_report,
            minimum_group_report=minimum_group_report,
        )

    reasons = _reoptimization_reasons(
        best_record,
        baseline_summary_record,
        scenario_id=scenario.scenario_id,
        baseline_id=baseline_id,
        completion_delta_ratio_threshold=completion_delta_ratio_threshold,
        time_range_threshold_hour=time_range_threshold_hour,
    )
    requires_reoptimization = bool(reasons)
    conclusion_status: ScenarioConclusionStatus = "needs_reoptimization" if requires_reoptimization else "best_in_pool"
    if _has_strong_proof(best_record, unlimited_report, minimum_group_report, scenario.time_tolerance_hour):
        conclusion_status = "proven_by_b5_or_b6"

    baseline_completion = None if baseline_summary_record is None else baseline_summary_record.completion_time_hour
    return ScenarioSummary(
        scenario_id=scenario.scenario_id,
        conclusion_status=conclusion_status,
        recommended_plan_id=best_record.plan_id,
        recommended_candidate_index=best_record.candidate_index,
        valid_candidate_count=len(valid_records),
        best_completion_time_hour=best_record.completion_time_hour,
        best_total_distance_km=best_record.total_distance_km,
        baseline_completion_delta_hour=_optional_delta(best_record.completion_time_hour, baseline_completion),
        bottleneck_route_ids=best_record.bottleneck_route_ids,
        bottleneck_changed_from_baseline=best_record.bottleneck_changed_from_baseline,
        requires_reoptimization=requires_reoptimization,
        reoptimization_reasons=reasons,
        unlimited_personnel_report=unlimited_report,
        minimum_group_report=minimum_group_report,
    )


def _unlimited_personnel_report(
    road_network: RoadNetwork,
    candidate_sources: tuple[_CandidateSource, ...],
    scenario: ParameterScenario,
) -> UnlimitedPersonnelReport:
    plans = tuple(source.plan for source in candidate_sources if source.plan is not None)
    return analyze_unlimited_personnel_time(
        road_network,
        candidate_plans=plans,
        parameters=scenario.to_unlimited_personnel_parameters(),
    )


def _minimum_group_report(
    road_network: RoadNetwork,
    candidate_sources: tuple[_CandidateSource, ...],
    scenario: ParameterScenario,
    k_values: Iterable[int],
) -> MinimumGroupReport:
    plans_by_k: dict[int, list[RoutePlan]] = {}
    for source in candidate_sources:
        if source.plan is None:
            continue
        plans_by_k.setdefault(len(source.plan.routes), []).append(source.plan)
    return decide_minimum_group_count(
        road_network,
        k_values=tuple(k_values),
        candidate_plans_by_k=plans_by_k,
        parameters=scenario.to_minimum_group_parameters(),
    )


def _reoptimization_reasons(
    best_record: ScenarioEvaluationRecord,
    baseline_best_record: Optional[ScenarioEvaluationRecord],
    *,
    scenario_id: str,
    baseline_id: str,
    completion_delta_ratio_threshold: float,
    time_range_threshold_hour: float,
) -> tuple[str, ...]:
    if scenario_id == baseline_id:
        return ()
    reasons: list[str] = []
    if baseline_best_record is not None and best_record.plan_id != baseline_best_record.plan_id:
        reasons.append("candidate_winner_changed")
    if (
        best_record.completion_delta_ratio is not None
        and best_record.completion_delta_ratio > completion_delta_ratio_threshold
    ):
        reasons.append("completion_delta_ratio_exceeds_threshold")
    if best_record.bottleneck_changed_from_baseline:
        reasons.append("bottleneck_changed")
    if best_record.time_range_hour is not None and best_record.time_range_hour > time_range_threshold_hour:
        reasons.append("time_range_exceeds_threshold")
    return tuple(reasons)


def _has_strong_proof(
    best_record: ScenarioEvaluationRecord,
    unlimited_report: Optional[UnlimitedPersonnelReport],
    minimum_group_report: Optional[MinimumGroupReport],
    tolerance: float,
) -> bool:
    if (
        minimum_group_report is not None
        and minimum_group_report.conclusion_status == "proven_minimum"
        and minimum_group_report.recommended_plan_id == best_record.plan_id
    ):
        return True
    return (
        unlimited_report is not None
        and unlimited_report.conclusion_status == "proven_shortest_time"
        and unlimited_report.recommended_plan_id == best_record.plan_id
        and best_record.completion_time_hour is not None
        and abs(best_record.completion_time_hour - unlimited_report.shortest_time_lower_bound_hour) <= tolerance
    )


def _baseline_best_record(
    records: tuple[ScenarioEvaluationRecord, ...],
    baseline_id: str,
) -> Optional[ScenarioEvaluationRecord]:
    valid_records = [
        record
        for record in records
        if record.scenario_id == baseline_id and record.is_final_valid and record.completion_time_hour is not None
    ]
    return min(valid_records, key=_record_sort_key, default=None)


def _route_component_breakdown(route_id: str, metrics: RouteMetrics) -> RouteComponentBreakdown:
    total = metrics.total_time_hour
    if total <= 0:
        travel_share = 0.0
        town_share = 0.0
        village_share = 0.0
    else:
        travel_share = metrics.travel_time_hour / total
        town_share = metrics.town_stop_time_hour / total
        village_share = metrics.village_stop_time_hour / total
    return RouteComponentBreakdown(
        route_id=route_id,
        distance_km=metrics.distance_km,
        travel_time_hour=metrics.travel_time_hour,
        town_stop_time_hour=metrics.town_stop_time_hour,
        village_stop_time_hour=metrics.village_stop_time_hour,
        total_stop_time_hour=metrics.total_stop_time_hour,
        total_time_hour=metrics.total_time_hour,
        travel_share=travel_share,
        town_stop_share=town_share,
        village_stop_share=village_share,
    )


def _parameter_warnings(plan: RoutePlan, scenario: ParameterScenario) -> tuple[str, ...]:
    expected = {
        "T_hour": scenario.T_hour,
        "t_hour": scenario.t_hour,
        "speed_km_per_hour": scenario.speed_km_per_hour,
        "time_limit_hour": scenario.time_limit_hour,
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
        if abs(actual_value - expected_value) > scenario.time_tolerance_hour:
            warnings.append(f"parameter_mismatch: {key}={actual_value}, expected {expected_value}")
    return tuple(warnings)


def _raw_record_sort_key(record: _RawScenarioRecord) -> tuple[float, float, float, float, str, int]:
    return (
        float("inf") if record.completion_time_hour is None else record.completion_time_hour,
        float("inf") if record.total_distance_km is None else record.total_distance_km,
        float("inf") if record.time_range_hour is None else record.time_range_hour,
        float("inf") if record.distance_range_km is None else record.distance_range_km,
        record.plan_id,
        record.candidate_index,
    )


def _record_sort_key(record: ScenarioEvaluationRecord) -> tuple[float, float, float, float, str, int]:
    return (
        float("inf") if record.completion_time_hour is None else record.completion_time_hour,
        float("inf") if record.total_distance_km is None else record.total_distance_km,
        float("inf") if record.time_range_hour is None else record.time_range_hour,
        float("inf") if record.distance_range_km is None else record.distance_range_km,
        record.plan_id,
        record.candidate_index,
    )


def _replace_raw_warnings(record: _RawScenarioRecord, warnings: tuple[str, ...]) -> _RawScenarioRecord:
    return _RawScenarioRecord(
        scenario=record.scenario,
        candidate_index=record.candidate_index,
        plan_id=record.plan_id,
        status=record.status,
        source=record.source,
        is_final_valid=record.is_final_valid,
        group_count=record.group_count,
        is_within_time_limit=record.is_within_time_limit,
        completion_time_hour=record.completion_time_hour,
        total_distance_km=record.total_distance_km,
        time_range_hour=record.time_range_hour,
        distance_range_km=record.distance_range_km,
        bottleneck_route_ids=record.bottleneck_route_ids,
        route_breakdowns=record.route_breakdowns,
        audit_result=record.audit_result,
        errors=record.errors,
        warnings=warnings,
    )


def _optional_delta(value: Optional[float], baseline: Optional[float]) -> Optional[float]:
    if value is None or baseline is None:
        return None
    return value - baseline


def _optional_ratio(delta: Optional[float], baseline: Optional[float]) -> Optional[float]:
    if delta is None or baseline is None or abs(baseline) <= 1e-12:
        return None
    return delta / baseline


def _validate_scenarios(scenarios: tuple[ParameterScenario, ...]) -> None:
    if not scenarios:
        raise ValueError("scenarios must not be empty.")
    scenario_ids = [scenario.scenario_id for scenario in scenarios]
    if len(set(scenario_ids)) != len(scenario_ids):
        raise ValueError("scenario_id values must be unique.")
    for scenario in scenarios:
        if not scenario.scenario_id:
            raise ValueError("scenario_id must not be empty.")
        if scenario.T_hour < 0 or scenario.t_hour < 0:
            raise ValueError("Stop times must be non-negative.")
        if scenario.speed_km_per_hour <= 0:
            raise ValueError("speed_km_per_hour must be > 0.")
        if scenario.time_limit_hour <= 0:
            raise ValueError("time_limit_hour must be > 0.")


def _parameter_scenario_from_mapping(data: object, index: int) -> ParameterScenario:
    if not isinstance(data, Mapping):
        raise ValueError(f"Scenario item {index} must be an object.")
    if "scenario_id" not in data:
        raise ValueError(f"Scenario item {index} is missing scenario_id.")
    required_nodes = data.get("required_visit_nodes", REQUIRED_VISIT_NODES)
    if not isinstance(required_nodes, (list, tuple, set, frozenset)):
        raise ValueError(f"Scenario item {index} required_visit_nodes must be a list when provided.")
    return ParameterScenario(
        scenario_id=str(data["scenario_id"]),
        T_hour=float(data.get("T_hour", 2.0)),
        t_hour=float(data.get("t_hour", 1.0)),
        speed_km_per_hour=float(data.get("speed_km_per_hour", 35.0)),
        time_limit_hour=float(data.get("time_limit_hour", 24.0)),
        required_visit_nodes=frozenset(str(node) for node in required_nodes),
        label=str(data.get("label", "")),
        description=str(data.get("description", "")),
        distance_tolerance_km=float(data.get("distance_tolerance_km", 1e-6)),
        time_tolerance_hour=float(data.get("time_tolerance_hour", 1e-6)),
    )


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
