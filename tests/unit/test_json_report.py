"""Tests for the JSON / JSONL report writers."""

from __future__ import annotations

import json
from pathlib import Path

from semvulguard.report.json_report import (
    REPORT_TOOL_NAME,
    build_report,
    write_findings_json,
    write_findings_jsonl,
)
from semvulguard.schemas.records import FinalFinding
from semvulguard.utils.jsonl import read_models


def _finding(sample_id: str, label: int, conf: float) -> FinalFinding:
    return FinalFinding(
        sample_id=sample_id,
        final_label=label,
        final_confidence=conf,
        predicted_cwe="CWE-119" if label else "",
        vulnerable_lines=[12] if label else [],
        evidence=[{"kind": "rank_score", "value": conf}],
        patch_hint="fix it" if label else "",
    )


def _findings() -> list[FinalFinding]:
    return [
        _finding("a", 1, 0.9),
        _finding("b", 0, 0.2),
        _finding("c", 1, 0.7),
    ]


def test_build_report_structure():
    report = build_report(_findings())
    assert report["metadata"]["tool"] == REPORT_TOOL_NAME
    assert report["total_findings"] == 3
    assert report["vulnerable_count"] == 2
    assert len(report["findings"]) == 3


def test_build_report_merges_metadata():
    report = build_report(_findings(), metadata={"threshold": 0.5})
    assert report["metadata"]["threshold"] == 0.5
    assert report["metadata"]["tool"] == REPORT_TOOL_NAME


def test_write_findings_json(tmp_path: Path):
    out = tmp_path / "findings.json"
    write_findings_json(_findings(), out, metadata={"threshold": 0.5})
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["total_findings"] == 3
    assert data["vulnerable_count"] == 2
    assert data["metadata"]["threshold"] == 0.5
    assert data["findings"][0]["sample_id"] == "a"


def test_write_findings_jsonl_roundtrips(tmp_path: Path):
    out = tmp_path / "findings.jsonl"
    write_findings_jsonl(_findings(), out)
    loaded = read_models(out, FinalFinding)
    assert [f.sample_id for f in loaded] == ["a", "b", "c"]
    assert loaded[0].final_label == 1


def test_json_report_is_deterministic(tmp_path: Path):
    out1 = tmp_path / "a.json"
    out2 = tmp_path / "b.json"
    write_findings_json(_findings(), out1)
    write_findings_json(_findings(), out2)
    assert out1.read_text() == out2.read_text()
