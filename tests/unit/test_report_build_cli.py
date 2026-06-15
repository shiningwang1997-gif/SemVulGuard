"""Tests for the end-to-end report build CLI."""

from __future__ import annotations

import json
from pathlib import Path

from semvulguard.report.build import build_report_artifacts
from semvulguard.report.build import main as build_main
from semvulguard.schemas.records import FinalFinding
from semvulguard.utils.jsonl import read_models


def _args(fixtures_dir: Path, out_dir: Path) -> list[str]:
    d = fixtures_dir / "fusion"
    return [
        "--features",
        str(d / "features.jsonl"),
        "--rank-scores",
        str(d / "rank_scores.jsonl"),
        "--alerts",
        str(d / "static_alerts.jsonl"),
        "--llm-verdicts",
        str(d / "llm_verdicts.jsonl"),
        "--output-dir",
        str(out_dir),
        "--threshold",
        "0.5",
    ]


def test_cli_writes_all_artifacts(fixtures_dir: Path, tmp_path: Path, capsys):
    out_dir = tmp_path / "final"
    rc = build_main(_args(fixtures_dir, out_dir))
    assert rc == 0

    for name in ("findings.json", "findings.jsonl", "findings.sarif",
                 "fusion_scores.jsonl"):
        assert (out_dir / name).exists(), name

    captured = capsys.readouterr().out
    assert "findings.sarif" in captured


def test_cli_findings_jsonl_valid(fixtures_dir: Path, tmp_path: Path):
    out_dir = tmp_path / "final"
    build_main(_args(fixtures_dir, out_dir))
    findings = read_models(out_dir / "findings.jsonl", FinalFinding)
    # One finding per feature record.
    assert len(findings) == 4
    by_id = {f.sample_id: f for f in findings}
    # The two strong cases are flagged vulnerable.
    assert by_id["fz_001"].final_label == 1
    assert by_id["fz_003"].final_label == 1
    # The clean function is benign.
    assert by_id["fz_002"].final_label == 0


def test_cli_json_report_counts(fixtures_dir: Path, tmp_path: Path):
    out_dir = tmp_path / "final"
    build_report_artifacts(
        features_path=fixtures_dir / "fusion" / "features.jsonl",
        rank_scores_path=fixtures_dir / "fusion" / "rank_scores.jsonl",
        alerts_path=fixtures_dir / "fusion" / "static_alerts.jsonl",
        llm_verdicts_path=fixtures_dir / "fusion" / "llm_verdicts.jsonl",
        output_dir=out_dir,
        threshold=0.5,
    )
    report = json.loads((out_dir / "findings.json").read_text())
    assert report["total_findings"] == 4
    assert report["vulnerable_count"] == 2
    assert report["metadata"]["threshold"] == 0.5


def test_cli_sarif_only_has_vulnerable(fixtures_dir: Path, tmp_path: Path):
    out_dir = tmp_path / "final"
    build_main(_args(fixtures_dir, out_dir))
    sarif = json.loads((out_dir / "findings.sarif").read_text())
    findings = read_models(out_dir / "findings.jsonl", FinalFinding)
    n_vuln = sum(f.final_label for f in findings)
    assert len(sarif["runs"][0]["results"]) == n_vuln
    assert sarif["version"] == "2.1.0"


def test_cli_is_deterministic(fixtures_dir: Path, tmp_path: Path):
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    build_main(_args(fixtures_dir, out1))
    build_main(_args(fixtures_dir, out2))
    assert (out1 / "findings.json").read_text() == (
        out2 / "findings.json"
    ).read_text()
    assert (out1 / "findings.sarif").read_text() == (
        out2 / "findings.sarif"
    ).read_text()
