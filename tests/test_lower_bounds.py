import networkx as nx

from mm_final.evaluation import (
    LowerBoundParameters,
    compute_lower_bound_report,
    default_k_values,
    lower_bound_report_to_markdown,
)
from mm_final.network import RoadNetwork, load_road_network


def make_network():
    graph = nx.Graph()
    graph.add_edge("O", "A", weight=10.0)
    graph.add_edge("O", "1", weight=20.0)
    graph.add_edge("A", "1", weight=50.0)
    return RoadNetwork(graph)


def make_parameters(time_limit_hour=6.0):
    return LowerBoundParameters(
        T_hour=2.0,
        t_hour=1.0,
        speed_km_per_hour=10.0,
        time_limit_hour=time_limit_hour,
        required_visit_nodes=frozenset(("A", "1")),
        farthest_node_count=2,
        distance_tier_count=2,
    )


def test_compute_lower_bound_report_uses_stop_and_single_node_bounds():
    report = compute_lower_bound_report(make_network(), k_values=(1, 2), parameters=make_parameters())

    assert report.total_stop_time_hour == 3.0
    assert report.minimum_group_count_by_stop_time == 1
    assert report.max_single_node == "1"
    assert report.max_single_node_round_trip_hour == 5.0
    assert report.unlimited_personnel_lower_bound_hour == 5.0

    bounds_by_k = {item.group_count: item for item in report.group_bounds}
    assert bounds_by_k[1].lower_bound_hour == 5.0
    assert bounds_by_k[1].status == "not_excluded"
    assert bounds_by_k[2].lower_bound_hour == 5.0
    assert bounds_by_k[2].status == "not_excluded"
    assert not any(code.startswith("collection_load_distance_tier") for code in bounds_by_k[1].active_bound_codes)

    assert any(item.strength == "strict/provable" for item in report.bound_entries)
    assert any(item.strength == "screening_only" for item in report.bound_entries)


def test_group_status_marks_lower_bound_impossible():
    report = compute_lower_bound_report(
        make_network(),
        k_values=(1,),
        parameters=make_parameters(time_limit_hour=4.0),
    )

    assert report.group_bounds[0].lower_bound_hour == 5.0
    assert report.group_bounds[0].status == "lower_bound_impossible"


def test_default_k_values_uses_required_node_count():
    params = make_parameters()

    assert default_k_values(params.required_visit_nodes) == (1, 2)


def test_lower_bound_report_to_dict_and_markdown_are_report_ready():
    report = compute_lower_bound_report(
        make_network(),
        k_values=(1,),
        parameters=make_parameters(time_limit_hour=4.0),
    )

    report_dict = report.to_dict()
    markdown = lower_bound_report_to_markdown(report)

    assert report_dict["parameters"]["required_visit_nodes"] == ["A", "1"]
    assert report_dict["group_bounds"][0]["status"] == "lower_bound_impossible"
    assert "## Lower Bound Report" in markdown
    assert "lower_bound_impossible" in markdown
    assert "strict/provable" in markdown


def test_official_road_network_smoke():
    network_result = load_road_network()

    assert network_result.network is not None

    report = compute_lower_bound_report(network_result.network, k_values=(1, 2, 3))

    assert len(report.group_bounds) == 3
    assert report.minimum_group_count_by_stop_time >= 1
    assert report.unlimited_personnel_lower_bound_hour > 0
