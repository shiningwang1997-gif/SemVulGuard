"""Graph feature conversion and static feature extraction.

``build_feature_graph`` turns a Joern :class:`ProgramGraph` slice into
integer-indexed :class:`FeatureNode` / :class:`FeatureEdge` lists, tagging each
node with line alignment and simple static flags. ``extract_static_features``
summarizes a sample's alerts and graph into a flat, model-ready feature dict.

The source/sink heuristics are intentionally simple keyword matches; they are a
cheap prior, not a precise taint analysis.
"""

from __future__ import annotations

from semvulguard.features.line_map import absolute_to_relative_line
from semvulguard.schemas.features import FeatureEdge, FeatureNode
from semvulguard.schemas.records import SampleRecord, StaticAlertRecord
from semvulguard.static.joern.graph import ProgramGraph

# Keyword priors for taint endpoints.
SOURCE_TERMS = ("recv", "read", "scanf", "argv", "getenv", "fgets", "gets")
SINK_TERMS = (
    "memcpy",
    "strcpy",
    "strcat",
    "sprintf",
    "system",
    "free",
    "malloc",
    "memmove",
    "alloca",
)

# Severity tokens -> ordinal score (higher is worse).
_SEVERITY_SCORE: dict[str, int] = {
    "error": 3,
    "high": 3,
    "critical": 3,
    "warning": 2,
    "medium": 2,
    "note": 1,
    "low": 1,
    "recommendation": 1,
    "info": 1,
}


def severity_score(severity: str | None) -> int:
    """Map a SARIF-style severity token to an ordinal score (0 when unknown)."""
    if severity is None:
        return 0
    return _SEVERITY_SCORE.get(severity.strip().lower(), 0)


def _contains_any(code: str, terms: tuple[str, ...]) -> bool:
    lowered = code.lower()
    return any(term in lowered for term in terms)


def _collect_lines(alerts: list[StaticAlertRecord]) -> tuple[set[int], set[int]]:
    """Return (alert_lines, trace_lines) sets gathered across all alerts."""
    alert_lines: set[int] = set()
    trace_lines: set[int] = set()
    for alert in alerts:
        alert_lines.update(range(alert.start_line, alert.end_line + 1))
        trace_lines.update(alert.trace_lines)
    return alert_lines, trace_lines


def build_feature_graph(
    graph_slice: ProgramGraph,
    sample: SampleRecord,
    alerts: list[StaticAlertRecord],
) -> tuple[list[FeatureNode], list[FeatureEdge]]:
    """Convert a graph slice into indexed feature nodes and edges.

    Node ordering follows the slice's node insertion order. Edges whose
    endpoints are both present are kept and rewritten to integer indices;
    dangling edges are dropped.
    """
    alert_lines, trace_lines = _collect_lines(alerts)

    feature_nodes: list[FeatureNode] = []
    index_of: dict[str, int] = {}
    for node_id, node in graph_slice.nodes.items():
        index_of[node_id] = len(feature_nodes)
        code = node.code or ""
        line = node.line
        line_index = (
            absolute_to_relative_line(line, sample.span)
            if line is not None
            else None
        )
        flags: dict[str, int | float] = {
            "is_alert_line": int(line in alert_lines) if line is not None else 0,
            "is_trace_line": int(line in trace_lines) if line is not None else 0,
            "is_source_like": int(_contains_any(code, SOURCE_TERMS)),
            "is_sink_like": int(_contains_any(code, SINK_TERMS)),
        }
        feature_nodes.append(
            FeatureNode(
                node_id=node_id,
                node_type=node.type or "UNKNOWN",
                code=code,
                line=line,
                line_index=line_index,
                static_flags=flags,
            )
        )

    feature_edges: list[FeatureEdge] = []
    for edge in graph_slice.edges:
        if edge.source in index_of and edge.target in index_of:
            feature_edges.append(
                FeatureEdge(
                    source=index_of[edge.source],
                    target=index_of[edge.target],
                    edge_type=edge.type or "UNKNOWN",
                )
            )
    return feature_nodes, feature_edges


def extract_static_features(
    sample: SampleRecord,
    alerts: list[StaticAlertRecord],
    graph_slice: ProgramGraph | None,
) -> dict[str, int | float | str]:
    """Summarize alerts and graph into a flat static-feature dict."""
    alert_lines, trace_lines = _collect_lines(alerts)
    query_ids = {a.query_id for a in alerts}
    max_sev = max((severity_score(a.severity) for a in alerts), default=0)

    dangerous_api_count = 0
    node_count = 0
    edge_count = 0
    if graph_slice is not None:
        node_count = len(graph_slice.nodes)
        edge_count = len(graph_slice.edges)
        for node in graph_slice.nodes.values():
            if _contains_any(node.code or "", SINK_TERMS):
                dangerous_api_count += 1

    function_line_count = sample.span.end_line - sample.span.start_line + 1

    return {
        "alert_count": len(alerts),
        "trace_line_count": len(trace_lines),
        "unique_query_count": len(query_ids),
        "has_codeql_alert": int(any(a.tool == "codeql" for a in alerts)),
        "max_severity_score": max_sev,
        "function_line_count": function_line_count,
        "graph_node_count": node_count,
        "graph_edge_count": edge_count,
        "dangerous_api_count": dangerous_api_count,
    }


__all__ = [
    "SOURCE_TERMS",
    "SINK_TERMS",
    "severity_score",
    "build_feature_graph",
    "extract_static_features",
]
