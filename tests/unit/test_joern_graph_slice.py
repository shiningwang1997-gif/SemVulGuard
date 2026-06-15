"""Tests for function-level and alert-centered graph slicing, plus the CLI."""

from __future__ import annotations

from pathlib import Path

from semvulguard.static.joern.graph import (
    GraphEdge,
    GraphNode,
    ProgramGraph,
    load_graph_json,
)
from semvulguard.static.joern.slice import (
    graph_to_dict,
    slice_around_lines,
    slice_by_function,
)
from semvulguard.static.joern.slice import (
    main as slice_main,
)


def _graph(fixtures_dir: Path) -> ProgramGraph:
    return load_graph_json(fixtures_dir / "joern" / "sample_graph.json")


def test_slice_by_function_by_span(fixtures_dir: Path):
    graph = _graph(fixtures_dir)
    sliced = slice_by_function(graph, "a.c", None, 1, 50)
    # foo's nodes 1-4 are within [1, 50]; bar (line 100) and b.c node excluded.
    assert set(sliced.nodes) == {"1", "2", "3", "4"}


def test_slice_by_function_prefers_function_name(fixtures_dir: Path):
    graph = _graph(fixtures_dir)
    # A tight span that would exclude line-20/25 nodes, but function match keeps.
    sliced = slice_by_function(graph, "a.c", "foo", 1, 1)
    assert set(sliced.nodes) == {"1", "2", "3", "4"}


def test_slice_by_function_suffix_path(fixtures_dir: Path):
    graph = _graph(fixtures_dir)
    sliced = slice_by_function(graph, "/repo/src/a.c", None, 1, 50)
    assert set(sliced.nodes) == {"1", "2", "3", "4"}


def test_slice_by_function_induced_edges(fixtures_dir: Path):
    graph = _graph(fixtures_dir)
    sliced = slice_by_function(graph, "a.c", None, 1, 50)
    # Edge 4->5 drops (5 excluded); edge 3->6 drops (6 in b.c).
    pairs = {(e.source, e.target) for e in sliced.edges}
    assert ("4", "5") not in pairs
    assert ("3", "6") not in pairs
    assert ("1", "2") in pairs


def test_slice_around_lines_one_hop(fixtures_dir: Path):
    graph = _graph(fixtures_dir)
    sliced = slice_around_lines(graph, "a.c", [20], k=1)
    # Seed node 3 (line 20); 1-hop neighbors: 2, 4, 6.
    assert set(sliced.nodes) == {"2", "3", "4", "6"}


def test_slice_around_lines_two_hops(fixtures_dir: Path):
    graph = _graph(fixtures_dir)
    sliced = slice_around_lines(graph, "a.c", [20], k=2)
    # 2-hop from node 3 reaches 1 (via 2) and 5 (via 4).
    assert set(sliced.nodes) == {"1", "2", "3", "4", "5", "6"}


def test_slice_around_lines_edge_type_filter(fixtures_dir: Path):
    graph = _graph(fixtures_dir)
    sliced = slice_around_lines(graph, "a.c", [20], k=2, edge_types={"DDG"})
    # Only DDG edge 3->4 is traversable from seed 3.
    assert set(sliced.nodes) == {"3", "4"}


def test_slice_around_lines_no_seed_returns_empty(fixtures_dir: Path):
    graph = _graph(fixtures_dir)
    sliced = slice_around_lines(graph, "a.c", [9999], k=2)
    assert len(sliced.nodes) == 0


def _line_graph(n: int) -> ProgramGraph:
    """A chain 0-1-2-...-(n-1), all on a.c with line == id+1."""
    graph = ProgramGraph()
    for i in range(n):
        graph.add_node(
            GraphNode(id=str(i), type="X", file="a.c", line=i + 1, function="f")
        )
    for i in range(n - 1):
        graph.add_edge(GraphEdge(source=str(i), target=str(i + 1), type="CFG"))
    return graph


def test_max_nodes_cap_is_deterministic():
    graph = _line_graph(20)
    # Seed at the chain start; large k would otherwise pull all 20 nodes.
    a = slice_around_lines(graph, "a.c", [1], k=50, max_nodes=5)
    b = slice_around_lines(graph, "a.c", [1], k=50, max_nodes=5)
    assert set(a.nodes) == set(b.nodes)
    assert len(a.nodes) == 5
    # Nearest nodes by distance (then line) win: ids 0..4.
    assert set(a.nodes) == {"0", "1", "2", "3", "4"}


def test_slice_cli_function_mode(fixtures_dir: Path, tmp_path: Path, capsys):
    out = tmp_path / "slice.json"
    rc = slice_main(
        [
            "--graph",
            str(fixtures_dir / "joern" / "sample_graph.json"),
            "--file",
            "a.c",
            "--start-line",
            "1",
            "--end-line",
            "50",
            "--output",
            str(out),
        ]
    )
    assert rc == 0
    assert out.exists()
    reloaded = load_graph_json(out)
    assert set(reloaded.nodes) == {"1", "2", "3", "4"}
    assert "sliced 4 nodes" in capsys.readouterr().out


def test_slice_cli_khop_mode(fixtures_dir: Path, tmp_path: Path):
    out = tmp_path / "slice.json"
    slice_main(
        [
            "--graph",
            str(fixtures_dir / "joern" / "sample_graph.json"),
            "--file",
            "a.c",
            "--lines",
            "20",
            "--k",
            "1",
            "--output",
            str(out),
        ]
    )
    reloaded = load_graph_json(out)
    assert set(reloaded.nodes) == {"2", "3", "4", "6"}


def test_graph_to_dict_round_trip(fixtures_dir: Path):
    graph = _graph(fixtures_dir)
    sliced = slice_by_function(graph, "a.c", None, 1, 50)
    d = graph_to_dict(sliced)
    assert len(d["nodes"]) == 4
    assert all("id" in n for n in d["nodes"])
