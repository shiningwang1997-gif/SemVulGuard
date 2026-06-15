"""Tests for deduplication helpers."""

from __future__ import annotations

from pathlib import Path

from semvulguard.dataset.dedup import (
    deduplicate_samples,
    exact_hash,
    normalized_code_hash,
)
from semvulguard.dataset.diversevul import DiverseVulLoader
from semvulguard.schemas.records import CodeSpan, SampleRecord


def _sample(sample_id: str, label: int = 1) -> SampleRecord:
    return SampleRecord(
        sample_id=sample_id,
        dataset="diversevul",
        language="c",
        file="a.c",
        span=CodeSpan(file="a.c", start_line=1, end_line=1),
        label=label,
        split="unknown",
    )


def test_exact_hash_stable_and_distinct():
    assert exact_hash("abc") == exact_hash("abc")
    assert exact_hash("abc") != exact_hash("abd")


def test_normalized_hash_ignores_comments_and_whitespace():
    a = "int f() {\n    return 0;\n}"
    b = "int f() {\n    // a comment\n    return 0;   }"
    c = "int f() {\n    /* block */ return 0; }"
    assert normalized_code_hash(a) == normalized_code_hash(b)
    assert normalized_code_hash(a) == normalized_code_hash(c)


def test_normalized_hash_preserves_identifier_case():
    assert normalized_code_hash("int Foo;") != normalized_code_hash("int foo;")


def test_deduplicate_exact_keeps_first():
    samples = [_sample("s1"), _sample("s2"), _sample("s3")]
    code_lookup = {"s1": "code A", "s2": "code A", "s3": "code B"}
    unique = deduplicate_samples(samples, code_lookup, mode="exact")
    assert [s.sample_id for s in unique] == ["s1", "s3"]


def test_deduplicate_normalized_collapses_cosmetic_dups():
    samples = [_sample("s1"), _sample("s2")]
    code_lookup = {
        "s1": "int f() { return 0; }",
        "s2": "int f() {\n   // hi\n   return 0;\n}",
    }
    exact = deduplicate_samples(samples, code_lookup, mode="exact")
    normalized = deduplicate_samples(samples, code_lookup, mode="normalized")
    assert len(exact) == 2  # differ byte-for-byte
    assert len(normalized) == 1  # same after normalization


def test_deduplicate_on_diversevul_fixture(fixtures_dir: Path):
    loader = DiverseVulLoader()
    samples = loader.load(fixtures_dir / "datasets" / "diversevul_sample.jsonl")
    # Fixture rows 5002 and 5003 share an identical BN_bin2bn body.
    unique = deduplicate_samples(samples, loader.code_lookup, mode="exact")
    assert len(unique) == len(samples) - 1
    assert "diversevul_5003" not in {s.sample_id for s in unique}
