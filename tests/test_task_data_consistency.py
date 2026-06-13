import csv
import re
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK_PATH = ROOT / "docs" / "task.md"
ROAD_NETWORK_PATH = ROOT / "data" / "raw" / "road_network.tsv"
FENCE_RE = re.compile(r"```(?P<lang>[a-z]+)\n(?P<body>.*?)\n```", re.DOTALL)
DOT_EDGE_RE = re.compile(
    r'^\s*"(?P<source>[^"]+)" -- "(?P<target>[^"]+)" '
    r'\[label="(?P<label>[0-9.]+)", weight="(?P<weight>[0-9.]+)"\];\s*$'
)


def test_task_tsv_matches_raw_road_network_tsv():
    task_tsv = _task_fenced_block("tsv")

    assert task_tsv.strip() == ROAD_NETWORK_PATH.read_text(encoding="utf-8").strip()


def test_task_tsv_and_dot_blocks_describe_same_edges():
    tsv_edges = _parse_tsv_edges(_task_fenced_block("tsv"))
    dot_edges = _parse_dot_edges(_task_fenced_block("dot"))

    assert dot_edges == tsv_edges


def _task_fenced_block(language: str) -> str:
    text = TASK_PATH.read_text(encoding="utf-8")
    for match in FENCE_RE.finditer(text):
        if match.group("lang") == language:
            return match.group("body")
    raise AssertionError(f"Missing {language!r} fenced block in task.md")


def _parse_tsv_edges(text: str) -> set[tuple[str, str, str]]:
    reader = csv.DictReader(StringIO(text), delimiter="\t")
    return {_edge_key(row["source"], row["target"], row["weight"]) for row in reader}


def _parse_dot_edges(text: str) -> set[tuple[str, str, str]]:
    edges = set()
    for line in text.splitlines():
        match = DOT_EDGE_RE.match(line)
        if not match:
            continue
        assert match.group("label") == match.group("weight")
        edges.add(_edge_key(match.group("source"), match.group("target"), match.group("weight")))
    return edges


def _edge_key(source: str, target: str, weight: str) -> tuple[str, str, str]:
    left, right = sorted((source, target))
    return (left, right, weight)
