"""Tests for cost aggregation and ablation comparison."""

from __future__ import annotations

import pytest

from semvulguard.eval.ablation import compare_ablation_results
from semvulguard.eval.cost import compute_cost_metrics


def test_cost_metrics_basic():
    records = [
        {"sample_id": "a", "total_tokens": 1000, "latency_seconds": 2.0,
         "api_cost_usd": 0.002},
        {"sample_id": "b", "total_tokens": 2000, "latency_seconds": 4.0,
         "api_cost_usd": 0.004},
    ]
    m = compute_cost_metrics(records)
    assert m["total_tokens"] == 3000
    assert m["avg_tokens_per_sample"] == 1500
    assert m["total_cost_usd"] == pytest.approx(0.006)
    assert m["avg_cost_per_sample"] == pytest.approx(0.003)
    assert m["avg_latency_seconds"] == pytest.approx(3.0)
    assert m["samples_count"] == 2


def test_cost_metrics_empty():
    m = compute_cost_metrics([])
    assert m["samples_count"] == 0
    assert m["total_tokens"] == 0.0
    assert m["p95_latency_seconds"] == 0.0


def test_cost_metrics_total_tokens_from_parts():
    records = [{"prompt_tokens": 100, "completion_tokens": 50}]
    m = compute_cost_metrics(records)
    assert m["total_tokens"] == 150


def test_cost_metrics_missing_fields_graceful():
    records = [
        {"sample_id": "a", "total_tokens": 500},  # no latency, no cost
        {"sample_id": "b", "latency_seconds": 1.0},  # no tokens, no cost
    ]
    m = compute_cost_metrics(records)
    assert m["total_tokens"] == 500
    assert m["total_cost_usd"] == 0.0
    # Only one record has latency; average over present values.
    assert m["avg_latency_seconds"] == pytest.approx(1.0)
    assert m["samples_count"] == 2


def test_cost_p95_latency():
    records = [{"latency_seconds": float(i)} for i in range(1, 101)]
    m = compute_cost_metrics(records)
    # p95 of 1..100 via linear interpolation ~ 95.05
    assert m["p95_latency_seconds"] == pytest.approx(95.05, abs=0.1)


def test_ablation_sorted_with_delta_against_full():
    results = {
        "static_only": {"f1": 0.3, "mcc": 0.2},
        "ranker_only": {"f1": 0.45, "mcc": 0.31},
        "full": {"f1": 0.58, "mcc": 0.44},
    }
    rows = compare_ablation_results(results, metric="f1")
    # Sorted descending by f1.
    assert [r["config"] for r in rows] == ["full", "ranker_only", "static_only"]
    assert [r["rank"] for r in rows] == [1, 2, 3]
    # Reference is "full"; its delta is 0.
    full_row = rows[0]
    assert full_row["is_reference"] is True
    assert full_row["delta"] == pytest.approx(0.0)
    # static_only delta vs full.
    static_row = rows[-1]
    assert static_row["delta"] == pytest.approx(0.3 - 0.58)


def test_ablation_custom_metric_and_baseline():
    results = {
        "a": {"f1": 0.5, "mcc": 0.1},
        "b": {"f1": 0.2, "mcc": 0.4},
    }
    rows = compare_ablation_results(results, metric="mcc", baseline="a")
    # Sorted by mcc: b (0.4) then a (0.1).
    assert [r["config"] for r in rows] == ["b", "a"]
    b_row = next(r for r in rows if r["config"] == "b")
    assert b_row["delta"] == pytest.approx(0.4 - 0.1)


def test_ablation_missing_metric_value():
    results = {"a": {"f1": 0.5}, "b": {"mcc": 0.3}}
    rows = compare_ablation_results(results, metric="f1")
    # b has no f1 -> treated as 0.0 for ordering, value None.
    b_row = next(r for r in rows if r["config"] == "b")
    assert b_row["value"] is None
