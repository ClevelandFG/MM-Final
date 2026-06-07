"""必访节点距离闭包与路线展开路径。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from mm_final.network import DEPOT, REQUIRED_VISIT_NODES, RoadNetwork, ShortestPath


@dataclass(frozen=True)
class RoutePath:
    distance_km: float
    expanded_node_path: tuple[str, ...]


@dataclass(frozen=True)
class DistanceMatrix:
    paths: Mapping[tuple[str, str], ShortestPath]
    nodes: tuple[str, ...]

    @classmethod
    def from_network(
        cls,
        network: RoadNetwork,
        nodes: Iterable[str] = REQUIRED_VISIT_NODES,
        *,
        depot: str = DEPOT,
    ) -> "DistanceMatrix":
        matrix_nodes = tuple(dict.fromkeys((depot,) + tuple(nodes)))
        paths: dict[tuple[str, str], ShortestPath] = {}

        for source in matrix_nodes:
            for target in matrix_nodes:
                paths[(source, target)] = (
                    ShortestPath(distance_km=0.0, node_path=(source,))
                    if source == target
                    else network.shortest_path(source, target)
                )

        return cls(paths=paths, nodes=matrix_nodes)

    def distance_km(self, source: str, target: str) -> float:
        return self.paths[(source, target)].distance_km

    def node_path(self, source: str, target: str) -> tuple[str, ...]:
        return self.paths[(source, target)].node_path

    def route_path(self, required_visit_order: Iterable[str], *, depot: str = DEPOT) -> RoutePath:
        stops = tuple(required_visit_order)
        if not stops:
            return RoutePath(distance_km=0.0, expanded_node_path=(depot,))

        checkpoints = (depot,) + stops + (depot,)
        total_distance = 0.0
        expanded_path: list[str] = []

        for index, (source, target) in enumerate(zip(checkpoints, checkpoints[1:])):
            segment = self.paths[(source, target)]
            total_distance += segment.distance_km
            expanded_path.extend(segment.node_path if index == 0 else segment.node_path[1:])

        return RoutePath(distance_km=total_distance, expanded_node_path=tuple(expanded_path))
