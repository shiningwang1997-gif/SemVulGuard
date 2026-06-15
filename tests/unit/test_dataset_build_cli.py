"""Tests for the dataset build CLI."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from semvulguard.dataset.build import build_manifest, compute_stats, main
from semvulguard.schemas.records import SampleRecord
from semvulguard.utils.jsonl import read_models


def _devign_input(fixtures_dir: Path) -> Path:
    return fixtures_dir / "datasets" / "devign_sample.jsonl"


def test_build_manifest_keep_split(fixtures_dir: Path):
    samples, code_lookup = build_manifest(
        "devign", _devign_input(fixtures_dir), split="keep"
    )
    assert len(samples) == 4
    assert all(isinstance(s, SampleRecord) for s in samples)
    assert code_lookup


def test_build_manifest_random_split_assigns(fixtures_dir: Path):
    samples, _ = build_manifest(
        "devign", _devign_input(fixtures_dir), split="random", seed=42
    )
    assert all(s.split in {"train", "valid", "test"} for s in samples)


def test_compute_stats(fixtures_dir: Path):
    samples, _ = build_manifest("devign", _devign_input(fixtures_dir), split="keep")
    stats = compute_stats(samples)
    assert stats["total"] == 4
    assert stats["vulnerable"] == 2
    assert stats["benign"] == 2
    assert stats["cwe"]["CWE-119"] == 1


def test_cli_main_writes_jsonl(fixtures_dir: Path, tmp_path: Path, capsys):
    out = tmp_path / "manifest.jsonl"
    rc = main(
        [
            "--dataset",
            "devign",
            "--input",
            str(_devign_input(fixtures_dir)),
            "--output",
            str(out),
            "--split",
            "random",
        ]
    )
    assert rc == 0
    assert out.exists()
    loaded = read_models(out, SampleRecord)
    assert len(loaded) == 4
    captured = capsys.readouterr()
    assert "total samples : 4" in captured.out


def test_cli_main_with_dedup(fixtures_dir: Path, tmp_path: Path):
    out = tmp_path / "manifest.jsonl"
    main(
        [
            "--dataset",
            "diversevul",
            "--input",
            str(fixtures_dir / "datasets" / "diversevul_sample.jsonl"),
            "--output",
            str(out),
            "--dedup",
            "exact",
        ]
    )
    loaded = read_models(out, SampleRecord)
    # One exact-duplicate body collapses (5002 / 5003).
    assert len(loaded) == 3
    counts = Counter(s.dataset for s in loaded)
    assert counts["diversevul"] == 3
