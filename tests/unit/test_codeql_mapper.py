"""Tests for mapping alerts to samples, plus the SARIF parser CLI."""

from __future__ import annotations

from pathlib import Path

from semvulguard.schemas.records import (
    CodeSpan,
    SampleRecord,
    StaticAlertRecord,
)
from semvulguard.static.codeql.mapper import map_alerts_to_samples
from semvulguard.static.codeql.sarif import main as sarif_main
from semvulguard.utils.jsonl import read_models


def _alert(file: str, start: int, end: int, query: str = "q") -> StaticAlertRecord:
    return StaticAlertRecord(
        sample_id="unknown",
        tool="codeql",
        query_id=query,
        message="m",
        file=file,
        start_line=start,
        end_line=end,
    )


def _sample(
    sample_id: str, file: str, start: int, end: int
) -> SampleRecord:
    return SampleRecord(
        sample_id=sample_id,
        dataset="devign",
        language="c",
        file=file,
        span=CodeSpan(file=file, start_line=start, end_line=end),
        label=1,
        split="unknown",
    )


def test_map_by_exact_path_and_overlap():
    alerts = [_alert("ssl/s3_pkt.c", 145, 146)]
    samples = [_sample("s1", "ssl/s3_pkt.c", 120, 219)]
    mapping = map_alerts_to_samples(alerts, samples)
    assert set(mapping) == {"s1"}
    assert mapping["s1"][0].sample_id == "s1"


def test_map_by_suffix_path():
    # Alert path is absolute; sample path is repo-relative.
    alerts = [_alert("/build/src/ssl/s3_pkt.c", 145, 146)]
    samples = [_sample("s1", "ssl/s3_pkt.c", 120, 219)]
    mapping = map_alerts_to_samples(alerts, samples)
    assert "s1" in mapping


def test_no_overlap_is_unmatched():
    alerts = [_alert("a.c", 500, 510)]
    samples = [_sample("s1", "a.c", 1, 50)]
    mapping, unmatched = map_alerts_to_samples(
        alerts, samples, return_unmatched=True
    )
    assert mapping == {}
    assert len(unmatched) == 1


def test_narrowest_span_wins_on_multiple_matches():
    alerts = [_alert("a.c", 30, 31)]
    wide = _sample("wide", "a.c", 1, 100)
    narrow = _sample("narrow", "a.c", 25, 40)
    mapping = map_alerts_to_samples(alerts, [wide, narrow])
    assert set(mapping) == {"narrow"}


def test_return_unmatched_flag_default_is_dict_only():
    alerts = [_alert("a.c", 5, 6)]
    samples = [_sample("s1", "a.c", 1, 50)]
    result = map_alerts_to_samples(alerts, samples)
    assert isinstance(result, dict)


def test_multiple_alerts_same_sample_grouped():
    alerts = [_alert("a.c", 5, 6, "q1"), _alert("a.c", 10, 12, "q2")]
    samples = [_sample("s1", "a.c", 1, 50)]
    mapping = map_alerts_to_samples(alerts, samples)
    assert len(mapping["s1"]) == 2


def test_sarif_cli_writes_alert_jsonl(fixtures_dir: Path, tmp_path: Path, capsys):
    out = tmp_path / "alerts.jsonl"
    rc = sarif_main(
        [
            "--sarif",
            str(fixtures_dir / "codeql" / "sample_codeql.sarif"),
            "--output",
            str(out),
        ]
    )
    assert rc == 0
    alerts = read_models(out, StaticAlertRecord)
    assert len(alerts) == 2
    assert alerts[0].query_id == "cpp/overflow-buffer"
    assert "parsed 2 alerts" in capsys.readouterr().out


def test_sarif_cli_applies_sample_id(fixtures_dir: Path, tmp_path: Path):
    out = tmp_path / "alerts.jsonl"
    sarif_main(
        [
            "--sarif",
            str(fixtures_dir / "codeql" / "sample_codeql_path.sarif"),
            "--output",
            str(out),
            "--sample-id",
            "diversevul_5001",
        ]
    )
    alerts = read_models(out, StaticAlertRecord)
    assert alerts[0].sample_id == "diversevul_5001"
    assert alerts[0].trace_lines == [132, 140, 145]
