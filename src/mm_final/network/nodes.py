"""题面节点语义。"""

from __future__ import annotations

from enum import Enum


class NodeType(Enum):
    DEPOT = "depot"
    TOWN = "town"
    VILLAGE = "village"
    AUXILIARY = "auxiliary"
    UNKNOWN = "unknown"


DEPOT = "O"
TOWN_NODES = tuple(
    node for node in (chr(code) for code in range(ord("A"), ord("R") + 1)) if node != DEPOT
)
VILLAGE_NODES = tuple(str(index) for index in range(1, 36))
AUXILIARY_NODES = tuple(f"U{index}" for index in range(1, 7))
REQUIRED_VISIT_NODES = frozenset(TOWN_NODES + VILLAGE_NODES)
ALL_KNOWN_NODES = frozenset((DEPOT,) + TOWN_NODES + VILLAGE_NODES + AUXILIARY_NODES)


def classify_node(node: str) -> NodeType:
    if node == DEPOT:
        return NodeType.DEPOT
    if node in TOWN_NODES:
        return NodeType.TOWN
    if node in VILLAGE_NODES:
        return NodeType.VILLAGE
    if node in AUXILIARY_NODES:
        return NodeType.AUXILIARY
    return NodeType.UNKNOWN
