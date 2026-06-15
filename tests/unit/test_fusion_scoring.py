"""Tests for fusion scoring: static/LLM/final scores, labels, and CWE choice."""

from __future__ import annotations

from pathlib import Path

from semvulguard.models.fusion.scoring import (
    DEFAULT_FUSION_WEIGHTS,
    build_final_finding,
    compute_final_score,
    compute_llm_score,
    compute_static_score,
    final_label_from_score,
    select_predicted_cwe,
)
from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import (
    CodeSpan,
    FinalFinding,
    LLMVerdict,
    StaticAlertRecord,
)
from semvulguard.utils.jsonl import read_models


def _alert(severity="high", trace=None, cwe=None, **kw) -> StaticAlertRecord:
    return StaticAlertRecord(
        sample_id=kw.get("sample_id", "s1"),
        tool=kw.get("tool", "codeql"),
        query_id=kw.get("query_id", "q"),
        message="m",
        severity=severity,
        file="a.c",
        start_line=kw.get("start_line", 10),
        end_line=kw.get("end_line", 10),
        cwe=cwe or [],
        trace_lines=trace or [],
    )


def _verdict(verdict="vulnerable", confidence=0.9, cwe="CWE-119") -> LLMVerdict:
    return LLMVerdict(
        sample_id="s1",
        verdict=verdict,
        confidence=confidence,
        predicted_cwe=cwe,
        vulnerable_lines=[],
        evidence=[],
        need_more_context=False,
        missing_context=[],
        patch_hint="",
    )


def _feature(sample_id="s1", cwe=None) -> FeatureRecord:
    return FeatureRecord(
        sample_id=sample_id,
        label=1,
        cwe=cwe or [],
        file="a.c",
        function="f",
        span=CodeSpan(file="a.c", start_line=10, end_line=20),
        function_code="void f(){}",
    )


# -- static score -----------------------------------------------------------

def test_static_score_zero_without_alerts():
    assert compute_static_score([]) == 0.0


def test_static_score_in_unit_interval():
    alerts = [_alert("high", trace=[1, 2]) for _ in range(10)]
    score = compute_static_score(alerts)
    assert 0.0 <= score <= 1.0


def test_static_score_severity_monotonic():
    high = compute_static_score([_alert("high")])
    medium = compute_static_score([_alert("medium")])
    low = compute_static_score([_alert("low")])
    unknown = compute_static_score([_alert("mystery")])
    assert high > medium > low > unknown


def test_static_score_trace_bonus():
    without = compute_static_score([_alert("low")])
    with_trace = compute_static_score([_alert("low", trace=[1, 2])])
    assert with_trace > without


# -- llm score --------------------------------------------------------------

def test_llm_score_missing_verdict():
    assert compute_llm_score(None) == 0.0


def test_llm_score_vulnerable_is_confidence():
    assert compute_llm_score(_verdict("vulnerable", 0.83)) == 0.83


def test_llm_score_benign_is_capped_low():
    assert compute_llm_score(_verdict("benign", 0.9)) <= 0.3
    assert compute_llm_score(_verdict("benign", 0.5)) <= 0.3


def test_llm_score_uncertain_is_bounded():
    score = compute_llm_score(_verdict("uncertain", 0.6))
    assert 0.0 < score <= 0.3


# -- final score ------------------------------------------------------------

def test_final_score_in_unit_interval():
    assert compute_final_score(1.0, 1.0, 1.0) == 1.0
    assert compute_final_score(0.0, 0.0, 0.0) == 0.0


def test_final_score_uses_default_weights():
    score = compute_final_score(1.0, 0.0, 0.0)
    assert score == DEFAULT_FUSION_WEIGHTS["static"]


def test_final_score_monotonic_in_each_signal():
    base = compute_final_score(0.2, 0.2, 0.2)
    assert compute_final_score(0.9, 0.2, 0.2) > base
    assert compute_final_score(0.2, 0.9, 0.2) > base
    assert compute_final_score(0.2, 0.2, 0.9) > base


def test_final_label_threshold():
    assert final_label_from_score(0.5) == 1
    assert final_label_from_score(0.49) == 0
    assert final_label_from_score(0.8, threshold=0.9) == 0


# -- cwe selection ----------------------------------------------------------

def test_cwe_priority_llm_first():
    cwe = select_predicted_cwe(
        [_alert(cwe=["CWE-416"])], _verdict(cwe="CWE-119"), _feature(cwe=["CWE-787"])
    )
    assert cwe == "CWE-119"


def test_cwe_falls_back_to_most_common_alert():
    alerts = [
        _alert(cwe=["CWE-416"]),
        _alert(cwe=["CWE-416"]),
        _alert(cwe=["CWE-119"]),
    ]
    cwe = select_predicted_cwe(alerts, _verdict(cwe=""), _feature(cwe=["CWE-787"]))
    assert cwe == "CWE-416"


def test_cwe_falls_back_to_feature_cwe():
    cwe = select_predicted_cwe([], _verdict(cwe=""), _feature(cwe=["CWE-787"]))
    assert cwe == "CWE-787"


def test_cwe_unknown_when_nothing_available():
    assert select_predicted_cwe([], None, _feature(cwe=[])) == "unknown"


# -- final finding ----------------------------------------------------------

def test_build_final_finding_shape(fixtures_dir: Path):
    features = read_models(
        fixtures_dir / "fusion" / "features.jsonl", FeatureRecord
    )
    feature = next(f for f in features if f.sample_id == "fz_001")
    alerts = [a for a in _fusion_alerts(fixtures_dir) if a.sample_id == "fz_001"]
    finding = build_final_finding(
        feature_record=feature,
        rank_score=0.92,
        alerts=alerts,
        llm_verdict=_verdict("vulnerable", 0.93, "CWE-787"),
    )
    assert isinstance(finding, FinalFinding)
    assert finding.sample_id == "fz_001"
    assert finding.final_label == 1
    assert 0.0 <= finding.final_confidence <= 1.0
    assert finding.predicted_cwe == "CWE-787"
    # Evidence carries the required pieces.
    kinds = {e["kind"] for e in finding.evidence}
    assert {"static_alert", "trace_lines", "llm_verdict", "rank_score",
            "fusion_scores"} <= kinds


def test_build_final_finding_benign_low_score(fixtures_dir: Path):
    features = read_models(
        fixtures_dir / "fusion" / "features.jsonl", FeatureRecord
    )
    feature = next(f for f in features if f.sample_id == "fz_002")
    finding = build_final_finding(
        feature_record=feature,
        rank_score=0.05,
        alerts=[],
        llm_verdict=_verdict("benign", 0.88, ""),
    )
    assert finding.final_label == 0
    assert finding.final_confidence < 0.5


def _fusion_alerts(fixtures_dir: Path):
    return read_models(
        fixtures_dir / "fusion" / "static_alerts.jsonl", StaticAlertRecord
    )
