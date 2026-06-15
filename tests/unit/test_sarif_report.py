"""Tests for SARIF 2.1.0 report generation."""

from __future__ import annotations

import json
from pathlib import Path

from semvulguard.report.sarif_report import (
    SARIF_VERSION,
    TOOL_NAME,
    final_findings_to_sarif,
    write_sarif,
)
from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import CodeSpan, FinalFinding


def _finding(sample_id, label, cwe, lines, conf=0.9) -> FinalFinding:
    return FinalFinding(
        sample_id=sample_id,
        final_label=label,
        final_confidence=conf,
        predicted_cwe=cwe,
        vulnerable_lines=lines,
        evidence=[{"kind": "rank_score", "value": conf}],
        patch_hint="bound the copy" if label else "",
    )


def _feature(sample_id, file) -> FeatureRecord:
    return FeatureRecord(
        sample_id=sample_id,
        label=1,
        cwe=[],
        file=file,
        function="f",
        span=CodeSpan(file=file, start_line=1, end_line=10),
        function_code="void f(){}",
    )


def _features_by_id():
    return {
        "a": _feature("a", "net/pkt.c"),
        "b": _feature("b", "math/add.c"),
    }


def test_sarif_top_level_shape():
    findings = [_finding("a", 1, "CWE-119", [12])]
    sarif = final_findings_to_sarif(findings, _features_by_id())
    assert sarif["version"] == SARIF_VERSION
    assert sarif["runs"][0]["tool"]["driver"]["name"] == TOOL_NAME


def test_only_vulnerable_findings_become_results():
    findings = [
        _finding("a", 1, "CWE-119", [12]),
        _finding("b", 0, "", []),
    ]
    sarif = final_findings_to_sarif(findings, _features_by_id())
    results = sarif["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["properties"]["sample_id"] == "a"


def test_rule_id_is_cwe_or_fallback():
    findings = [
        _finding("a", 1, "CWE-119", [12]),
        _finding("b", 1, "", [3]),
    ]
    sarif = final_findings_to_sarif(findings, _features_by_id())
    rule_ids = [r["ruleId"] for r in sarif["runs"][0]["results"]]
    assert rule_ids == ["CWE-119", "SemVulGuard"]


def test_result_message_includes_confidence():
    sarif = final_findings_to_sarif(
        [_finding("a", 1, "CWE-119", [12], conf=0.87)], _features_by_id()
    )
    msg = sarif["runs"][0]["results"][0]["message"]["text"]
    assert "0.87" in msg
    assert "CWE-119" in msg


def test_location_points_at_file_and_first_line():
    sarif = final_findings_to_sarif(
        [_finding("a", 1, "CWE-119", [12, 13])], _features_by_id()
    )
    loc = sarif["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"] == "net/pkt.c"
    assert loc["region"]["startLine"] == 12


def test_properties_carry_evidence_and_patch_hint():
    sarif = final_findings_to_sarif(
        [_finding("a", 1, "CWE-119", [12])], _features_by_id()
    )
    props = sarif["runs"][0]["results"][0]["properties"]
    assert props["patch_hint"] == "bound the copy"
    assert props["vulnerable_lines"] == [12]
    assert props["evidence"][0]["kind"] == "rank_score"
    assert props["final_confidence"] == 0.9


def test_missing_feature_falls_back_to_sample_id():
    sarif = final_findings_to_sarif(
        [_finding("orphan", 1, "CWE-119", [5])], {}
    )
    uri = sarif["runs"][0]["results"][0]["locations"][0][
        "physicalLocation"
    ]["artifactLocation"]["uri"]
    assert uri == "orphan"


def test_write_sarif_file(tmp_path: Path):
    out = tmp_path / "findings.sarif"
    write_sarif([_finding("a", 1, "CWE-119", [12])], _features_by_id(), out)
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["version"] == SARIF_VERSION
    assert len(data["runs"][0]["results"]) == 1
