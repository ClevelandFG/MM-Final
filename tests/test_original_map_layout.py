import json
from pathlib import Path

from mm_final.network import load_road_network


LAYOUT_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "road_network_layout" / "original-map-layout.json"


def test_original_map_layout_covers_official_road_network_nodes():
    layout = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
    network_result = load_road_network()

    assert network_result.is_valid
    assert network_result.network is not None
    assert set(layout["nodes"]) == set(network_result.network.nodes)
    assert len(layout["nodes"]) == network_result.network.node_count


def test_original_map_layout_source_image_exists():
    layout = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
    source_image = Path(__file__).resolve().parents[1] / layout["source"]["image_path"]

    assert source_image.exists()


def test_original_map_layout_uses_normalized_coordinates():
    layout = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))

    assert layout["coordinate_system"]["type"] == "normalized_image"
    assert layout["coordinate_system"]["origin"] == "top_left"

    for node, coordinate in layout["nodes"].items():
        assert 0.0 <= coordinate["x"] <= 1.0, node
        assert 0.0 <= coordinate["y"] <= 1.0, node
        assert len(coordinate["source_pixel"]) == 2
