import json
from pathlib import Path

import networkx as nx
import pytest

from apps.gui.route_animation_player import main as route_animation_player_main
from mm_final.contracts import Route, RoutePlan
from mm_final.evaluation import EvaluationParameters
from mm_final.network import RoadNetwork
from mm_final.visualization import (
    LayoutNode,
    RoadNetworkLayout,
    RouteAnimationTimeline,
    build_route_animation_bundle,
    export_animation_gif,
    export_animation_mp4,
    export_route_animation_package,
    render_snapshot_png,
)
from mm_final.visualization.exports import VisualizationInputError


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "route_plans"


def make_network() -> RoadNetwork:
    graph = nx.Graph()
    graph.add_edge("O", "A", weight=10.0)
    graph.add_edge("A", "1", weight=5.0)
    graph.add_edge("1", "O", weight=15.0)
    return RoadNetwork(graph)


def make_parameters() -> EvaluationParameters:
    return EvaluationParameters(
        T_hour=2.0,
        t_hour=1.0,
        speed_km_per_hour=10.0,
        time_limit_hour=24.0,
        required_visit_nodes=frozenset(("A", "1")),
    )


def make_plan(expanded_node_path=None) -> RoutePlan:
    return RoutePlan(
        schema_version="route-plan-v1",
        plan_id="viz-small",
        source="manual_fixture",
        parameters={
            "T_hour": 2.0,
            "t_hour": 1.0,
            "speed_km_per_hour": 10.0,
            "time_limit_hour": 24.0,
        },
        routes=[Route("R1", "O", ["A", "1"], expanded_node_path, None, None)],
        metrics=None,
    )


def make_layout() -> RoadNetworkLayout:
    return RoadNetworkLayout(
        layout_id="small",
        coordinate_system={"type": "normalized_image"},
        source={"method": "test"},
        nodes={
            "O": LayoutNode(0.0, 0.0),
            "A": LayoutNode(1.0, 0.0),
            "1": LayoutNode(1.0, 1.0),
        },
    )


def test_route_animation_timeline_interpolates_travel_stop_and_completion():
    timeline = RouteAnimationTimeline.from_route_plan(make_plan(), make_network(), make_parameters())

    assert timeline.completion_time_hour == pytest.approx(6.0)
    assert len(timeline.segments_by_route_id["R1"]) == 5

    traveling = timeline.state_at(0.5).team_states[0]
    assert traveling.status == "traveling"
    assert traveling.edge == ("O", "A")
    assert traveling.edge_progress == pytest.approx(0.5)

    stopping = timeline.state_at(2.0).team_states[0]
    assert stopping.status == "stopping"
    assert stopping.current_node == "A"

    partial_next_edge = timeline.state_at(3.25)
    assert partial_next_edge.team_states[0].edge == ("A", "1")
    assert partial_next_edge.team_states[0].edge_progress == pytest.approx(0.5)
    assert any(item.source == "A" and item.target == "1" for item in partial_next_edge.traversed_edges)

    finished = timeline.state_at(99.0).team_states[0]
    assert finished.status == "finished"
    assert finished.current_node == "O"


def test_route_animation_map_speed_uses_layout_distance_over_edge_weight():
    timeline = RouteAnimationTimeline.from_route_plan(make_plan(), make_network(), make_parameters())
    layout = make_layout()
    first_edge = timeline.segments_by_route_id["R1"][0]
    source = layout.require_node(first_edge.source)
    target = layout.require_node(first_edge.target)
    layout_distance = ((target.x - source.x) ** 2 + (target.y - source.y) ** 2) ** 0.5
    expected_map_speed = make_parameters().speed_km_per_hour * layout_distance / first_edge.distance_km

    start = timeline.state_at(0.25).team_states[0]
    end = timeline.state_at(0.75).team_states[0]
    observed_map_distance = (end.edge_progress - start.edge_progress) * layout_distance

    assert start.edge == ("O", "A")
    assert end.edge == ("O", "A")
    assert observed_map_distance / 0.5 == pytest.approx(expected_map_speed)


def test_build_bundle_rejects_old_contract_path_in_formal_mode():
    plan = make_plan(expanded_node_path=["O", "U01", "A", "1", "O"])

    with pytest.raises(VisualizationInputError) as exc_info:
        build_route_animation_bundle(plan, make_network(), parameters=make_parameters(), layout=make_layout())

    assert exc_info.value.audit_result is not None
    assert not exc_info.value.audit_result.route_valid
    assert any("expanded_path_edge_missing" in error for error in exc_info.value.audit_result.errors)


def test_export_route_animation_package_writes_version_locked_metadata(tmp_path):
    result = export_route_animation_package(
        FIXTURE_DIR / "full-coverage-smoke-001.json",
        tmp_path,
        render_frames=False,
    )

    assert (tmp_path / "README.md").exists()
    assert (tmp_path / "route-summary.csv").exists()
    summary = json.loads((tmp_path / "timeline-summary.json").read_text(encoding="utf-8"))
    assert summary["formal_result"] is True
    assert summary["data_version"]["route_plan_contract_version"] == "route-plan-v1"
    assert len(summary["data_version"]["road_network_sha256"]) == 64
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "git_commit" in readme
    assert "road_network_sha256" in readme


def test_route_animation_player_entrypoint_exports_without_running_a_line(tmp_path):
    exit_code = route_animation_player_main(
        [
            str(FIXTURE_DIR / "full-coverage-smoke-001.json"),
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "README.md").exists()


def test_render_snapshot_png_smoke_when_viz_extra_is_installed(tmp_path):
    pytest.importorskip("matplotlib")
    timeline = RouteAnimationTimeline.from_route_plan(make_plan(), make_network(), make_parameters())

    output = render_snapshot_png(timeline, make_network(), make_layout(), tmp_path / "frame.png", time_hour=3.25)

    assert output.exists()
    assert output.stat().st_size > 0


def test_gif_and_mp4_export_smoke_when_viz_extra_is_installed(tmp_path):
    pytest.importorskip("matplotlib")
    pytest.importorskip("imageio")
    timeline = RouteAnimationTimeline.from_route_plan(make_plan(), make_network(), make_parameters())

    gif_path = export_animation_gif(
        timeline,
        make_network(),
        make_layout(),
        tmp_path / "route.gif",
        fps=1,
        model_hours_per_second=6.0,
    )
    mp4_path = export_animation_mp4(
        timeline,
        make_network(),
        make_layout(),
        tmp_path / "route.mp4",
        fps=1,
        model_hours_per_second=6.0,
    )

    assert gif_path.exists()
    assert gif_path.stat().st_size > 0
    assert mp4_path.exists()
    assert mp4_path.stat().st_size > 0
