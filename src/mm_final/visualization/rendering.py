"""B8 Matplotlib/ImageIO 渲染与动画导出。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Mapping, Optional, Sequence, Union

from mm_final.network import NodeType, RoadNetwork, classify_node
from mm_final.visualization.layout import RoadNetworkLayout
from mm_final.visualization.timeline import EdgeProgress, RouteAnimationTimeline


DEFAULT_ROUTE_COLORS = (
    "#d62728",
    "#f2c230",
    "#1f77b4",
    "#2ca02c",
    "#9467bd",
    "#ff7f0e",
    "#17becf",
    "#8c564b",
)


@dataclass(frozen=True)
class RenderOptions:
    """Matplotlib 渲染选项。"""

    width_inch: float = 12.0
    height_inch: float = 8.0
    dpi: int = 140
    show_edge_labels: bool = False
    title: Optional[str] = None
    route_colors: tuple[str, ...] = DEFAULT_ROUTE_COLORS


def render_snapshot_png(
    timeline: RouteAnimationTimeline,
    road_network: RoadNetwork,
    layout: RoadNetworkLayout,
    output_path: Union[str, Path],
    *,
    time_hour: Optional[float] = None,
    options: RenderOptions = RenderOptions(),
) -> Path:
    """把某一动画快照渲染为 PNG。"""

    plt = _import_matplotlib_pyplot()
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = timeline.state_at(timeline.completion_time_hour if time_hour is None else time_hour)
    route_colors = _route_color_map(timeline.segments_by_route_id.keys(), options.route_colors)

    fig, ax = plt.subplots(figsize=(options.width_inch, options.height_inch), dpi=options.dpi)
    graph = road_network.to_networkx()
    _draw_base_edges(ax, graph.edges(data=True), layout, options.show_edge_labels)
    _draw_progress_edges(ax, snapshot.traversed_edges, layout, route_colors)
    _draw_nodes(ax, graph.nodes, layout)
    _draw_team_markers(ax, snapshot, layout, route_colors)

    title = options.title or f"{timeline.plan_id}  t={snapshot.time_hour:.2f} h"
    ax.set_title(title)
    ax.set_xlim(-0.04, 1.04)
    ax.set_ylim(1.04, -0.04)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def export_animation_gif(
    timeline: RouteAnimationTimeline,
    road_network: RoadNetwork,
    layout: RoadNetworkLayout,
    output_path: Union[str, Path],
    *,
    fps: int = 10,
    model_hours_per_second: float = 1.0,
    options: RenderOptions = RenderOptions(),
) -> Path:
    """导出 GIF 动画。"""

    return _export_animation(
        timeline,
        road_network,
        layout,
        output_path,
        fps=fps,
        model_hours_per_second=model_hours_per_second,
        options=options,
        kind="gif",
    )


def export_animation_mp4(
    timeline: RouteAnimationTimeline,
    road_network: RoadNetwork,
    layout: RoadNetworkLayout,
    output_path: Union[str, Path],
    *,
    fps: int = 10,
    model_hours_per_second: float = 1.0,
    options: RenderOptions = RenderOptions(),
) -> Path:
    """导出无声 MP4 动画。"""

    return _export_animation(
        timeline,
        road_network,
        layout,
        output_path,
        fps=fps,
        model_hours_per_second=model_hours_per_second,
        options=options,
        kind="mp4",
    )


def _export_animation(
    timeline: RouteAnimationTimeline,
    road_network: RoadNetwork,
    layout: RoadNetworkLayout,
    output_path: Union[str, Path],
    *,
    fps: int,
    model_hours_per_second: float,
    options: RenderOptions,
    kind: str,
) -> Path:
    imageio = _import_imageio()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame_times = _frame_times(timeline.completion_time_hour, fps, model_hours_per_second)

    with tempfile.TemporaryDirectory(prefix="mm-final-b8-frames-") as tmp_dir:
        frame_paths: list[Path] = []
        for index, time_hour in enumerate(frame_times):
            frame_path = Path(tmp_dir) / f"frame-{index:04d}.png"
            render_snapshot_png(
                timeline,
                road_network,
                layout,
                frame_path,
                time_hour=time_hour,
                options=options,
            )
            frame_paths.append(frame_path)

        frames = [imageio.imread(frame_path) for frame_path in frame_paths]
        if kind == "gif":
            imageio.mimsave(output, frames, duration=1000 / fps)
        else:
            imageio.mimsave(output, frames, fps=fps, macro_block_size=1)

    return output


def _frame_times(completion_time_hour: float, fps: int, model_hours_per_second: float) -> list[float]:
    if fps <= 0:
        raise ValueError("fps must be > 0.")
    if model_hours_per_second <= 0:
        raise ValueError("model_hours_per_second must be > 0.")
    duration_second = max(completion_time_hour / model_hours_per_second, 0.1)
    frame_count = max(2, int(duration_second * fps) + 1)
    if frame_count == 2:
        return [0.0, completion_time_hour]
    return [completion_time_hour * index / (frame_count - 1) for index in range(frame_count)]


def _draw_base_edges(ax, edges: Sequence[tuple[str, str, Mapping[str, object]]], layout: RoadNetworkLayout, show_labels: bool) -> None:
    for source, target, data in edges:
        source_node = layout.require_node(source)
        target_node = layout.require_node(target)
        ax.plot([source_node.x, target_node.x], [source_node.y, target_node.y], color="#2f2f2f", linewidth=1.2, alpha=0.55)
        if show_labels:
            ax.text(
                (source_node.x + target_node.x) / 2,
                (source_node.y + target_node.y) / 2,
                f"{float(data['weight']):.1f}",
                fontsize=6,
                color="#333333",
            )


def _draw_progress_edges(
    ax,
    progress_items: Sequence[EdgeProgress],
    layout: RoadNetworkLayout,
    route_colors: Mapping[str, str],
) -> None:
    for item in progress_items:
        source = layout.require_node(item.source)
        target = layout.require_node(item.target)
        end_x = source.x + (target.x - source.x) * item.progress
        end_y = source.y + (target.y - source.y) * item.progress
        ax.plot(
            [source.x, end_x],
            [source.y, end_y],
            color=route_colors[item.route_id],
            linewidth=3.0,
            alpha=0.85,
        )


def _draw_nodes(ax, nodes: Sequence[str], layout: RoadNetworkLayout) -> None:
    for node in nodes:
        point = layout.require_node(node)
        marker, color, size = _node_style(node)
        ax.scatter([point.x], [point.y], marker=marker, s=size, color=color, edgecolors="#222222", linewidths=0.4, zorder=5)
        ax.text(point.x + 0.006, point.y - 0.006, node, fontsize=7, color="#111111", zorder=6)


def _draw_team_markers(ax, snapshot, layout: RoadNetworkLayout, route_colors: Mapping[str, str]) -> None:
    for state in snapshot.team_states:
        color = route_colors[state.route_id]
        if state.edge is not None:
            source = layout.require_node(state.edge[0])
            target = layout.require_node(state.edge[1])
            x = source.x + (target.x - source.x) * state.edge_progress
            y = source.y + (target.y - source.y) * state.edge_progress
        else:
            node = layout.require_node(state.current_node or "O")
            x, y = node.x, node.y
        ax.scatter([x], [y], marker="o", s=62, color=color, edgecolors="#ffffff", linewidths=1.0, zorder=8)


def _node_style(node: str) -> tuple[str, str, int]:
    node_type = classify_node(node)
    if node == "O":
        return ("*", "#f4b000", 110)
    if node_type is NodeType.TOWN:
        return ("s", "#5DA5DA", 42)
    if node_type is NodeType.VILLAGE:
        return ("o", "#F15854", 30)
    return ("x", "#777777", 24)


def _route_color_map(route_ids, colors: tuple[str, ...]) -> dict[str, str]:
    return {route_id: colors[index % len(colors)] for index, route_id in enumerate(route_ids)}


def _import_matplotlib_pyplot():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - 依赖由 viz extra 提供
        raise ImportError("Matplotlib is required for B8 rendering. Install the 'viz' extra.") from exc
    return plt


def _import_imageio():
    try:
        import imageio.v2 as imageio
    except ImportError as exc:  # pragma: no cover - 依赖由 viz extra 提供
        raise ImportError("ImageIO is required for GIF/MP4 export. Install the 'viz' extra.") from exc
    return imageio
