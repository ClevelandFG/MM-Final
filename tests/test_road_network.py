from pathlib import Path

from mm_final.network import (
    AUXILIARY_NODES,
    DEPOT,
    REQUIRED_VISIT_NODES,
    TOWN_NODES,
    VILLAGE_NODES,
    NodeType,
    classify_node,
    load_road_network,
    validate_road_network_tsv,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "road_networks"


def diagnostic_codes(result):
    return {diagnostic.code for diagnostic in result.diagnostics}


def test_node_classification_and_counts():
    assert classify_node("O") is NodeType.DEPOT
    assert classify_node("A") is NodeType.TOWN
    assert classify_node("R") is NodeType.TOWN
    assert classify_node("I") is NodeType.TOWN
    assert classify_node("1") is NodeType.VILLAGE
    assert classify_node("35") is NodeType.VILLAGE
    assert classify_node("U01") is NodeType.AUXILIARY
    assert classify_node("U05") is NodeType.AUXILIARY
    assert classify_node("X") is NodeType.UNKNOWN

    assert len(TOWN_NODES) == 17
    assert DEPOT not in TOWN_NODES
    assert len(VILLAGE_NODES) == 35
    assert len(AUXILIARY_NODES) == 5
    assert len(REQUIRED_VISIT_NODES) == 52


def test_default_road_network_loads_and_validates_official_tsv():
    result = load_road_network()

    assert result.is_valid
    assert not result.diagnostics
    assert result.network is not None
    assert result.network.node_count == 58
    assert result.network.edge_count == 91
    assert REQUIRED_VISIT_NODES.issubset(result.network.nodes)
    assert result.network.has_edge("P", "O")
    assert result.network.edge_weight_km("P", "O") == 10.1


def test_to_networkx_returns_copy():
    result = load_road_network()
    assert result.network is not None

    graph_copy = result.network.to_networkx()
    graph_copy.remove_node("O")

    assert "O" in result.network.nodes
    assert "O" not in graph_copy.nodes


def test_invalid_header_is_error():
    result = validate_road_network_tsv(FIXTURE_DIR / "invalid-header.tsv")

    assert not result.is_valid
    assert "invalid_header" in diagnostic_codes(result)


def test_unknown_node_is_error():
    result = validate_road_network_tsv(FIXTURE_DIR / "unknown-node.tsv")

    assert not result.is_valid
    assert "unknown_node" in diagnostic_codes(result)


def test_non_positive_weight_is_error():
    result = validate_road_network_tsv(FIXTURE_DIR / "non-positive-weight.tsv")

    assert not result.is_valid
    assert "non_positive_weight" in diagnostic_codes(result)


def test_duplicate_undirected_edge_is_error():
    result = validate_road_network_tsv(FIXTURE_DIR / "duplicate-edge.tsv")

    assert not result.is_valid
    assert "duplicate_edge" in diagnostic_codes(result)


def test_disconnected_graph_reports_components():
    result = validate_road_network_tsv(FIXTURE_DIR / "disconnected.tsv")

    assert not result.is_valid
    assert "graph_not_connected" in diagnostic_codes(result)
    diagnostic_text = "\n".join(diagnostic.to_text() for diagnostic in result.diagnostics)
    assert "connected components" in diagnostic_text
    assert "['A', 'B']" in diagnostic_text
    assert "['C', 'D']" in diagnostic_text
