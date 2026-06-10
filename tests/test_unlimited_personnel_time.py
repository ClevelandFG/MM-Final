import networkx as nx

from mm_final.contracts import Route, RoutePlan
from mm_final.evaluation import (
    UnlimitedPersonnelParameters,
    analyze_unlimited_personnel_time,
    analyze_unlimited_personnel_time_json_files,
    build_singleton_certificate_plan,
    unlimited_personnel_report_to_markdown,
)
from mm_final.network import RoadNetwork, load_road_network


def make_network():
    graph = nx.Graph()
    graph.add_edge("O", "A", weight=1.0)
    graph.add_edge("O", "B", weight=1.0)
    graph.add_edge("A", "B", weight=1.0)
    graph.add_edge("O", "1", weight=20.0)
    return RoadNetwork(graph)


def make_parameters(time_limit_hour=24.0):
    return UnlimitedPersonnelParameters(
        T_hour=2.0,
        t_hour=1.0,
        speed_km_per_hour=10.0,
        time_limit_hour=time_limit_hour,
        required_visit_nodes=frozenset(("A", "B", "1")),
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


def test_singleton_certificate_proves_shortest_time_without_candidates():
    report = analyze_unlimited_personnel_time(
        make_network(),
        candidate_plans=(),
        parameters=make_parameters(),
    )

    assert report.conclusion_status == "proven_shortest_time"
    assert report.shortest_time_lower_bound_hour == 5.0
    assert report.best_completion_time_hour == 5.0
    assert report.gap_hour == 0.0
    assert report.recommended_plan_id == "singleton-certificate"
    assert report.recommended_status == "singleton_certificate"
    assert report.candidate_records[0].status == "singleton_certificate"
    assert report.candidate_records[0].group_count == 3


def test_equal_shortest_candidate_with_fewer_groups_beats_singleton_baseline():
    candidate = make_plan(
        "two-route-optimal",
        [
            Route("R1", "O", ["A", "B"], None, None, None),
            Route("R2", "O", ["1"], None, None, None),
        ],
    )

    report = analyze_unlimited_personnel_time(
        make_network(),
        candidate_plans=(candidate,),
        parameters=make_parameters(),
    )

    records_by_plan_id = {record.plan_id: record for record in report.candidate_records}
    assert records_by_plan_id["two-route-optimal"].status == "optimal_time_candidate"
    assert records_by_plan_id["two-route-optimal"].completion_time_hour == 5.0
    assert report.recommended_plan_id == "two-route-optimal"
    assert report.recommended_status == "optimal_time_candidate"


def test_valid_slower_candidate_is_not_recommended_over_singleton_certificate():
    slower = make_plan("slower", [Route("R1", "O", ["A", "B", "1"], None, None, None)])

    report = analyze_unlimited_personnel_time(
        make_network(),
        candidate_plans=(slower,),
        parameters=make_parameters(),
    )

    records_by_plan_id = {record.plan_id: record for record in report.candidate_records}
    assert records_by_plan_id["slower"].status == "valid_slower_candidate"
    assert records_by_plan_id["slower"].completion_time_hour > report.shortest_time_lower_bound_hour
    assert report.recommended_plan_id == "singleton-certificate"


def test_24_hour_limit_is_not_a_b6_legality_gate():
    candidate = make_plan(
        "two-route-optimal",
        [
            Route("R1", "O", ["A", "B"], None, None, None),
            Route("R2", "O", ["1"], None, None, None),
        ],
    )

    report = analyze_unlimited_personnel_time(
        make_network(),
        candidate_plans=(candidate,),
        parameters=make_parameters(time_limit_hour=1.0),
    )

    record = [item for item in report.candidate_records if item.plan_id == "two-route-optimal"][0]
    assert record.status == "optimal_time_candidate"
    assert record.is_within_time_limit is False
    assert report.recommended_plan_id == "two-route-optimal"


def test_invalid_candidate_and_parameter_mismatch_are_reported():
    invalid = make_plan(
        "invalid",
        [Route("R1", "O", ["A", "B"], None, None, None)],
        parameters={"speed_km_per_hour": 35.0},
    )

    report = analyze_unlimited_personnel_time(
        make_network(),
        candidate_plans=(invalid,),
        parameters=make_parameters(),
    )

    record = [item for item in report.candidate_records if item.plan_id == "invalid"][0]
    assert record.status == "candidate_invalid"
    assert any("parameter_mismatch" in warning for warning in record.warnings)


def test_json_file_helper_turns_parse_failure_into_parse_failed_record(tmp_path):
    invalid_path = tmp_path / "bad.json"
    invalid_path.write_text("{not json", encoding="utf-8")

    report = analyze_unlimited_personnel_time_json_files(
        make_network(),
        candidate_paths=(invalid_path,),
        parameters=make_parameters(),
    )

    record = [item for item in report.candidate_records if item.plan_id == "bad"][0]
    assert record.status == "parse_failed"
    assert record.audit_result is None


def test_singleton_certificate_plan_helper_builds_route_plan():
    plan = build_singleton_certificate_plan(parameters=make_parameters())

    assert plan.plan_id == "singleton-certificate"
    assert len(plan.routes) == 3
    assert {tuple(route.required_visit_order) for route in plan.routes} == {("A",), ("B",), ("1",)}


def test_unlimited_personnel_report_to_dict_and_markdown_are_report_ready():
    report = analyze_unlimited_personnel_time(
        make_network(),
        candidate_plans=(),
        parameters=make_parameters(),
    )

    report_dict = report.to_dict()
    markdown = unlimited_personnel_report_to_markdown(report)

    assert report_dict["conclusion_status"] == "proven_shortest_time"
    assert report_dict["recommended_plan_id"] == "singleton-certificate"
    assert "## Unlimited Personnel Time Report" in markdown
    assert "proven_shortest_time" in markdown
    assert "singleton-certificate" in markdown


def test_official_road_network_smoke():
    network_result = load_road_network()

    assert network_result.network is not None

    report = analyze_unlimited_personnel_time(network_result.network, candidate_plans=())

    assert report.conclusion_status == "proven_shortest_time"
    assert report.shortest_time_lower_bound_hour > 0
    assert report.gap_hour == 0.0
