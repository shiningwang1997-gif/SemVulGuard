"""Function-level and alert-centered graph slicing.

Two slicers carve a small subgraph out of a whole-repo program graph:

* :func:`slice_by_function` keeps the nodes of one function (by file + line
  span, preferring an explicit function-name match), and
* :func:`slice_around_lines` grows a k-hop neighborhood around the lines an
  alert fired on, with optional edge-type filtering and a deterministic node
  cap.

Both return a fresh :class:`ProgramGraph` containing only edges whose endpoints
both survived the slice.
"""

from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path

from semvulguard.static.joern.graph import (
    ProgramGraph,
    load_graph_json,
    load_graphml,
)
from semvulguard.utils.logging import get_logger

LOGGER = get_logger("semvulguard.static.joern.slice")


def _paths_match(node_file: str | None, target_file: str) -> bool:
    """Match a node's file against a target by exact or suffix path."""
    if node_file is None:
        return False
    if node_file == target_file:
        return True
    a = node_file.replace("\\", "/").lstrip("/")
    b = target_file.replace("\\", "/").lstrip("/")
    if a == b:
        return True
    return a.endswith("/" + b) or b.endswith("/" + a)


def _subgraph(graph: ProgramGraph, node_ids: set[str]) -> ProgramGraph:
    """Build a new graph from a node-id subset and induced edges."""
    sliced = ProgramGraph()
    for node_id in node_ids:
        sliced.add_node(graph.nodes[node_id])
    for edge in graph.edges:
        if edge.source in node_ids and edge.target in node_ids:
            sliced.add_edge(edge)
    return sliced


def slice_by_function(
    graph: ProgramGraph,
    file: str,
    function: str | None,
    start_line: int,
    end_line: int,
) -> ProgramGraph:
    """Slice the nodes belonging to a single function.

    A node is kept when its file matches ``file`` (exact or suffix) and either
    its function name equals ``function`` (when both are available) or its line
    falls within ``[start_line, end_line]``. Nodes lacking a line are kept only
    on a function-name match.
    """
    selected: set[str] = set()
    for node_id, node in graph.nodes.items():
        if not _paths_match(node.file, file):
            continue
        if function and node.function:
            if node.function == function or node.function.endswith(function):
                selected.add(node_id)
                continue
        if node.line is not None and start_line <= node.line <= end_line:
            selected.add(node_id)
    return _subgraph(graph, selected)


def _seed_nodes(graph: ProgramGraph, file: str, lines: list[int]) -> set[str]:
    """Find nodes on ``file`` whose line is in ``lines``."""
    line_set = set(lines)
    return {
        node_id
        for node_id, node in graph.nodes.items()
        if node.line in line_set and _paths_match(node.file, file)
    }


def _bfs_distances(
    adjacency: dict[str, set[str]], seeds: set[str], k: int
) -> dict[str, int]:
    """BFS up to depth ``k``; return ``node_id -> distance`` from the seeds."""
    distance: dict[str, int] = {s: 0 for s in seeds}
    queue: deque[str] = deque(seeds)
    while queue:
        current = queue.popleft()
        if distance[current] >= k:
            continue
        for neighbor in adjacency.get(current, set()):
            if neighbor not in distance:
                distance[neighbor] = distance[current] + 1
                queue.append(neighbor)
    return distance


def slice_around_lines(
    graph: ProgramGraph,
    file: str,
    lines: list[int],
    k: int = 2,
    edge_types: set[str] | None = None,
    max_nodes: int = 400,
) -> ProgramGraph:
    """Slice a k-hop neighborhood around alert lines.

    Seeds are nodes on ``file`` matching any of ``lines``. Expansion is BFS over
    (optionally edge-type-filtered) undirected adjacency. If the result exceeds
    ``max_nodes`` it is trimmed deterministically by ascending (distance, line,
    node id), so seeds and nearer context are kept first.
    """
    seeds = _seed_nodes(graph, file, lines)
    if not seeds:
        return ProgramGraph()

    adjacency = graph.adjacency(edge_types)
    distance = _bfs_distances(adjacency, seeds, k)

    def sort_key(node_id: str) -> tuple[int, int, str]:
        node = graph.nodes[node_id]
        line = node.line if node.line is not None else 1_000_000_000
        return (distance[node_id], line, node_id)

    ordered = sorted(distance, key=sort_key)
    if len(ordered) > max_nodes:
        ordered = ordered[:max_nodes]
    return _subgraph(graph, set(ordered))


# -- serialization ----------------------------------------------------------


def graph_to_dict(graph: ProgramGraph) -> dict:
    """Serialize a :class:`ProgramGraph` to the simple JSON graph format."""
    return {
        "nodes": [
            {
                "id": node.id,
                "type": node.type,
                "code": node.code,
                "file": node.file,
                "line": node.line,
                "function": node.function,
                "properties": node.properties,
            }
            for node in graph.nodes.values()
        ],
        "edges": [
            {
                "source": edge.source,
                "target": edge.target,
                "type": edge.type,
                "properties": edge.properties,
            }
            for edge in graph.edges
        ],
    }


def write_graph_json(graph: ProgramGraph, path: str | Path) -> None:
    """Write a graph to disk in the simple JSON format."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(graph_to_dict(graph), fh, ensure_ascii=False, indent=2)


def _load_any(path: Path) -> ProgramGraph:
    """Load a graph by extension (``.graphml`` -> GraphML, else JSON)."""
    if path.suffix.lower() == ".graphml":
        return load_graphml(path)
    return load_graph_json(path)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="semvulguard.static.joern.slice",
        description="Slice a program graph by function or around alert lines.",
    )
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--file", required=True)
    parser.add_argument("--function", default=None)
    parser.add_argument("--start-line", type=int, default=None)
    parser.add_argument("--end-line", type=int, default=None)
    parser.add_argument(
        "--lines",
        default=None,
        help="comma-separated alert lines for k-hop slicing",
    )
    parser.add_argument("--k", type=int, default=2)
    parser.add_argument(
        "--edge-types",
        default=None,
        help="comma-separated edge types to traverse (k-hop mode)",
    )
    parser.add_argument("--max-nodes", type=int, default=400)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    graph = _load_any(args.graph)

    if args.lines is not None:
        lines = [int(x) for x in args.lines.split(",") if x.strip()]
        edge_types = (
            {t.strip() for t in args.edge_types.split(",") if t.strip()}
            if args.edge_types
            else None
        )
        sliced = slice_around_lines(
            graph,
            args.file,
            lines,
            k=args.k,
            edge_types=edge_types,
            max_nodes=args.max_nodes,
        )
    else:
        start = args.start_line if args.start_line is not None else 1
        end = args.end_line if args.end_line is not None else 1_000_000_000
        sliced = slice_by_function(graph, args.file, args.function, start, end)

    write_graph_json(sliced, args.output)
    LOGGER.info(
        "sliced %d nodes / %d edges -> %s",
        len(sliced.nodes),
        len(sliced.edges),
        args.output,
    )
    print(
        f"sliced {len(sliced.nodes)} nodes / {len(sliced.edges)} edges "
        f"-> {args.output}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "slice_by_function",
    "slice_around_lines",
    "graph_to_dict",
    "write_graph_json",
]
