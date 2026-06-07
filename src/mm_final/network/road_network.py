"""道路网络 TSV 读取与基础校验。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
from typing import Iterable, Optional, Union

import networkx as nx
from networkx import NetworkXNoPath, NodeNotFound

from mm_final.network.nodes import ALL_KNOWN_NODES, REQUIRED_VISIT_NODES


DEFAULT_ROAD_NETWORK_PATH = Path(__file__).resolve().parents[3] / "data" / "raw" / "road_network.tsv"
EXPECTED_HEADER = ["source", "target", "weight"]


@dataclass(frozen=True)
class NetworkDiagnostic:
    severity: str
    code: str
    path: str
    message: str

    def to_text(self) -> str:
        return f"{self.code} at {self.path}: {self.message}"


@dataclass(frozen=True)
class ShortestPath:
    distance_km: float
    node_path: tuple[str, ...]


@dataclass(frozen=True)
class RoadNetwork:
    _graph: nx.Graph

    @property
    def node_count(self) -> int:
        return self._graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self._graph.number_of_edges()

    @property
    def nodes(self) -> frozenset[str]:
        return frozenset(self._graph.nodes)

    @property
    def edges(self) -> frozenset[frozenset[str]]:
        return frozenset(frozenset((source, target)) for source, target in self._graph.edges)

    def has_edge(self, source: str, target: str) -> bool:
        return self._graph.has_edge(source, target)

    def edge_weight_km(self, source: str, target: str) -> float:
        return float(self._graph[source][target]["weight"])

    def shortest_path(self, source: str, target: str) -> ShortestPath:
        try:
            node_path = tuple(nx.shortest_path(self._graph, source, target, weight="weight"))
        except (NodeNotFound, NetworkXNoPath) as exc:
            raise ValueError(f"No shortest path from {source!r} to {target!r}.") from exc

        distance = float(nx.shortest_path_length(self._graph, source, target, weight="weight"))
        return ShortestPath(distance_km=distance, node_path=node_path)

    def to_networkx(self) -> nx.Graph:
        return self._graph.copy()


@dataclass(frozen=True)
class RoadNetworkLoadResult:
    network: Optional[RoadNetwork]
    diagnostics: list[NetworkDiagnostic]

    @property
    def errors(self) -> list[NetworkDiagnostic]:
        return [item for item in self.diagnostics if item.severity == "error"]

    @property
    def warnings(self) -> list[NetworkDiagnostic]:
        return [item for item in self.diagnostics if item.severity == "warning"]

    @property
    def is_valid(self) -> bool:
        return self.network is not None and not self.errors


def load_road_network(path: Optional[Union[str, Path]] = None) -> RoadNetworkLoadResult:
    return validate_road_network_tsv(DEFAULT_ROAD_NETWORK_PATH if path is None else path)


def validate_road_network_tsv(path: Union[str, Path]) -> RoadNetworkLoadResult:
    tsv_path = Path(path)
    diagnostics: list[NetworkDiagnostic] = []
    graph = nx.Graph()
    seen_edges: set[frozenset[str]] = set()

    try:
        with tsv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if reader.fieldnames != EXPECTED_HEADER:
                return RoadNetworkLoadResult(
                    network=None,
                    diagnostics=[
                        _error(
                            "header",
                            "invalid_header",
                            f"TSV header must be {EXPECTED_HEADER!r}.",
                        )
                    ],
                )
            for row_number, row in enumerate(reader, start=2):
                _read_edge_row(row, row_number, graph, seen_edges, diagnostics)
    except FileNotFoundError:
        return RoadNetworkLoadResult(
            network=None,
            diagnostics=[_error(str(tsv_path), "file_not_found", "Road network TSV does not exist.")],
        )

    _validate_required_nodes_present(graph.nodes, diagnostics)
    _validate_connectivity(graph, diagnostics)

    return RoadNetworkLoadResult(
        network=None if [item for item in diagnostics if item.severity == "error"] else RoadNetwork(graph),
        diagnostics=diagnostics,
    )


def _read_edge_row(
    row: dict[str, str],
    row_number: int,
    graph: nx.Graph,
    seen_edges: set[frozenset[str]],
    diagnostics: list[NetworkDiagnostic],
) -> None:
    source = row["source"]
    target = row["target"]
    row_path = f"row[{row_number}]"

    if source not in ALL_KNOWN_NODES:
        diagnostics.append(_error(f"{row_path}.source", "unknown_node", f"Unknown node {source!r}."))
    if target not in ALL_KNOWN_NODES:
        diagnostics.append(_error(f"{row_path}.target", "unknown_node", f"Unknown node {target!r}."))

    try:
        weight = float(row["weight"])
    except (TypeError, ValueError):
        diagnostics.append(_error(f"{row_path}.weight", "invalid_weight", "Edge weight must be a number."))
        return

    if weight <= 0:
        diagnostics.append(_error(f"{row_path}.weight", "non_positive_weight", "Edge weight must be > 0."))

    edge_key = frozenset((source, target))
    if edge_key in seen_edges:
        diagnostics.append(_error(row_path, "duplicate_edge", f"Duplicate undirected edge {source!r}-{target!r}."))
    seen_edges.add(edge_key)

    if source in ALL_KNOWN_NODES and target in ALL_KNOWN_NODES and weight > 0:
        graph.add_edge(source, target, weight=weight)


def _validate_required_nodes_present(
    actual_nodes: Iterable[str],
    diagnostics: list[NetworkDiagnostic],
) -> None:
    actual = set(actual_nodes)
    for node in sorted(REQUIRED_VISIT_NODES - actual, key=_node_sort_key):
        diagnostics.append(_error("nodes", "missing_required_node", f"Required visit node {node!r} is absent."))


def _validate_connectivity(
    graph: nx.Graph,
    diagnostics: list[NetworkDiagnostic],
) -> None:
    if graph.number_of_nodes() == 0:
        diagnostics.append(_error("graph", "empty_graph", "Road network graph has no valid nodes."))
        return

    if nx.is_connected(graph):
        return

    components = [sorted(component, key=_node_sort_key) for component in nx.connected_components(graph)]
    component_text = "; ".join(f"{index + 1}: {component}" for index, component in enumerate(components))
    diagnostics.append(
        _error(
            "graph",
            "graph_not_connected",
            f"Graph has {len(components)} connected components: {component_text}.",
        )
    )


def _error(path: str, code: str, message: str) -> NetworkDiagnostic:
    return NetworkDiagnostic(severity="error", code=code, path=path, message=message)


def _node_sort_key(node: str) -> tuple[int, int, str]:
    if node == "O":
        return (0, 0, node)
    if node.isalpha():
        return (1, 0, node)
    if node.isdigit():
        return (2, int(node), node)
    if node.startswith("U") and node[1:].isdigit():
        return (3, int(node[1:]), node)
    return (4, 0, node)
