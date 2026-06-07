from pathlib import Path

import networkx as nx

from mm_final.contracts import PlanMetrics, Route, RouteMetrics, RoutePlan, load_route_plan_json
from mm_final.evaluation import EvaluationParameters, evaluate_route_plan
from mm_final.network import RoadNetwork, load_road_network


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "route_plans"


def make_network():
    graph = nx.Graph()
    graph.add_edge("O", "A", weight=2.0)
    graph.add_edge("A", "B", weight=3.0)
    graph.add_edge("B", "1", weight=4.0)
    graph.add_edge("O", "1", weight=20.0)
    return RoadNetwork(graph)


def make_plan(routes, metrics=None):
    return RoutePlan(
        schema_version="route-plan-v1",
        plan_id="manual-eval",
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


def make_parameters():
    return EvaluationParameters(
        T_hour=2.0,
        t_hour=1.0,
        speed_km_per_hour=10.0,
        time_limit_hour=24.0,
        required_visit_nodes=frozenset(("A", "B", "1")),
    )


def diagnostic_codes(result):
    return {diagnostic.code for diagnostic in result.diagnostics}


def test_evaluate_route_plan_recomputes_metrics_paths_balance_and_bottleneck():
    plan = make_plan(
        [
            Route("R1", "O", ["A", "B"], None, None, None),
            Route("R2", "O", ["1"], None, None, None),
        ]
    )

    result = evaluate_route_plan(plan, make_network(), make_parameters())

    assert result.plan_id == "manual-eval"
    assert result.route_metrics_by_id["R1"] == RouteMetrics(10.0, 1.0, 4.0, 0.0, 4.0, 5.0)
    assert result.route_metrics_by_id["R2"] == RouteMetrics(18.0, 1.8, 0.0, 1.0, 1.0, 2.8)
    assert result.plan_metrics == PlanMetrics(2, 28.0, 18.0, 10.0, 8.0, 5.0, 5.0, 2.2, True)
    assert result.expanded_paths_by_route_id["R1"] == ("O", "A", "B", "A", "O")
    assert result.bottleneck_route_ids == ("R1",)
    assert result.distance_balance.longest_route_ids == ("R2",)
    assert result.distance_balance.shortest_route_ids == ("R1",)
    assert result.coverage_summary.missing == ()
    assert not result.diagnostics


def test_evaluate_route_plan_warns_for_metric_mismatch_but_uses_recomputed_values():
    plan = make_plan(
        [
            Route(
                "R1",
                "O",
                ["A", "B"],
                None,
                999.0,
                {"distance_km": 999.0, "travel_time_hour": 99.0},
            )
        ],
        metrics={"total_distance_km": 999.0, "completion_time_hour": 99.0},
    )

    result = evaluate_route_plan(plan, make_network(), make_parameters())

    assert result.route_metrics_by_id["R1"].distance_km == 10.0
    assert result.plan_metrics.total_distance_km == 10.0
    assert {
        "route_distance_mismatch",
        "route_metric_mismatch",
        "plan_metric_mismatch",
    }.issubset(diagnostic_codes(result))


def test_evaluate_route_plan_reports_empty_duplicate_and_missing_nodes_as_warnings():
    plan = make_plan(
        [
            Route("R1", "O", ["A", "B", "B"], None, None, None),
            Route("R2", "O", [], None, None, None),
        ]
    )

    result = evaluate_route_plan(plan, make_network(), make_parameters())

    assert result.route_metrics_by_id["R2"].total_time_hour == 0.0
    assert result.coverage_summary.covered == ("A", "B")
    assert result.coverage_summary.missing == ("1",)
    assert result.coverage_summary.duplicated["B"] == ("R1", "R1")
    assert {"empty_route", "duplicate_required_node", "missing_required_nodes"}.issubset(diagnostic_codes(result))


def test_evaluate_route_plan_reports_expanded_path_differences_and_bad_edges():
    plan = make_plan(
        [
            Route("R1", "O", ["A", "B"], ["O", "A", "O"], None, None),
            Route("R2", "O", ["1"], ["O", "B"], None, None),
        ]
    )

    result = evaluate_route_plan(plan, make_network(), make_parameters())

    assert "expanded_path_mismatch" in diagnostic_codes(result)
    assert "expanded_path_edge_missing" in diagnostic_codes(result)
    assert result.route_metrics_by_id["R2"].distance_km == 18.0


def test_evaluation_result_to_dict_is_json_ready():
    plan = make_plan([Route("R1", "O", ["A", "B"], None, None, None)])

    result_dict = evaluate_route_plan(plan, make_network(), make_parameters()).to_dict()

    assert result_dict["plan_id"] == "manual-eval"
    assert result_dict["route_metrics_by_id"]["R1"]["distance_km"] == 10.0
    assert result_dict["coverage_summary"]["covered"] == ["A", "B"]
    assert result_dict["expanded_paths_by_route_id"]["R1"] == ["O", "A", "B", "A", "O"]


def test_evaluate_b0_json_fixture_against_official_road_network():
    plan_result = load_route_plan_json(FIXTURE_DIR / "schema-smoke-001.json")
    network_result = load_road_network()

    assert plan_result.plan is not None
    assert network_result.network is not None

    result = evaluate_route_plan(plan_result.plan, network_result.network)

    assert result.plan_id == "schema-smoke-001"
    assert result.route_metrics_by_id["R1"].distance_km > 0
    assert result.plan_metrics is not None
    assert "missing_required_nodes" in diagnostic_codes(result)
