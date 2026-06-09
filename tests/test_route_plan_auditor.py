import networkx as nx
from pathlib import Path

from mm_final.contracts import Route, RoutePlan, validate_route_plan_dict
from mm_final.evaluation import (
    EvaluationParameters,
    audit_route_plan,
    audit_route_plan_json,
    audit_validation_result,
    audit_result_to_markdown,
)
from mm_final.network import RoadNetwork


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "route_plans"


def make_network():
    graph = nx.Graph()
    graph.add_edge("O", "A", weight=2.0)
    graph.add_edge("A", "B", weight=3.0)
    graph.add_edge("B", "1", weight=4.0)
    graph.add_edge("O", "1", weight=20.0)
    return RoadNetwork(graph)


def make_parameters():
    return EvaluationParameters(
        T_hour=2.0,
        t_hour=1.0,
        speed_km_per_hour=10.0,
        time_limit_hour=24.0,
        required_visit_nodes=frozenset(("A", "B", "1")),
    )


def make_plan(routes, metrics=None, schema_version="route-plan-v1"):
    return RoutePlan(
        schema_version=schema_version,
        plan_id="manual-audit",
        source="manual_fixture",
        parameters={
            "T_hour": 2.0,
            "t_hour": 1.0,
            "speed_km_per_hour": 10.0,
            "time_limit_hour": 24.0,
        },
        routes=routes,
        metrics=metrics,
    )


def assert_contains_text(items, text):
    assert any(text in item for item in items)


def test_audit_route_plan_accepts_final_valid_plan_and_recomputes_metrics():
    plan = make_plan(
        [
            Route("R1", "O", ["A", "B"], None, None, None),
            Route("R2", "O", ["1"], None, None, None),
        ]
    )

    result = audit_route_plan(plan, make_network(), make_parameters(), mode="final")

    assert result.schema_valid
    assert result.coverage_valid
    assert result.route_valid
    assert result.metric_valid
    assert not result.errors
    assert not result.warnings
    assert result.recomputed_metrics is not None
    assert result.recomputed_metrics.completion_time_hour == 5.0


def test_final_audit_rejects_missing_duplicate_empty_and_metric_mismatch():
    plan = make_plan(
        [
            Route("R1", "O", ["A", "B", "B"], None, 999.0, {"distance_km": 999.0}),
            Route("R2", "O", [], None, None, None),
        ],
        metrics={"completion_time_hour": 999.0},
    )

    result = audit_route_plan(plan, make_network(), make_parameters(), mode="final")

    assert result.schema_valid
    assert not result.coverage_valid
    assert not result.route_valid
    assert not result.metric_valid
    assert_contains_text(result.errors, "missing_required_nodes")
    assert_contains_text(result.errors, "duplicate_required_node")
    assert_contains_text(result.errors, "empty_route")
    assert_contains_text(result.errors, "route_distance_mismatch")
    assert_contains_text(result.errors, "route_metric_mismatch")
    assert_contains_text(result.errors, "plan_metric_mismatch")


def test_candidate_audit_downgrades_intermediate_route_quality_issues():
    plan = make_plan(
        [
            Route("R1", "O", ["A", "B", "B"], None, 999.0, {"distance_km": 999.0}),
            Route("R2", "O", [], None, None, None),
        ],
        metrics={"completion_time_hour": 999.0},
    )

    result = audit_route_plan(plan, make_network(), make_parameters(), mode="candidate")

    assert result.schema_valid
    assert result.coverage_valid
    assert result.route_valid
    assert result.metric_valid
    assert not result.errors
    assert_contains_text(result.warnings, "candidate audit")
    assert_contains_text(result.warnings, "missing_required_nodes")
    assert_contains_text(result.warnings, "duplicate_required_node")
    assert_contains_text(result.warnings, "empty_route")
    assert_contains_text(result.warnings, "route_metric_mismatch")


def test_audit_route_plan_keeps_schema_and_bad_path_as_hard_errors_in_candidate_mode():
    plan = make_plan(
        [
            Route("R1", "X", ["A"], ["O", "B"], None, None),
            Route("R1", "O", ["B", "1"], None, None, None),
        ],
        schema_version="bad-version",
    )

    result = audit_route_plan(plan, make_network(), make_parameters(), mode="candidate")

    assert not result.schema_valid
    assert not result.route_valid
    assert_contains_text(result.errors, "invalid_schema_version")
    assert_contains_text(result.errors, "invalid_depot")
    assert_contains_text(result.errors, "duplicate_route_id")
    assert_contains_text(result.errors, "expanded_path_edge_missing")


def test_audit_validation_result_reports_schema_failure_without_core_route_plan():
    validation = validate_route_plan_dict(
        {
            "schema_version": "bad-version",
            "plan_id": "bad-plan",
            "source": "manual_fixture",
            "parameters": {},
            "routes": [],
            "metrics": None,
        }
    )

    result = audit_validation_result(validation, make_network(), plan_id="bad-plan")

    assert not result.schema_valid
    assert not result.coverage_valid
    assert not result.route_valid
    assert not result.metric_valid
    assert result.recomputed_metrics is None
    assert_contains_text(result.errors, "invalid_schema_version")


def test_audit_route_plan_json_reports_schema_failure_with_file_stem_plan_id():
    result = audit_route_plan_json(FIXTURE_DIR / "invalid-schema-version.json", make_network())

    assert result.plan_id == "invalid-schema-version"
    assert not result.schema_valid
    assert_contains_text(result.errors, "invalid_schema_version")


def test_markdown_summary_marks_mode_and_uses_audit_result_metrics():
    plan = make_plan([Route("R1", "O", ["A", "B", "1"], None, None, None)])
    audit = audit_route_plan(plan, make_network(), make_parameters(), mode="candidate")

    markdown = audit_result_to_markdown(audit, mode="candidate")

    assert "# RoutePlan Audit Summary" in markdown
    assert "mode: candidate" in markdown
    assert "candidate audit is not a final legality proof" in markdown
    assert "completion_time_hour" in markdown
