import networkx as nx

from mm_final.contracts import Route, RoutePlan
from mm_final.evaluation import (
    MinimumGroupParameters,
    decide_minimum_group_count,
    decide_minimum_group_count_json_files,
    minimum_group_report_to_markdown,
)
from mm_final.network import RoadNetwork, load_road_network


def make_network():
    graph = nx.Graph()
    graph.add_edge("O", "A", weight=10.0)
    graph.add_edge("A", "1", weight=15.0)
    graph.add_edge("O", "1", weight=20.0)
    return RoadNetwork(graph)


def make_parameters(time_limit_hour=6.0):
    return MinimumGroupParameters(
        T_hour=2.0,
        t_hour=1.0,
        speed_km_per_hour=10.0,
        time_limit_hour=time_limit_hour,
        required_visit_nodes=frozenset(("A", "1")),
    )


def make_three_town_network():
    graph = nx.Graph()
    graph.add_edge("O", "A", weight=5.0)
    graph.add_edge("O", "B", weight=5.0)
    graph.add_edge("O", "C", weight=5.0)
    graph.add_edge("A", "B", weight=1.0)
    graph.add_edge("B", "C", weight=1.0)
    return RoadNetwork(graph)


def make_three_town_parameters():
    return MinimumGroupParameters(
        T_hour=2.0,
        t_hour=1.0,
        speed_km_per_hour=10.0,
        time_limit_hour=5.5,
        required_visit_nodes=frozenset(("A", "B", "C")),
    )


def make_plan(plan_id, routes, parameters=None):
    return RoutePlan(
        schema_version="route-plan-v1",
        plan_id=plan_id,
        source="manual_test",
        parameters={} if parameters is None else parameters,
        routes=routes,
        metrics=None,
    )


def test_minimum_group_report_keeps_candidate_minimum_when_smaller_k_not_excluded():
    k1_over_time = make_plan("k1-over-time", [Route("R1", "O", ["A", "1"], None, None, None)])
    k2_feasible = make_plan(
        "k2-feasible",
        [
            Route("R1", "O", ["A"], None, None, None),
            Route("R2", "O", ["1"], None, None, None),
        ],
    )

    report = decide_minimum_group_count(
        make_network(),
        k_values=(1, 2, 3),
        candidate_plans_by_k={1: [k1_over_time], 2: [k2_feasible]},
        parameters=make_parameters(),
    )

    decisions = {item.group_count: item for item in report.group_decisions}
    assert decisions[1].status == "insufficient_evidence"
    assert decisions[1].best_candidate_time_hour == 7.5
    assert decisions[1].feasible_upper_bound_hour is None
    assert decisions[2].status == "candidate_feasible"
    assert decisions[2].best_candidate_plan_id == "k2-feasible"
    assert decisions[2].feasible_upper_bound_hour == 5.0
    assert decisions[2].gap_hour == 0.0
    assert decisions[3].status == "candidate_not_found"
    assert report.minimum_feasible_k == 2
    assert report.conclusion_status == "incumbent_minimum"
    assert report.recommended_plan_id == "k2-feasible"


def test_report_marks_proven_minimum_when_all_smaller_k_are_excluded():
    k2_feasible = make_plan(
        "k2-feasible",
        [
            Route("R1", "O", ["A", "B"], None, None, None),
            Route("R2", "O", ["C"], None, None, None),
        ],
    )

    report = decide_minimum_group_count(
        make_three_town_network(),
        k_values=(1, 2),
        candidate_plans_by_k={2: [k2_feasible]},
        parameters=make_three_town_parameters(),
    )

    decisions = {item.group_count: item for item in report.group_decisions}
    assert decisions[1].status == "lower_bound_impossible"
    assert decisions[2].status == "candidate_feasible"
    assert report.minimum_feasible_k == 2
    assert report.conclusion_status == "proven_minimum"


def test_lower_bound_impossible_strongly_excludes_k_without_candidates():
    report = decide_minimum_group_count(
        make_network(),
        k_values=(1,),
        candidate_plans_by_k={},
        parameters=make_parameters(time_limit_hour=4.0),
    )

    decision = report.group_decisions[0]
    assert decision.status == "lower_bound_impossible"
    assert decision.lower_bound_status == "lower_bound_impossible"
    assert decision.candidate_records == ()
    assert report.conclusion_status == "no_feasible_candidate"


def test_invalid_candidates_do_not_form_upper_bound():
    invalid_plan = make_plan(
        "invalid-coverage",
        [
            Route("R1", "O", ["A"], None, None, None),
            Route("R2", "O", [], None, None, None),
        ],
    )

    report = decide_minimum_group_count(
        make_network(),
        k_values=(2,),
        candidate_plans_by_k={2: [invalid_plan]},
        parameters=make_parameters(),
    )

    decision = report.group_decisions[0]
    assert decision.status == "candidate_invalid"
    assert decision.candidate_records[0].status == "candidate_invalid"
    assert decision.best_candidate_time_hour is None
    assert decision.feasible_upper_bound_hour is None


def test_group_count_mismatch_is_reported_for_candidate_under_wrong_k():
    mismatch_plan = make_plan("one-route-for-k2", [Route("R1", "O", ["A", "1"], None, None, None)])

    report = decide_minimum_group_count(
        make_network(),
        k_values=(2,),
        candidate_plans_by_k={2: [mismatch_plan]},
        parameters=make_parameters(),
    )

    record = report.group_decisions[0].candidate_records[0]
    assert record.status == "candidate_group_count_mismatch"
    assert "candidate_group_count_mismatch" in record.warnings


def test_duplicate_plan_id_and_parameter_mismatch_are_warnings():
    plan_1 = make_plan(
        "duplicate",
        [Route("R1", "O", ["A"], None, None, None), Route("R2", "O", ["1"], None, None, None)],
        parameters={"speed_km_per_hour": 35.0},
    )
    plan_2 = make_plan(
        "duplicate",
        [Route("R1", "O", ["A"], None, None, None), Route("R2", "O", ["1"], None, None, None)],
    )

    report = decide_minimum_group_count(
        make_network(),
        k_values=(2,),
        candidate_plans_by_k={2: [plan_1, plan_2]},
        parameters=make_parameters(),
    )

    warnings = report.group_decisions[0].candidate_records[0].warnings
    duplicate_warnings = report.group_decisions[0].candidate_records[1].warnings
    assert any("parameter_mismatch" in warning for warning in warnings)
    assert any("duplicate_plan_id" in warning for warning in duplicate_warnings)


def test_json_file_helper_turns_parse_failure_into_invalid_candidate(tmp_path):
    invalid_path = tmp_path / "bad.json"
    invalid_path.write_text("{not json", encoding="utf-8")

    report = decide_minimum_group_count_json_files(
        make_network(),
        k_values=(2,),
        candidate_paths_by_k={2: [invalid_path]},
        parameters=make_parameters(),
    )

    decision = report.group_decisions[0]
    assert decision.status == "candidate_invalid"
    assert decision.candidate_records[0].status == "candidate_invalid"
    assert decision.candidate_records[0].plan_id == "bad"
    assert decision.candidate_records[0].audit_result is None


def test_minimum_group_report_to_dict_and_markdown_are_report_ready():
    feasible_plan = make_plan(
        "k2-feasible",
        [
            Route("R1", "O", ["A"], None, None, None),
            Route("R2", "O", ["1"], None, None, None),
        ],
    )
    report = decide_minimum_group_count(
        make_network(),
        k_values=(2,),
        candidate_plans_by_k={2: [feasible_plan]},
        parameters=make_parameters(),
    )

    report_dict = report.to_dict()
    markdown = minimum_group_report_to_markdown(report)

    assert report_dict["minimum_feasible_k"] == 2
    assert report_dict["group_decisions"][0]["candidate_records"][0]["audit_result"]["plan_id"] == "k2-feasible"
    assert "## Minimum Group Report" in markdown
    assert "candidate_feasible" in markdown
    assert "k2-feasible" in markdown


def test_official_road_network_smoke():
    network_result = load_road_network()

    assert network_result.network is not None

    report = decide_minimum_group_count(
        network_result.network,
        k_values=(1,),
        candidate_plans_by_k={},
    )

    assert len(report.group_decisions) == 1
    assert report.group_decisions[0].lower_bound_hour is not None
