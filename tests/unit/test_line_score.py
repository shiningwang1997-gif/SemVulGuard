"""Tests for line-level localization scoring and Top-K selection."""

from __future__ import annotations

from semvulguard.localization.line_score import (
    DEFAULT_LINE_WEIGHTS,
    compute_line_scores,
    top_k_lines,
)
from semvulguard.schemas.features import FeatureNode, FeatureRecord
from semvulguard.schemas.records import CodeSpan, LLMVerdict, StaticAlertRecord


def _feature(nodes=None, alert_lines=None, trace_lines=None) -> FeatureRecord:
    return FeatureRecord(
        sample_id="s1",
        label=1,
        cwe=[],
        file="a.c",
        function="f",
        span=CodeSpan(file="a.c", start_line=1, end_line=30),
        function_code="void f(){}",
        alert_lines=alert_lines or [],
        trace_lines=trace_lines or [],
        nodes=nodes or [],
    )


def _alert(start, end, trace=None) -> StaticAlertRecord:
    return StaticAlertRecord(
        sample_id="s1",
        tool="codeql",
        query_id="q",
        message="m",
        severity="high",
        file="a.c",
        start_line=start,
        end_line=end,
        trace_lines=trace or [],
    )


def _verdict(lines) -> LLMVerdict:
    return LLMVerdict(
        sample_id="s1",
        verdict="vulnerable",
        confidence=0.9,
        predicted_cwe="CWE-119",
        vulnerable_lines=lines,
        evidence=[],
        need_more_context=False,
        missing_context=[],
        patch_hint="",
    )


def test_empty_evidence_gives_no_scores():
    assert compute_line_scores(_feature(), [], None) == {}


def test_alert_line_scored():
    scores = compute_line_scores(_feature(), [_alert(12, 12)], None)
    assert scores[12] == DEFAULT_LINE_WEIGHTS["static_alert_line"]


def test_components_accumulate_and_cap_at_one():
    alert = _alert(12, 12, trace=[12])
    verdict = _verdict([12])
    node = FeatureNode(
        node_id="n", node_type="CALL", code="memcpy()", line=12,
        static_flags={"is_sink_like": 1},
    )
    scores = compute_line_scores(_feature(nodes=[node]), [alert], verdict)
    # All four components hit line 12; sum exceeds 1.0 but is capped.
    assert scores[12] == 1.0


def test_llm_lines_scored_without_alerts():
    scores = compute_line_scores(_feature(), [], _verdict([7]))
    assert scores[7] == DEFAULT_LINE_WEIGHTS["llm_vote"]


def test_feature_lines_used_as_fallback():
    feature = _feature(alert_lines=[3], trace_lines=[4])
    scores = compute_line_scores(feature, [], None)
    assert scores[3] == DEFAULT_LINE_WEIGHTS["static_alert_line"]
    assert scores[4] == DEFAULT_LINE_WEIGHTS["trace_line"]


def test_graph_flag_only_when_flag_nonzero():
    flagged = FeatureNode(
        node_id="a", node_type="CALL", code="x", line=5,
        static_flags={"is_sink_like": 1},
    )
    unflagged = FeatureNode(
        node_id="b", node_type="CALL", code="y", line=6,
        static_flags={"is_sink_like": 0},
    )
    scores = compute_line_scores(_feature(nodes=[flagged, unflagged]), [], None)
    assert 5 in scores
    assert 6 not in scores


def test_top_k_sorted_by_score_then_line():
    scores = {10: 0.9, 20: 0.9, 5: 0.5, 30: 1.0}
    # 30 highest; 10 & 20 tie -> ascending line; then 5.
    assert top_k_lines(scores, k=3) == [30, 10, 20]


def test_top_k_non_positive_returns_empty():
    assert top_k_lines({1: 0.9}, k=0) == []
    assert top_k_lines({1: 0.9}, k=-1) == []


def test_top_k_limits_results():
    scores = {i: 1.0 - i / 100 for i in range(1, 20)}
    assert len(top_k_lines(scores, k=5)) == 5
