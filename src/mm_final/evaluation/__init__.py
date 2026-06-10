"""B 线方案评价入口。"""

from mm_final.evaluation.route_plan_auditor import (
    AuditMode,
    audit_result_to_markdown,
    audit_route_plan,
    audit_route_plan_json,
    audit_validation_result,
)
from mm_final.evaluation.lower_bounds import (
    GroupLowerBound,
    LowerBoundEntry,
    LowerBoundParameters,
    LowerBoundReport,
    compute_lower_bound_report,
    default_k_values,
    lower_bound_report_to_markdown,
)
from mm_final.evaluation.minimum_group_count import (
    CandidateDecisionRecord,
    GroupDecisionRecord,
    MinimumGroupParameters,
    MinimumGroupReport,
    decide_minimum_group_count,
    decide_minimum_group_count_json_files,
    default_minimum_group_k_values,
    minimum_group_report_to_markdown,
)
from mm_final.evaluation.route_plan_evaluator import (
    CoverageSummary,
    DistanceBalanceSummary,
    EvaluationParameters,
    EvaluationResult,
    evaluate_route_plan,
)

__all__ = [
    "AuditMode",
    "CandidateDecisionRecord",
    "CoverageSummary",
    "DistanceBalanceSummary",
    "EvaluationParameters",
    "EvaluationResult",
    "GroupDecisionRecord",
    "GroupLowerBound",
    "LowerBoundEntry",
    "LowerBoundParameters",
    "LowerBoundReport",
    "MinimumGroupParameters",
    "MinimumGroupReport",
    "audit_result_to_markdown",
    "audit_route_plan",
    "audit_route_plan_json",
    "audit_validation_result",
    "compute_lower_bound_report",
    "decide_minimum_group_count",
    "decide_minimum_group_count_json_files",
    "default_k_values",
    "default_minimum_group_k_values",
    "evaluate_route_plan",
    "lower_bound_report_to_markdown",
    "minimum_group_report_to_markdown",
]
