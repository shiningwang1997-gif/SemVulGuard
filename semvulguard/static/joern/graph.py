"""In-memory program-graph representation and loaders.

Joern exports a Code Property Graph (CPG) and its projections (AST/CFG/CDG/DDG/
PDG). This module models a single graph with a minimal, serializable structure
plus the adjacency helpers the slicing code needs. Two loaders are provided:

* :func:`load_graph_json` for the project's simple JSON graph format, and
* :func:`load_graphml` for Joern's GraphML export (parsed with stdlib ElementTree).

The representation is deliberately self-contained (no networkx dependency) so
unit tests run without any extra packages.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

from pydantic import BaseModel, Field

# Keys that map onto first-class GraphNode fields rather than the property bag.
# Values are tuples of accepted source attribute names (Joern uses several).
_NODE_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "type": ("type", "label", "TYPE"),
    "code": ("code", "CODE"),
    "file": ("file", "filename", "FILENAME", "FILE"),
    "line": ("line", "lineNumber", "LINE_NUMBER"),
    "function": ("function", "method", "METHOD_FULL_NAME", "name", "NAME"),
}
_EDGE_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "type": ("type", "label", "TYPE"),
}


class GraphNode(BaseModel):
    """A single program-graph node."""

    id: str
    type: str | None = None
    code: str | None = None
    file: str | None = None
    line: int | None = None
    function: str | None = None
    properties: dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """A directed edge between two nodes."""

    source: str
    target: str
    type: str | None = None
    properties: dict = Field(default_factory=dict)


class ProgramGraph(BaseModel):
    """A program graph: a node table plus a directed edge list.

    Adjacency is computed lazily and cached; mutating the graph after the first
    adjacency access is not supported (slicing always builds fresh graphs).
    """

    nodes: dict[str, GraphNode] = Field(default_factory=dict)
    edges: list[GraphEdge] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    # -- construction helpers ----------------------------------------------

    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        self.edges.append(edge)

    # -- adjacency ----------------------------------------------------------

    def neighbors(
        self, node_id: str, edge_types: set[str] | None = None
    ) -> set[str]:
        """Return undirected neighbors of ``node_id`` (optionally typed).

        Edges are treated as undirected for k-hop expansion, since structural
        and data-flow context is relevant in both directions.
        """
        result: set[str] = set()
        for edge in self.edges:
            if edge_types is not None and edge.type not in edge_types:
                continue
            if edge.source == node_id:
                result.add(edge.target)
            elif edge.target == node_id:
                result.add(edge.source)
        return result

    def adjacency(
        self, edge_types: set[str] | None = None
    ) -> dict[str, set[str]]:
        """Build an undirected adjacency map over all nodes."""
        adj: dict[str, set[str]] = defaultdict(set)
        for node_id in self.nodes:
            adj[node_id]  # ensure isolated nodes appear
        for edge in self.edges:
            if edge_types is not None and edge.type not in edge_types:
                continue
            if edge.source in self.nodes and edge.target in self.nodes:
                adj[edge.source].add(edge.target)
                adj[edge.target].add(edge.source)
        return adj

    def __len__(self) -> int:
        return len(self.nodes)


def _coerce_line(value: object) -> int | None:
    """Best-effort conversion of a line attribute to a positive int."""
    if value is None or value == "":
        return None
    try:
        line = int(float(value))
    except (TypeError, ValueError):
        return None
    return line if line >= 1 else None


def _split_fields(
    attrs: dict, aliases: dict[str, tuple[str, ...]]
) -> tuple[dict, dict]:
    """Partition raw attributes into first-class fields and a property bag.

    Returns ``(fields, remaining)`` where ``fields`` holds resolved values for
    the alias keys and ``remaining`` keeps everything not consumed.
    """
    fields: dict = {}
    consumed: set[str] = set()
    for field, names in aliases.items():
        for name in names:
            if name in attrs and attrs[name] not in (None, ""):
                fields[field] = attrs[name]
                consumed.add(name)
                break
    remaining = {k: v for k, v in attrs.items() if k not in consumed}
    return fields, remaining


def _node_from_attrs(node_id: str, attrs: dict) -> GraphNode:
    fields, remaining = _split_fields(attrs, _NODE_FIELD_ALIASES)
    return GraphNode(
        id=node_id,
        type=fields.get("type"),
        code=fields.get("code"),
        file=fields.get("file"),
        line=_coerce_line(fields.get("line")),
        function=fields.get("function"),
        properties=remaining,
    )


def load_graph_json(path: str | Path) -> ProgramGraph:
    """Load a :class:`ProgramGraph` from the simple JSON graph format."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        doc = json.load(fh)

    graph = ProgramGraph()
    for raw in doc.get("nodes", []) or []:
        node_id = str(raw["id"])
        props = dict(raw.get("properties", {}) or {})
        # Hoist any inline first-class fields (id/properties excluded).
        inline = {k: v for k, v in raw.items() if k not in {"id", "properties"}}
        graph.add_node(
            GraphNode(
                id=node_id,
                type=inline.get("type"),
                code=inline.get("code"),
                file=inline.get("file"),
                line=_coerce_line(inline.get("line")),
                function=inline.get("function"),
                properties=props,
            )
        )
    for raw in doc.get("edges", []) or []:
        graph.add_edge(
            GraphEdge(
                source=str(raw["source"]),
                target=str(raw["target"]),
                type=raw.get("type"),
                properties=dict(raw.get("properties", {}) or {}),
            )
        )
    return graph


def _strip_ns(tag: str) -> str:
    """Drop an XML namespace prefix, e.g. ``{ns}node`` -> ``node``."""
    return tag.split("}", 1)[-1] if "}" in tag else tag


def load_graphml(path: str | Path) -> ProgramGraph:
    """Load a :class:`ProgramGraph` from a GraphML export.

    Supports GraphML ``<key>`` declarations (mapping ``id`` -> human-readable
    ``attr.name``) and ``<data key=...>`` children on nodes and edges, which is
    how Joern's GraphML output encodes node/edge attributes.
    """
    path = Path(path)
    tree = ET.parse(path)
    root = tree.getroot()

    # Map each declared key id to its attribute name (fall back to the id).
    key_names: dict[str, str] = {}
    for key in root.iter():
        if _strip_ns(key.tag) != "key":
            continue
        key_id = key.get("id")
        if key_id is not None:
            key_names[key_id] = key.get("attr.name", key_id)

    def collect_data(element: ET.Element) -> dict:
        attrs: dict = {}
        for child in element:
            if _strip_ns(child.tag) != "data":
                continue
            key_id = child.get("key", "")
            name = key_names.get(key_id, key_id)
            attrs[name] = (child.text or "").strip()
        return attrs

    graph = ProgramGraph()
    graph_el = next(
        (el for el in root.iter() if _strip_ns(el.tag) == "graph"), root
    )
    for element in graph_el:
        tag = _strip_ns(element.tag)
        if tag == "node":
            node_id = element.get("id")
            if node_id is None:
                continue
            graph.add_node(_node_from_attrs(str(node_id), collect_data(element)))
        elif tag == "edge":
            source = element.get("source")
            target = element.get("target")
            if source is None or target is None:
                continue
            attrs = collect_data(element)
            edge_label = element.get("label")
            fields, remaining = _split_fields(attrs, _EDGE_FIELD_ALIASES)
            graph.add_edge(
                GraphEdge(
                    source=str(source),
                    target=str(target),
                    type=fields.get("type") or edge_label,
                    properties=remaining,
                )
            )
    return graph


__all__ = [
    "GraphNode",
    "GraphEdge",
    "ProgramGraph",
    "load_graph_json",
    "load_graphml",
]
