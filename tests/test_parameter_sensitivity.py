from pathlib import Path

import networkx as nx

from mm_final.contracts import Route, RoutePlan
from mm_final.evaluation import (
    ParameterScenario,
    analyze_parameter_sensitivity,
    analyze_parameter_sensitivity_json_files,
    default_parameter_scenarios,
    load_parameter_scenarios_json,
    sensitivity_report_to_markdown,
)
from mm_final.network import RoadNetwork, load_road_network


def make_network():
    graph = nx.Graph()
    graph.add_edge("O", "A", weight=1.0)
    graph.add_edge("O", "B", weight=1.0)
    graph.add_edge("A", "B", weight=1.0)
    graph.add_edge("O", "1", weight=10.0)
    return RoadNetwork(graph)


def make_scenario(scenario_id, *, T_hour=2.0, t_hour=1.0, speed=10.0, time_limit=24.0):
    return ParameterScenario(
        scenario_id=scenario_id,
        T_hour=T_hour,
        t_hour=t_hour,
        speed_km_per_hour=speed,
        time_limit_hour=time_limit,
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


def town_pair_plan(plan_id="town-pair", parameters=None):
    return make_plan(
        plan_id,
        [
            Route("R1", "O", ["A", "B"], None, None, None),
            Route("R2", "O", ["1"], None, None, None),
        ],
        parameters=parameters,
    )


def mixed_plan(plan_id="mixed"):
    return make_plan(
        plan_id,
        [
            Route("R1", "O", ["A"], None, None, None),
            Route("R2", "O", ["B", "1"], None, None, None),
        ],
    )


def records_by_scenario_and_plan(report):
    return {
        (record.scenario_id, record.plan_id): record
        for record in report.candidate_records
    }


def summaries_by_scenario(report):
    return {summary.scenario_id: summary for summary in report.scenario_summaries}


def test_parameter_sensitivity_ranks_candidates_and_detects_winner_change():
    report = analyze_parameter_sensitivity(
        make_network(),
        candidate_plans=(town_pair_plan(), mixed_plan()),
        scenarios=(
            make_scenario("baseline"),
            make_scenario("T_high", T_hour=4.0),
        ),
        include_unlimited_personnel_summary=False,
    )

    summaries = summaries_by_scenario(report)
    records = records_by_scenario_and_plan(report)

    assert summaries["baseline"].recommended_plan_id == "town-pair"
    assert summaries["baseline"].conclusion_status == "best_in_pool"
    assert records[("baseline", "town-pair")].completion_time_hour == 4.3
    assert records[("baseline", "town-pair")].rank == 1

    assert summaries["T_high"].recommended_plan_id == "mixed"
    assert summaries["T_high"].conclusion_status == "needs_reoptimization"
    assert "candidate_winner_changed" in summaries["T_high"].reoptimization_reasons
    assert records[("T_high", "mixed")].rank == 1
    assert records[("T_high", "mixed")].baseline_rank == 2
    assert records[("T_high", "mixed")].rank_delta == -1


def test_bottleneck_change_and_route_breakdown_are_recorded():
    report = analyze_parameter_sensitivity(
        make_network(),
        candidate_plans=(town_pair_plan(),),
        scenarios=(
            make_scenario("baseline"),
            make_scenario("t_high", t_hour=4.0),
        ),
        include_unlimited_personnel_summary=False,
        time_range_threshold_hour=10.0,
    )

    records = records_by_scenario_and_plan(report)
    baseline = records[("baseline", "town-pair")]
    t_high = records[("t_high", "town-pair")]

    assert baseline.bottleneck_route_ids == ("R1",)
    assert t_high.bottleneck_route_ids == ("R2",)
    assert t_high.bottleneck_changed_from_baseline is True
    assert "bottleneck_changed" in summaries_by_scenario(report)["t_high"].reoptimization_reasons

    breakdowns = {item.route_id: item for item in baseline.route_breakdowns}
    assert breakdowns["R1"].town_stop_time_hour == 4.0
    assert breakdowns["R1"].travel_time_hour == 0.3
    assert breakdowns["R1"].town_stop_share > breakdowns["R1"].travel_share


def test_invalid_candidate_and_parameter_mismatch_are_reported():
    invalid = make_plan(
        "invalid",
        [Route("R1", "O", ["A", "B"], None, None, None)],
        parameters={"speed_km_per_hour": 99.0},
    )

    report = analyze_parameter_sensitivity(
        make_network(),
        candidate_plans=(invalid,),
        scenarios=(make_scenario("baseline"),),
        include_unlimited_personnel_summary=False,
    )

    record = report.candidate_records[0]
    assert record.status == "candidate_invalid"
    assert not record.is_final_valid
    assert any("missing_required_nodes" in error for error in record.audit_result.errors)
    assert any("parameter_mismatch" in warning for warning in record.warnings)
    assert summaries_by_scenario(report)["baseline"].conclusion_status == "no_valid_candidate"


def test_json_file_helper_turns_parse_failure_into_record(tmp_path):
    invalid_path = tmp_path / "bad.json"
    invalid_path.write_text("{not json", encoding="utf-8")

    report = analyze_parameter_sensitivity_json_files(
        make_network(),
        candidate_paths=(invalid_path,),
        scenarios=(make_scenario("baseline"),),
        include_unlimited_personnel_summary=False,
    )

    record = report.candidate_records[0]
    assert record.plan_id == "bad"
    assert record.status == "parse_failed"
    assert record.audit_result is None


def test_parameter_scenario_json_helper_loads_independent_config(tmp_path):
    scenario_path = tmp_path / "scenarios.json"
    scenario_path.write_text(
        """
        {
          "scenarios": [
            {
              "scenario_id": "custom",
              "T_hour": 3.0,
              "t_hour": 1.5,
              "speed_km_per_hour": 12.0,
              "required_visit_nodes": ["A", "B", "1"]
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    scenarios = load_parameter_scenarios_json(scenario_path)

    assert scenarios == (
        ParameterScenario(
            "custom",
            T_hour=3.0,
            t_hour=1.5,
            speed_km_per_hour=12.0,
            required_visit_nodes=frozenset(("A", "B", "1")),
        ),
    )


def test_unlimited_personnel_summary_is_available_by_default():
    report = analyze_parameter_sensitivity(
        make_network(),
        candidate_plans=(town_pair_plan(),),
        scenarios=(make_scenario("baseline"),),
    )

    summary = report.scenario_summaries[0]
    assert summary.unlimited_personnel_report is not None
    assert summary.unlimited_personnel_report.conclusion_status == "proven_shortest_time"
    assert summary.unlimited_personnel_report.shortest_time_lower_bound_hour == 3.0


def test_optional_minimum_group_summary_can_prove_scenario_candidate():
    report = analyze_parameter_sensitivity(
        make_network(),
        candidate_plans=(town_pair_plan(),),
        scenarios=(make_scenario("baseline", time_limit=4.5),),
        minimum_group_k_values=(1, 2),
        include_unlimited_personnel_summary=False,
    )

    summary = report.scenario_summaries[0]
    assert summary.minimum_group_report is not None
    assert summary.minimum_group_report.conclusion_status == "proven_minimum"
    assert summary.conclusion_status == "proven_by_b5_or_b6"


def test_report_to_dict_markdown_and_table_rows_are_report_ready():
    report = analyze_parameter_sensitivity(
        make_network(),
        candidate_plans=(town_pair_plan(), mixed_plan()),
        scenarios=(
            make_scenario("baseline"),
            make_scenario("T_high", T_hour=4.0),
        ),
        include_unlimited_personnel_summary=False,
    )

    report_dict = report.to_dict()
    markdown = sensitivity_report_to_markdown(report)
    rows = report.to_table_rows()

    assert report_dict["baseline_scenario_id"] == "baseline"
    assert report_dict["scenario_summaries"][1]["recommended_plan_id"] == "mixed"
    assert "## Parameter Sensitivity Report" in markdown
    assert "candidate_winner_changed" in markdown
    assert rows[0]["scenario_id"] == "baseline"
    assert rows[0]["plan_id"] == "town-pair"


def test_default_parameter_scenarios_are_one_factor_perturbations():
    scenarios = default_parameter_scenarios(required_visit_nodes=frozenset(("A", "B", "1")))
    scenario_ids = {scenario.scenario_id for scenario in scenarios}

    assert "baseline" in scenario_ids
    assert "T_high" in scenario_ids
    assert "t_low" in scenario_ids
    assert "v_high" in scenario_ids
    assert all(scenario.required_visit_nodes == frozenset(("A", "B", "1")) for scenario in scenarios)


def test_official_road_network_smoke():
    network_result = load_road_network()

    assert network_result.network is not None

    report = analyze_parameter_sensitivity(
        network_result.network,
        candidate_plans=(),
        include_unlimited_personnel_summary=False,
    )

    assert len(report.scenario_summaries) == len(default_parameter_scenarios())
    assert report.scenario_summaries[0].conclusion_status == "no_valid_candidate"
    assert "candidate_pool_empty" in report.warnings
