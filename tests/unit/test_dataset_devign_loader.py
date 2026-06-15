"""Tests for the Devign loader."""

from __future__ import annotations

from pathlib import Path

from semvulguard.dataset.devign import DevignLoader
from semvulguard.schemas.records import SampleRecord


def _load(fixtures_dir: Path) -> list[SampleRecord]:
    loader = DevignLoader()
    return loader.load(fixtures_dir / "datasets" / "devign_sample.jsonl")


def test_devign_produces_sample_records(fixtures_dir: Path):
    samples = _load(fixtures_dir)
    assert len(samples) == 4
    assert all(isinstance(s, SampleRecord) for s in samples)
    assert all(s.dataset == "devign" for s in samples)
    assert all(s.language == "c" for s in samples)


def test_devign_sample_id_from_idx(fixtures_dir: Path):
    samples = _load(fixtures_dir)
    assert samples[0].sample_id == "devign_0"
    assert samples[1].sample_id == "devign_1"


def test_devign_sample_id_hash_when_no_idx(fixtures_dir: Path):
    # Last fixture row has no idx -> deterministic hashed id.
    samples = _load(fixtures_dir)
    last = samples[-1]
    assert last.sample_id.startswith("devign_")
    assert last.sample_id not in {"devign_3"}
    assert len(last.sample_id.split("_")[-1]) == 16


def test_devign_labels_and_span(fixtures_dir: Path):
    samples = _load(fixtures_dir)
    assert samples[0].label == 1
    assert samples[1].label == 0
    # Span end_line equals the number of lines in the function body.
    assert samples[0].span.start_line == 1
    assert samples[0].span.end_line == 5


def test_devign_cwe_string_coerced_to_list(fixtures_dir: Path):
    samples = _load(fixtures_dir)
    assert samples[3].cwe == ["CWE-787"]


def test_devign_split_defaults_unknown(fixtures_dir: Path):
    samples = _load(fixtures_dir)
    assert samples[0].split == "train"
    assert samples[2].split == "unknown"


def test_devign_code_lookup_populated(fixtures_dir: Path):
    loader = DevignLoader()
    samples = loader.load(fixtures_dir / "datasets" / "devign_sample.jsonl")
    for sample in samples:
        assert sample.sample_id in loader.code_lookup
    assert "memcpy" in loader.code_lookup[samples[0].sample_id]
