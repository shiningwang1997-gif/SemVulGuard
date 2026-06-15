"""Tests for the BigVul CSV loader."""

from __future__ import annotations

from pathlib import Path

from semvulguard.dataset.bigvul import BigVulLoader
from semvulguard.schemas.records import SampleRecord


def _load(fixtures_dir: Path) -> list[SampleRecord]:
    loader = BigVulLoader()
    return loader.load(fixtures_dir / "datasets" / "bigvul_sample.csv")


def test_bigvul_produces_sample_records(fixtures_dir: Path):
    samples = _load(fixtures_dir)
    assert len(samples) == 3
    assert all(isinstance(s, SampleRecord) for s in samples)
    assert all(s.dataset == "bigvul" for s in samples)


def test_bigvul_sample_id_from_id(fixtures_dir: Path):
    samples = _load(fixtures_dir)
    assert samples[0].sample_id == "bigvul_100"


def test_bigvul_label_from_vulnerable(fixtures_dir: Path):
    samples = _load(fixtures_dir)
    assert samples[0].label == 1
    assert samples[1].label == 0


def test_bigvul_uses_func_before_for_span(fixtures_dir: Path):
    loader = BigVulLoader()
    samples = loader.load(fixtures_dir / "datasets" / "bigvul_sample.csv")
    code = loader.code_lookup[samples[0].sample_id]
    assert "memcpy" in code  # taken from func_before, not func_after
    assert samples[0].span.end_line == code.count("\n") + 1


def test_bigvul_commit_and_function_fields(fixtures_dir: Path):
    samples = _load(fixtures_dir)
    assert samples[0].commit_before == "f00d01"
    assert samples[0].commit_after is None
    assert samples[0].function == "read_pkt"
    assert samples[0].repo == "linux"


def test_bigvul_cwe_parsed(fixtures_dir: Path):
    samples = _load(fixtures_dir)
    assert samples[0].cwe == ["CWE-787"]
    assert samples[1].cwe == []
