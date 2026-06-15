"""Joern backend: program-graph loading, slicing, and an optional CLI runner."""

from semvulguard.static.joern.graph import (
    GraphEdge,
    GraphNode,
    ProgramGraph,
    load_graph_json,
    load_graphml,
)
from semvulguard.static.joern.runner import JoernRunner
from semvulguard.static.joern.slice import (
    graph_to_dict,
    slice_around_lines,
    slice_by_function,
    write_graph_json,
)

__all__ = [
    "GraphNode",
    "GraphEdge",
    "ProgramGraph",
    "load_graph_json",
    "load_graphml",
    "slice_by_function",
    "slice_around_lines",
    "graph_to_dict",
    "write_graph_json",
    "JoernRunner",
]
