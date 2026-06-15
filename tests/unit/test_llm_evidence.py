"""Tests for the static-evidence collector."""

from __future__ import annotations

from semvulguard.llm.evidence import EvidenceCollector
from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import CodeSpan, StaticAlertRecord


def _feature() -> FeatureRecord:
    # Absolute lines: 10 def, 11 buf, 12 memcpy, 13 recv, 14 free, 15 return.
    return FeatureRecord(
        sample_id="s1",
        label=1,
        cwe=["CWE-119"],
        file="a.c",
        function="f",
        span=CodeSpan(file="a.c", start_line=10, end_line=15),
        function_code="...",
        code_lines=[
            "void f(int fd) {",
            "    char buf[64];",
            "    memcpy(buf, src, n);",
            "    recv(fd, buf, 64);",
            "    free(buf);",
            "    return;",
        ],
        alert_lines=[12],
        trace_lines=[11, 12],
        static_features={"language": "c"},
    )


def _alert() -> StaticAlertRecord:
    return StaticAlertRecord(
        sample_id="s1",
        tool="codeql",
        query_id="cpp/unbounded-write",
        message="Unbounded write",
        severity="high",
        file="a.c",
        start_line=12,
        end_line=12,
        cwe=["CWE-119"],
        trace_lines=[11, 12],
    )


def test_collect_basic_shape():
    summary = EvidenceCollector().collect(_feature(), [_alert()], rank_score=0.8)
    assert summary["sample_id"] == "s1"
    assert summary["static_alert_count"] == 1
    assert summary["rank_score"] == 0.8
    assert summary["function_span"] == {
        "file": "a.c",
        "start_line": 10,
        "end_line": 15,
    }
    assert "memcpy" in summary["code_excerpt"]


def test_dangerous_api_lines_detected():
    summary = EvidenceCollector().collect(_feature(), [], rank_score=None)
    # memcpy@12, recv? (recv is source not dangerous), free@14, also malloc/etc.
    assert 12 in summary["dangerous_api_lines"]  # memcpy
    assert 14 in summary["dangerous_api_lines"]  # free


def test_source_and_sink_lines_detected():
    summary = EvidenceCollector().collect(_feature(), [], rank_score=None)
    # recv@13 is source-like; memcpy@12 and free@14 are sink-like.
    assert 13 in summary["source_like_lines"]
    assert 12 in summary["sink_like_lines"]
    assert 14 in summary["sink_like_lines"]


def test_trace_lines_merged_and_sorted():
    summary = EvidenceCollector().collect(_feature(), [_alert()], rank_score=None)
    assert summary["trace_lines"] == [11, 12]


def test_alert_summaries_compact():
    summary = EvidenceCollector().collect(_feature(), [_alert()], rank_score=None)
    alert = summary["alert_summaries"][0]
    assert alert["query_id"] == "cpp/unbounded-write"
    assert alert["severity"] == "high"
    assert alert["cwe"] == ["CWE-119"]


def test_collect_is_deterministic():
    collector = EvidenceCollector()
    a = collector.collect(_feature(), [_alert()], rank_score=0.5)
    b = collector.collect(_feature(), [_alert()], rank_score=0.5)
    assert a == b


def test_joern_evidence_summarized():
    summary = EvidenceCollector().collect(
        _feature(), [], rank_score=None, joern_evidence={"sinks": ["memcpy"]}
    )
    assert summary["joern_summary"] == {"sinks": ["memcpy"]}


def test_does_not_call_llm():
    # The collector has no client and never imports one; smoke test that
    # collection works in complete isolation.
    summary = EvidenceCollector().collect(_feature(), [], rank_score=None)
    assert isinstance(summary, dict)
