"""B4 组数下界与不可能性分析。"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite
from typing import Iterable, Literal, Optional

from mm_final.network import DEPOT, REQUIRED_VISIT_NODES, NodeType, RoadNetwork, classify_node


BoundStrength = Literal["strict/provable", "screening_only", "heuristic"]
GroupStatus = Literal["lower_bound_impossible", "not_excluded", "insufficient_evidence"]


@dataclass(frozen=True)
class LowerBoundParameters:
    """下界分析参数，允许在没有 RoutePlan 的情况下独立运行。"""

    T_hour: float = 2.0
    t_hour: float = 1.0
    speed_km_per_hour: float = 35.0
    time_limit_hour: float = 24.0
    required_visit_nodes: frozenset[str] = frozenset(REQUIRED_VISIT_NODES)
    farthest_node_count: int = 5
    distance_tier_count: int = 3
    time_tolerance_hour: float = 1e-6


@dataclass(frozen=True)
class LowerBoundEntry:
    code: str
    label: str
    value: float
    unit: str
    strength: BoundStrength
    scope: str
    nodes: tuple[str, ...] = ()
    explanation: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "label": self.label,
            "value": self.value,
            "unit": self.unit,
            "strength": self.strength,
            "scope": self.scope,
            "nodes": list(self.nodes),
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class GroupLowerBound:
    group_count: int
    lower_bound_hour: float
    status: GroupStatus
    active_bound_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "group_count": self.group_count,
            "lower_bound_hour": self.lower_bound_hour,
            "status": self.status,
            "active_bound_codes": list(self.active_bound_codes),
        }


@dataclass(frozen=True)
class LowerBoundReport:
    parameters: LowerBoundParameters
    k_values: tuple[int, ...]
    total_stop_time_hour: float
    minimum_group_count_by_stop_time: int
    max_single_node: Optional[str]
    max_single_node_round_trip_hour: float
    unlimited_personnel_lower_bound_hour: float
    bound_entries: tuple[LowerBoundEntry, ...]
    group_bounds: tuple[GroupLowerBound, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "parameters": _parameters_to_dict(self.parameters),
            "k_values": list(self.k_values),
            "total_stop_time_hour": self.total_stop_time_hour,
            "minimum_group_count_by_stop_time": self.minimum_group_count_by_stop_time,
            "max_single_node": self.max_single_node,
            "max_single_node_round_trip_hour": self.max_single_node_round_trip_hour,
            "unlimited_personnel_lower_bound_hour": self.unlimited_personnel_lower_bound_hour,
            "bound_entries": [item.to_dict() for item in self.bound_entries],
            "group_bounds": [item.to_dict() for item in self.group_bounds],
        }


def default_k_values(required_visit_nodes: Iterable[str] = REQUIRED_VISIT_NODES) -> tuple[int, ...]:
    nodes = tuple(required_visit_nodes)
    return tuple(range(1, len(nodes) + 1))


def compute_lower_bound_report(
    road_network: RoadNetwork,
    *,
    k_values: Iterable[int],
    parameters: Optional[LowerBoundParameters] = None,
) -> LowerBoundReport:
    params = LowerBoundParameters() if parameters is None else parameters
    _validate_parameters(params)
    k_tuple = tuple(k_values)
    _validate_k_values(k_tuple)

    required_nodes = tuple(sorted(params.required_visit_nodes, key=_node_sort_key))
    _validate_required_nodes_in_network(required_nodes, road_network)
    depot_distances = _depot_distances(road_network, required_nodes)

    total_stop_time = sum(_stop_time(node, params) for node in required_nodes)
    min_group_count = ceil(total_stop_time / params.time_limit_hour) if total_stop_time > 0 else 0

    single_node_times = {
        node: 2.0 * depot_distances[node] / params.speed_km_per_hour + _stop_time(node, params)
        for node in required_nodes
    }
    max_single_node = max(single_node_times, key=lambda node: (single_node_times[node], _node_sort_key(node)), default=None)
    max_single_time = single_node_times[max_single_node] if max_single_node is not None else 0.0

    entries = [
        LowerBoundEntry(
            code="total_stop_time_capacity",
            label="Total stop-time capacity",
            value=total_stop_time,
            unit="hour",
            strength="strict/provable",
            scope="global",
            nodes=required_nodes,
            explanation="For k groups, completion time is at least total required stop time divided by k.",
        )
    ]
    if max_single_node is not None:
        entries.append(
            LowerBoundEntry(
                code="single_node_round_trip",
                label="Single-node round-trip bottleneck",
                value=max_single_time,
                unit="hour",
                strength="strict/provable",
                scope="global",
                nodes=(max_single_node,),
                explanation="Any feasible plan must send one group from depot to this node and back, plus its stop time.",
            )
        )

    entries.extend(_collection_bound_entries(required_nodes, depot_distances, params))
    group_bounds = _group_lower_bounds(k_tuple, entries, params)

    return LowerBoundReport(
        parameters=params,
        k_values=k_tuple,
        total_stop_time_hour=total_stop_time,
        minimum_group_count_by_stop_time=min_group_count,
        max_single_node=max_single_node,
        max_single_node_round_trip_hour=max_single_time,
        unlimited_personnel_lower_bound_hour=max_single_time,
        bound_entries=tuple(entries),
        group_bounds=group_bounds,
    )


def lower_bound_report_to_markdown(report: LowerBoundReport) -> str:
    lines = [
        "## Lower Bound Report",
        "",
        f"- Time limit: {report.parameters.time_limit_hour:.6g} h",
        f"- Speed: {report.parameters.speed_km_per_hour:.6g} km/h",
        f"- Required nodes: {len(report.parameters.required_visit_nodes)}",
        f"- Total stop time: {report.total_stop_time_hour:.6g} h",
        f"- Stop-time group lower bound: {report.minimum_group_count_by_stop_time}",
        f"- Unlimited-personnel lower bound: {report.unlimited_personnel_lower_bound_hour:.6g} h",
        "",
        "### Group Bounds",
        "",
        "| k | lower_bound_hour | status | active_bound_codes |",
        "| --- | ---: | --- | --- |",
    ]
    for item in report.group_bounds:
        active_codes = ", ".join(item.active_bound_codes) if item.active_bound_codes else "-"
        lines.append(f"| {item.group_count} | {item.lower_bound_hour:.6g} | {item.status} | {active_codes} |")

    lines.extend(
        [
            "",
            "### Bound Evidence",
            "",
            "| code | strength | scope | value | unit | nodes |",
            "| --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for entry in report.bound_entries:
        nodes = ", ".join(entry.nodes) if entry.nodes else "-"
        lines.append(
            f"| {entry.code} | {entry.strength} | {entry.scope} | "
            f"{entry.value:.6g} | {entry.unit} | {nodes} |"
        )

    return "\n".join(lines) + "\n"


def _collection_bound_entries(
    required_nodes: tuple[str, ...],
    depot_distances: dict[str, float],
    params: LowerBoundParameters,
) -> tuple[LowerBoundEntry, ...]:
    entries: list[LowerBoundEntry] = []
    collection_specs: list[tuple[str, str, tuple[str, ...], BoundStrength]] = [
        ("towns", "Town collection load", _nodes_by_type(required_nodes, NodeType.TOWN), "strict/provable"),
        ("villages", "Village collection load", _nodes_by_type(required_nodes, NodeType.VILLAGE), "strict/provable"),
        (
            f"farthest_top_{params.farthest_node_count}",
            "Farthest-node collection load",
            _farthest_nodes(required_nodes, depot_distances, params.farthest_node_count),
            "strict/provable",
        ),
    ]
    for index, nodes in enumerate(_distance_tiers(required_nodes, depot_distances, params.distance_tier_count), start=1):
        collection_specs.append((f"distance_tier_{index}", f"Distance tier {index} load", nodes, "screening_only"))

    seen_codes: set[str] = set()
    for code_suffix, label, nodes, strength in collection_specs:
        if not nodes:
            continue
        code = f"collection_load_{code_suffix}"
        if code in seen_codes:
            continue
        seen_codes.add(code)
        entries.append(_collection_entry(code, label, nodes, strength, depot_distances, params))

    return tuple(entries)


def _collection_entry(
    code: str,
    label: str,
    nodes: tuple[str, ...],
    strength: BoundStrength,
    depot_distances: dict[str, float],
    params: LowerBoundParameters,
) -> LowerBoundEntry:
    stop_load = sum(_stop_time(node, params) for node in nodes)
    nearest_distance = min(depot_distances[node] for node in nodes)
    workload_hour = stop_load + 2.0 * nearest_distance / params.speed_km_per_hour
    explanation = (
        "For any non-empty collection, covering the collection requires its stop load and at least one depot "
        "round trip to the nearest node; per-k contribution is this value divided by k."
    )
    return LowerBoundEntry(
        code=code,
        label=label,
        value=workload_hour,
        unit="hour",
        strength=strength,
        scope="collection",
        nodes=tuple(sorted(nodes, key=_node_sort_key)),
        explanation=explanation,
    )


def _group_lower_bounds(
    k_values: tuple[int, ...],
    entries: list[LowerBoundEntry],
    params: LowerBoundParameters,
) -> tuple[GroupLowerBound, ...]:
    strict_entries = [entry for entry in entries if entry.strength == "strict/provable"]
    group_bounds: list[GroupLowerBound] = []

    for group_count in k_values:
        candidates: list[tuple[str, float]] = []
        for entry in strict_entries:
            if entry.code == "single_node_round_trip":
                candidates.append((entry.code, entry.value))
            else:
                candidates.append((entry.code, entry.value / group_count))

        if not candidates:
            group_bounds.append(
                GroupLowerBound(
                    group_count=group_count,
                    lower_bound_hour=0.0,
                    status="insufficient_evidence",
                    active_bound_codes=(),
                )
            )
            continue

        lower_bound = max(value for _, value in candidates)
        active_codes = tuple(code for code, value in candidates if abs(value - lower_bound) <= params.time_tolerance_hour)
        status: GroupStatus = (
            "lower_bound_impossible"
            if lower_bound > params.time_limit_hour + params.time_tolerance_hour
            else "not_excluded"
        )
        group_bounds.append(
            GroupLowerBound(
                group_count=group_count,
                lower_bound_hour=lower_bound,
                status=status,
                active_bound_codes=active_codes,
            )
        )

    return tuple(group_bounds)


def _depot_distances(road_network: RoadNetwork, nodes: tuple[str, ...]) -> dict[str, float]:
    return {node: road_network.shortest_path(DEPOT, node).distance_km for node in nodes}


def _nodes_by_type(nodes: tuple[str, ...], node_type: NodeType) -> tuple[str, ...]:
    return tuple(node for node in nodes if classify_node(node) is node_type)


def _farthest_nodes(nodes: tuple[str, ...], depot_distances: dict[str, float], count: int) -> tuple[str, ...]:
    if count <= 0:
        return ()
    return tuple(
        sorted(nodes, key=lambda node: (-depot_distances[node], _node_sort_key(node)))[:count]
    )


def _distance_tiers(
    nodes: tuple[str, ...],
    depot_distances: dict[str, float],
    tier_count: int,
) -> tuple[tuple[str, ...], ...]:
    if tier_count <= 0 or not nodes:
        return ()
    sorted_nodes = sorted(nodes, key=lambda node: (depot_distances[node], _node_sort_key(node)))
    tier_size = ceil(len(sorted_nodes) / tier_count)
    return tuple(
        tuple(sorted_nodes[start : start + tier_size])
        for start in range(0, len(sorted_nodes), tier_size)
    )


def _stop_time(node: str, params: LowerBoundParameters) -> float:
    node_type = classify_node(node)
    if node_type is NodeType.TOWN:
        return params.T_hour
    if node_type is NodeType.VILLAGE:
        return params.t_hour
    raise ValueError(f"Node {node!r} is not a required town or village.")


def _validate_parameters(params: LowerBoundParameters) -> None:
    numeric_fields = {
        "T_hour": params.T_hour,
        "t_hour": params.t_hour,
        "speed_km_per_hour": params.speed_km_per_hour,
        "time_limit_hour": params.time_limit_hour,
        "time_tolerance_hour": params.time_tolerance_hour,
    }
    for field_name, value in numeric_fields.items():
        if not isfinite(value):
            raise ValueError(f"{field_name} must be finite.")
    if params.T_hour < 0 or params.t_hour < 0:
        raise ValueError("Stop times must be non-negative.")
    if params.speed_km_per_hour <= 0:
        raise ValueError("speed_km_per_hour must be > 0.")
    if params.time_limit_hour <= 0:
        raise ValueError("time_limit_hour must be > 0.")
    if params.time_tolerance_hour < 0:
        raise ValueError("time_tolerance_hour must be non-negative.")
    for node in params.required_visit_nodes:
        node_type = classify_node(node)
        if node_type not in (NodeType.TOWN, NodeType.VILLAGE):
            raise ValueError(f"Required visit node {node!r} must be a town or village.")


def _validate_k_values(k_values: tuple[int, ...]) -> None:
    if not k_values:
        raise ValueError("k_values must not be empty.")
    for group_count in k_values:
        if group_count <= 0:
            raise ValueError("Every k value must be a positive integer.")


def _validate_required_nodes_in_network(nodes: tuple[str, ...], road_network: RoadNetwork) -> None:
    missing_nodes = [node for node in nodes if node not in road_network.nodes]
    if missing_nodes:
        missing_text = ", ".join(missing_nodes)
        raise ValueError(f"Required visit nodes are absent from road network: {missing_text}.")


def _parameters_to_dict(params: LowerBoundParameters) -> dict[str, object]:
    return {
        "T_hour": params.T_hour,
        "t_hour": params.t_hour,
        "speed_km_per_hour": params.speed_km_per_hour,
        "time_limit_hour": params.time_limit_hour,
        "required_visit_nodes": sorted(params.required_visit_nodes, key=_node_sort_key),
        "farthest_node_count": params.farthest_node_count,
        "distance_tier_count": params.distance_tier_count,
        "time_tolerance_hour": params.time_tolerance_hour,
    }


def _node_sort_key(node: str) -> tuple[int, int, str]:
    if node == DEPOT:
        return (0, 0, node)
    if node.isalpha():
        return (1, 0, node)
    if node.isdigit():
        return (2, int(node), node)
    if node.startswith("U") and node[1:].isdigit():
        return (3, int(node[1:]), node)
    return (4, 0, node)
