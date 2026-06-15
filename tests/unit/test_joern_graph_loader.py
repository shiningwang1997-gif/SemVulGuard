"""Tests for the Joern graph loaders (JSON and GraphML)."""

from __future__ import annotations

from pathlib import Path

from semvulguard.static.joern.graph import (
    GraphNode,
    ProgramGraph,
    load_graph_json,
    load_graphml,
)


def _json(fixtures_dir: Path) -> Path:
    return fixtures_dir / "joern" / "sample_graph.json"


def _graphml(fixtures_dir: Path) -> Path:
    return fixtures_dir / "joern" / "sample_graph.graphml"


def test_load_graph_json_node_count(fixtures_dir: Path):
    graph = load_graph_json(_json(fixtures_dir))
    assert isinstance(graph, ProgramGraph)
    assert len(graph.nodes) == 6
    assert len(graph.edges) == 5


def test_load_graph_json_node_fields(fixtures_dir: Path):
    graph = load_graph_json(_json(fixtures_dir))
    node = graph.nodes["2"]
    assert isinstance(node, GraphNode)
    assert node.type == "CALL"
    assert node.code == "p = malloc(n)"
    assert node.file == "a.c"
    assert node.line == 10
    assert node.function == "foo"


def test_load_graph_json_edge_fields(fixtures_dir: Path):
    graph = load_graph_json(_json(fixtures_dir))
    edge = graph.edges[0]
    assert edge.source == "1"
    assert edge.target == "2"
    assert edge.type == "AST"


def test_load_graphml_node_count(fixtures_dir: Path):
    graph = load_graphml(_graphml(fixtures_dir))
    assert len(graph.nodes) == 3
    assert len(graph.edges) == 2


def test_load_graphml_attribute_mapping(fixtures_dir: Path):
    graph = load_graphml(_graphml(fixtures_dir))
    node = graph.nodes["2"]
    # label -> type, filename -> file, lineNumber -> line, method -> function.
    assert node.type == "CALL"
    assert node.code == "free(p)"
    assert node.file == "a.c"
    assert node.line == 20
    assert node.function == "foo"


def test_load_graphml_edge_types(fixtures_dir: Path):
    graph = load_graphml(_graphml(fixtures_dir))
    # First edge uses a <data> label, second uses the label attribute.
    types = {(e.source, e.target): e.type for e in graph.edges}
    assert types[("1", "2")] == "AST"
    assert types[("2", "3")] == "DDG"


def test_neighbors_undirected(fixtures_dir: Path):
    graph = load_graph_json(_json(fixtures_dir))
    # Node 3 connects to 2 (CFG), 4 (DDG), 6 (AST).
    assert graph.neighbors("3") == {"2", "4", "6"}


def test_neighbors_filtered_by_edge_type(fixtures_dir: Path):
    graph = load_graph_json(_json(fixtures_dir))
    assert graph.neighbors("3", edge_types={"DDG"}) == {"4"}


def test_adjacency_includes_isolated_handling(fixtures_dir: Path):
    graph = load_graph_json(_json(fixtures_dir))
    adj = graph.adjacency()
    assert adj["1"] == {"2"}
    assert "6" in adj
