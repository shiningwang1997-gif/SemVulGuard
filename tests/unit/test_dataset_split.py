"""Tests for split assignment."""

from __future__ import annotations

from collections import Counter

from semvulguard.dataset.split import assign_random_split, assign_time_split
from semvulguard.schemas.records import CodeSpan, SampleRecord


def _samples(n: int) -> list[SampleRecord]:
    return [
        SampleRecord(
            sample_id=f"s{i:03d}",
            dataset="devign",
            language="c",
            file="a.c",
            span=CodeSpan(file="a.c", start_line=1, end_line=1),
            label=i % 2,
            split="unknown",
        )
        for i in range(n)
    ]


def test_random_split_is_deterministic():
    samples = _samples(20)
    a = assign_random_split(samples, seed=42)
    b = assign_random_split(samples, seed=42)
    assert [s.split for s in a] == [s.split for s in b]


def test_random_split_changes_with_seed():
    samples = _samples(50)
    a = assign_random_split(samples, seed=1)
    b = assign_random_split(samples, seed=2)
    assert [s.split for s in a] != [s.split for s in b]


def test_random_split_ratios_and_values():
    samples = _samples(100)
    out = assign_random_split(samples, 0.7, 0.1, 0.2, seed=42)
    counts = Counter(s.split for s in out)
    assert counts["train"] == 70
    assert counts["valid"] == 10
    assert counts["test"] == 20
    assert set(counts) <= {"train", "valid", "test"}


def test_random_split_does_not_mutate_input():
    samples = _samples(10)
    assign_random_split(samples, seed=42)
    assert all(s.split == "unknown" for s in samples)


def test_time_split_orders_by_timestamp():
    samples = _samples(10)
    # Reverse-chronological timestamps: s009 earliest .. s000 latest.
    time_lookup = {f"s{i:03d}": float(10 - i) for i in range(10)}
    out = assign_time_split(samples, time_lookup, 0.7, 0.1, 0.2)
    split_by_id = {s.sample_id: s.split for s in out}
    # Earliest (largest negative order) become train, latest become test.
    assert split_by_id["s009"] == "train"
    assert split_by_id["s000"] == "test"


def test_time_split_fallback_stable_by_sample_id():
    samples = _samples(10)
    a = assign_time_split(samples, time_lookup=None)
    b = assign_time_split(samples, time_lookup=None)
    assert [s.split for s in a] == [s.split for s in b]
    # With no timestamps, ordering is by sample_id, so s000 sorts first.
    split_by_id = {s.sample_id: s.split for s in a}
    assert split_by_id["s000"] == "train"
    assert split_by_id["s009"] == "test"
