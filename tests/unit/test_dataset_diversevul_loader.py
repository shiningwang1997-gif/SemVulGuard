"""Tests for the DiverseVul loader."""

from __future__ import annotations

from pathlib import Path

from semvulguard.dataset.diversevul import DiverseVulLoader
from semvulguard.schemas.records import SampleRecord


def _load(fixtures_dir: Path) -> list[SampleRecord]:
    loader = DiverseVulLoader()
    return loader.load(fixtures_dir / "datasets" / "diversevul_sample.jsonl")


def test_diversevul_produces_sample_records(fixtures_dir: Path):
    samples = _load(fixtures_dir)
    assert len(samples) == 4
    assert all(isinstance(s, SampleRecord) for s in samples)
    assert all(s.dataset == "diversevul" for s in samples)


def test_diversevul_sample_id_from_id(fixtures_dir: Path):
    samples = _load(fixtures_dir)
    assert samples[0].sample_id == "diversevul_5001"


def test_diversevul_sample_id_hash_when_no_id(fixtures_dir: Path):
    samples = _load(fixtures_dir)
    last = samples[-1]
    assert last.sample_id.startswith("diversevul_")
    assert len(last.sample_id.split("_")[-1]) == 16


def test_diversevul_labels(fixtures_dir: Path):
    samples = _load(fixtures_dir)
    assert samples[0].label == 1
    assert samples[1].label == 0
    assert samples[3].label == 1


def test_diversevul_cwe_and_function(fixtures_dir: Path):
    samples = _load(fixtures_dir)
    assert samples[0].cwe == ["CWE-416"]
    assert samples[0].function == "ssl3_get_key_exchange"
    assert samples[3].cwe == ["CWE-134"]
