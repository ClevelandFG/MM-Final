"""B8 可视化布局读取与兜底生成。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Mapping, Optional, Union

import networkx as nx

from mm_final.network import RoadNetwork


DEFAULT_LAYOUT_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "processed" / "road_network_layout" / "original-map-layout.json"
)


@dataclass(frozen=True)
class LayoutNode:
    """归一化布局坐标。"""

    x: float
    y: float
    source_pixel: Optional[tuple[int, int]] = None


@dataclass(frozen=True)
class RoadNetworkLayout:
    """仅用于绘图的节点二维布局，不参与距离计算。"""

    layout_id: str
    coordinate_system: Mapping[str, object]
    source: Mapping[str, object]
    nodes: Mapping[str, LayoutNode]

    def require_node(self, node: str) -> LayoutNode:
        try:
            return self.nodes[node]
        except KeyError as exc:
            raise KeyError(f"Layout does not contain node {node!r}.") from exc

    def to_dict(self) -> dict[str, object]:
        return {
            "layout_id": self.layout_id,
            "coordinate_system": dict(self.coordinate_system),
            "source": dict(self.source),
            "nodes": {
                node: {
                    "x": value.x,
                    "y": value.y,
                    "source_pixel": None if value.source_pixel is None else list(value.source_pixel),
                }
                for node, value in self.nodes.items()
            },
        }


def load_layout_json(path: Union[str, Path] = DEFAULT_LAYOUT_PATH) -> RoadNetworkLayout:
    """读取半手工标注的 layout JSON。"""

    layout_path = Path(path)
    with layout_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    nodes: dict[str, LayoutNode] = {}
    for node, value in raw["nodes"].items():
        pixel = value.get("source_pixel")
        nodes[node] = LayoutNode(
            x=float(value["x"]),
            y=float(value["y"]),
            source_pixel=None if pixel is None else (int(pixel[0]), int(pixel[1])),
        )

    return RoadNetworkLayout(
        layout_id=str(raw.get("layout_id", layout_path.stem)),
        coordinate_system=dict(raw.get("coordinate_system", {})),
        source=dict(raw.get("source", {})),
        nodes=nodes,
    )


def make_fallback_layout(road_network: RoadNetwork, *, seed: int = 20260613) -> RoadNetworkLayout:
    """在缺少人工 layout 时生成稳定自动布局。"""

    graph = road_network.to_networkx()
    positions = nx.spring_layout(graph, seed=seed, weight="weight")
    xs = [float(point[0]) for point in positions.values()]
    ys = [float(point[1]) for point in positions.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)

    nodes = {
        node: LayoutNode(
            x=(float(point[0]) - min_x) / span_x,
            y=(float(point[1]) - min_y) / span_y,
        )
        for node, point in positions.items()
    }
    return RoadNetworkLayout(
        layout_id=f"fallback-spring-seed-{seed}",
        coordinate_system={"type": "normalized_auto", "origin": "top_left"},
        source={"method": "networkx.spring_layout", "seed": seed},
        nodes=nodes,
    )
