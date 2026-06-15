"""Tests for graph feature conversion and static feature extraction."""

from __future__ import annotations

from pathlib import Path

from semvulguard.features.graph_features import (
    build_feature_graph,
    extract_static_features,
    severity_score,
)
from semvulguard.schemas.records import CodeSpan, SampleRecord, StaticAlertRecord
from semvulguard.static.joern.graph import load_graph_json


def _sample() -> SampleRecord:
    return SampleRecord(
        sample_id="s1",
        dataset="diversevul",
        language="c",
        file="a.c",
        span=CodeSpan(file="a.c", start_line=1, end_line=10),
        label=1,
        cwe=["CWE-416"],
        split="train",
    )


def _alerts() -> list[StaticAlertRecord]:
    return [
        StaticAlertRecord(
            sample_id="s1",
            tool="codeql",
            query_id="cpp/use-after-free",
            message="Use after free",
            severity="high",
            file="a.c",
            start_line=5,
            end_line=6,
            cwe=["CWE-416"],
            trace_lines=[3, 5],
        )
    ]


def _graph(fixtures_dir: Path):
    return load_graph_json(fixtures_dir / "features" / "sample_graph_slice.json")


def test_severity_score_mapping():
    assert severity_score("error") == 3
    assert severity_score("high") == 3
    assert severity_score("warning") == 2
    assert severity_score("medium") == 2
    assert severity_score("note") == 1
    assert severity_score("recommendation") == 1
    assert severity_score(None) == 0
    assert severity_score("mystery") == 0


def test_build_feature_graph_indices_and_drops_dangling(fixtures_dir: Path):
    graph = _graph(fixtures_dir)
    nodes, edges = build_feature_graph(graph, _sample(), _alerts())
    assert len(nodes) == 5
    # Edge to node "99" (absent) is dropped; 4 of 5 edges survive.
    assert len(edges) == 4
    assert all(0 <= e.source < len(nodes) for e in edges)
    assert all(0 <= e.target < len(nodes) for e in edges)


def test_node_alert_and_trace_flags(fixtures_dir: Path):
    graph = _graph(fixtures_dir)
    nodes, _ = build_feature_graph(graph, _sample(), _alerts())
    by_id = {n.node_id: n for n in nodes}
    # Node 3 is on line 5 -> alert line (5-6) and trace line (3,5).
    assert by_id["3"].static_flags["is_alert_line"] == 1
    assert by_id["3"].static_flags["is_trace_line"] == 1
    # Node 2 on line 3 -> trace line but not alert line.
    assert by_id["2"].static_flags["is_alert_line"] == 0
    assert by_id["2"].static_flags["is_trace_line"] == 1
    # Node 5 on line 9 -> neither.
    assert by_id["5"].static_flags["is_alert_line"] == 0
    assert by_id["5"].static_flags["is_trace_line"] == 0


def test_node_source_sink_flags(fixtures_dir: Path):
    graph = _graph(fixtures_dir)
    nodes, _ = build_feature_graph(graph, _sample(), _alerts())
    by_id = {n.node_id: n for n in nodes}
    # Node 2 calls read(...) -> source-like.
    assert by_id["2"].static_flags["is_source_like"] == 1
    # Node 3 calls free(...) -> sink-like.
    assert by_id["3"].static_flags["is_sink_like"] == 1
    # Node 5 "return n" -> neither.
    assert by_id["5"].static_flags["is_source_like"] == 0
    assert by_id["5"].static_flags["is_sink_like"] == 0


def test_node_line_index_alignment(fixtures_dir: Path):
    graph = _graph(fixtures_dir)
    nodes, _ = build_feature_graph(graph, _sample(), _alerts())
    by_id = {n.node_id: n for n in nodes}
    # Span starts at line 1, so absolute line 5 -> relative index 5.
    assert by_id["3"].line == 5
    assert by_id["3"].line_index == 5


def test_extract_static_features(fixtures_dir: Path):
    graph = _graph(fixtures_dir)
    feats = extract_static_features(_sample(), _alerts(), graph)
    assert feats["alert_count"] == 1
    assert feats["trace_line_count"] == 2
    assert feats["unique_query_count"] == 1
    assert feats["has_codeql_alert"] == 1
    assert feats["max_severity_score"] == 3
    assert feats["function_line_count"] == 10
    assert feats["graph_node_count"] == 5
    assert feats["graph_edge_count"] == 5
    # free + malloc-free... node 3 (free) is the only sink-like code here.
    assert feats["dangerous_api_count"] == 1


def test_extract_static_features_no_graph():
    feats = extract_static_features(_sample(), _alerts(), None)
    assert feats["graph_node_count"] == 0
    assert feats["graph_edge_count"] == 0
    assert feats["dangerous_api_count"] == 0
    assert feats["alert_count"] == 1


def test_extract_static_features_no_alerts(fixtures_dir: Path):
    graph = _graph(fixtures_dir)
    feats = extract_static_features(_sample(), [], graph)
    assert feats["alert_count"] == 0
    assert feats["trace_line_count"] == 0
    assert feats["has_codeql_alert"] == 0
    assert feats["max_severity_score"] == 0
