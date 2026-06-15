"""Tests for the CodeQL SARIF parser."""

from __future__ import annotations

from pathlib import Path

from semvulguard.schemas.records import StaticAlertRecord
from semvulguard.static.codeql.sarif import (
    parse_sarif,
    sarif_to_static_alerts,
)


def _ordinary(fixtures_dir: Path) -> Path:
    return fixtures_dir / "codeql" / "sample_codeql.sarif"


def _path(fixtures_dir: Path) -> Path:
    return fixtures_dir / "codeql" / "sample_codeql_path.sarif"


def test_parse_sarif_ordinary_results(fixtures_dir: Path):
    results = parse_sarif(_ordinary(fixtures_dir))
    assert len(results) == 2
    assert results[0]["rule_id"] == "cpp/overflow-buffer"
    assert results[0]["message"] == "This buffer write may overflow."
    assert results[0]["locations"][0]["uri"] == "net/core/skbuff.c"
    assert results[0]["locations"][0]["start_line"] == 145
    assert results[0]["locations"][0]["end_line"] == 146


def test_parse_sarif_rule_index_fallback(fixtures_dir: Path):
    # Second result has no ruleId, only ruleIndex -> resolved via rules table.
    results = parse_sarif(_ordinary(fixtures_dir))
    assert results[1]["rule_id"] == "cpp/unused-local-variable"


def test_ordinary_alerts_are_static_alert_records(fixtures_dir: Path):
    alerts = sarif_to_static_alerts(_ordinary(fixtures_dir))
    assert len(alerts) == 2
    assert all(isinstance(a, StaticAlertRecord) for a in alerts)
    assert all(a.tool == "codeql" for a in alerts)
    assert all(a.sample_id == "unknown" for a in alerts)


def test_default_sample_id_is_applied(fixtures_dir: Path):
    alerts = sarif_to_static_alerts(_ordinary(fixtures_dir), default_sample_id="s1")
    assert all(a.sample_id == "s1" for a in alerts)


def test_cwe_extracted_from_tags(fixtures_dir: Path):
    alerts = sarif_to_static_alerts(_ordinary(fixtures_dir))
    assert alerts[0].cwe == ["CWE-119", "CWE-787"]
    # The maintainability rule carries no CWE tags.
    assert alerts[1].cwe == []


def test_severity_from_level(fixtures_dir: Path):
    alerts = sarif_to_static_alerts(_ordinary(fixtures_dir))
    assert alerts[0].severity == "error"


def test_missing_end_line_defaults_to_start(fixtures_dir: Path):
    alerts = sarif_to_static_alerts(_ordinary(fixtures_dir))
    # Second result region has only startLine.
    assert alerts[1].start_line == 12
    assert alerts[1].end_line == 12


def test_path_query_trace_lines(fixtures_dir: Path):
    alerts = sarif_to_static_alerts(_path(fixtures_dir))
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.query_id == "cpp/tainted-buffer-access"
    assert alert.trace_lines == [132, 140, 145]
    assert alert.cwe == ["CWE-416"]
    assert alert.file == "ssl/s3_pkt.c"
    assert alert.start_line == 145
    assert alert.end_line == 146


def test_raw_result_preserved(fixtures_dir: Path):
    alerts = sarif_to_static_alerts(_ordinary(fixtures_dir))
    assert alerts[0].raw is not None
    assert alerts[0].raw["ruleId"] == "cpp/overflow-buffer"


def test_empty_runs_yield_no_alerts(tmp_path: Path):
    empty = tmp_path / "empty.sarif"
    empty.write_text('{"version": "2.1.0", "runs": []}', encoding="utf-8")
    assert sarif_to_static_alerts(empty) == []
