"""Tests for line-level localization metrics."""

from __future__ import annotations

import pytest

from semvulguard.eval.localization import (
    compute_iou,
    compute_localization_metrics,
    compute_topk_line_hit,
)


def test_topk_hit_true_within_k():
    assert compute_topk_line_hit([10, 20, 30], [20], k=2) == 1


def test_topk_hit_false_outside_k():
    # The true line 30 is the 3rd prediction; k=2 misses it.
    assert compute_topk_line_hit([10, 20, 30], [30], k=2) == 0


def test_topk_hit_empty_ground_truth():
    assert compute_topk_line_hit([10], [], k=1) == 0


def test_topk_hit_non_positive_k():
    assert compute_topk_line_hit([10], [10], k=0) == 0


def test_iou_full_overlap():
    assert compute_iou([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)


def test_iou_partial_overlap():
    # intersection {2}, union {1,2,3} -> 1/3
    assert compute_iou([1, 2], [2, 3]) == pytest.approx(1 / 3)


def test_iou_no_overlap():
    assert compute_iou([1], [2]) == 0.0


def test_iou_both_empty():
    assert compute_iou([], []) == 0.0


def test_localization_metrics_aggregate():
    predictions = {
        "s1": [10, 11],
        "s2": [5, 4],
        "s3": [99],  # miss
    }
    ground_truth = {
        "s1": [10, 11],
        "s2": [5],
        "s3": [7, 8],
    }
    m = compute_localization_metrics(predictions, ground_truth, k_values=[1, 3, 5])
    # s1 top1 hit (10), s2 top1 hit (5), s3 miss -> 2/3
    assert m["top1_hit_rate"] == pytest.approx(2 / 3)
    assert m["top3_hit_rate"] == pytest.approx(2 / 3)
    # mean IoU: s1=1.0, s2=1/2, s3=0 -> 0.5
    assert m["mean_iou"] == pytest.approx((1.0 + 0.5 + 0.0) / 3)
    assert m["coverage"] == pytest.approx(1.0)
    assert m["num_samples"] == 3


def test_localization_missing_prediction_counts_as_miss():
    predictions = {"s1": [10]}
    ground_truth = {"s1": [10], "s2": [3]}
    m = compute_localization_metrics(predictions, ground_truth, k_values=[1])
    # s2 has no prediction -> miss, coverage 1/2.
    assert m["top1_hit_rate"] == pytest.approx(0.5)
    assert m["coverage"] == pytest.approx(0.5)


def test_localization_empty_ground_truth():
    m = compute_localization_metrics({}, {}, k_values=[1, 3, 5])
    assert m["top1_hit_rate"] == 0.0
    assert m["mean_iou"] == 0.0
    assert m["coverage"] == 0.0
    assert m["num_samples"] == 0
