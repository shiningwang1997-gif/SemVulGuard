"""JSONL round-trip and fixture-loading tests."""

from __future__ import annotations

from pathlib import Path

from semvulguard.schemas.records import (
    LLMVerdict,
    SampleRecord,
    StaticAlertRecord,
)
from semvulguard.utils.jsonl import read_jsonl, read_models, write_jsonl


def test_write_then_read_dicts_round_trip(tmp_path: Path):
    records = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
    out = tmp_path / "out.jsonl"
    n = write_jsonl(out, records)
    assert n == 2
    assert list(read_jsonl(out)) == records


def test_write_creates_parent_dirs(tmp_path: Path):
    out = tmp_path / "nested" / "deep" / "out.jsonl"
    write_jsonl(out, [{"k": "v"}])
    assert out.exists()


def test_read_jsonl_skips_blank_lines(tmp_path: Path):
    out = tmp_path / "blanks.jsonl"
    out.write_text('{"a": 1}\n\n   \n{"a": 2}\n', encoding="utf-8")
    assert list(read_jsonl(out)) == [{"a": 1}, {"a": 2}]


def test_model_round_trip(tmp_path: Path):
    samples = [
        SampleRecord(
            sample_id="s1",
            dataset="d",
            language="C",
            file="a.c",
            span={"file": "a.c", "start_line": 1, "end_line": 5},
            label=1,
            cwe=["CWE-119"],
            split="train",
        ),
        SampleRecord(
            sample_id="s2",
            dataset="d",
            language="cpp",
            file="b.cpp",
            span={"file": "b.cpp", "start_line": 3, "end_line": 9},
            label=0,
            split="test",
        ),
    ]
    out = tmp_path / "samples.jsonl"
    write_jsonl(out, samples)
    loaded = read_models(out, SampleRecord)
    assert loaded == samples
    assert loaded[0].language == "c"


def test_read_sample_fixtures(fixtures_dir: Path):
    records = read_models(fixtures_dir / "sample_records.jsonl", SampleRecord)
    assert len(records) == 3
    assert records[0].sample_id == "diversevul_000123"
    assert all(r.language in {"c", "cpp"} for r in records)


def test_read_static_alert_fixtures(fixtures_dir: Path):
    alerts = read_models(fixtures_dir / "static_alerts.jsonl", StaticAlertRecord)
    assert len(alerts) == 2
    assert alerts[0].tool == "codeql"


def test_read_llm_verdict_fixtures(fixtures_dir: Path):
    verdicts = read_models(fixtures_dir / "llm_verdicts.jsonl", LLMVerdict)
    assert len(verdicts) == 2
    assert {v.verdict for v in verdicts} == {"vulnerable", "benign"}
