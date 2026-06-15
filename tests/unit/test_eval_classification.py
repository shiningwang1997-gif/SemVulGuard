"""Tests for binary classification metrics."""

from __future__ import annotations

import math

import pytest

from semvulguard.eval.classification import (
    compute_binary_classification_metrics,
)


def test_perfect_classification():
    y_true = [1, 1, 0, 0]
    y_score = [0.9, 0.8, 0.2, 0.1]
    m = compute_binary_classification_metrics(y_true, y_score, threshold=0.5)
    assert m["accuracy"] == 1.0
    assert m["precision"] == 1.0
    assert m["recall"] == 1.0
    assert m["f1"] == 1.0
    assert m["mcc"] == 1.0
    assert m["confusion_matrix"] == {"tp": 2, "fp": 0, "tn": 2, "fn": 0}


def test_confusion_matrix_counts():
    # scores: pred = [1,1,1,0] vs true [1,0,1,1]
    y_true = [1, 0, 1, 1]
    y_score = [0.8, 0.7, 0.6, 0.2]
    m = compute_binary_classification_metrics(y_true, y_score, threshold=0.5)
    cm = m["confusion_matrix"]
    assert cm == {"tp": 2, "fp": 1, "tn": 0, "fn": 1}
    assert m["precision"] == pytest.approx(2 / 3)
    assert m["recall"] == pytest.approx(2 / 3)


def test_mcc_known_small_case():
    # tp=1, fp=1, tn=1, fn=1 -> MCC = 0.
    y_true = [1, 0, 1, 0]
    y_score = [0.9, 0.9, 0.1, 0.1]
    m = compute_binary_classification_metrics(y_true, y_score, threshold=0.5)
    assert m["confusion_matrix"] == {"tp": 1, "fp": 1, "tn": 1, "fn": 1}
    assert m["mcc"] == pytest.approx(0.0)


def test_mcc_nonzero_known_value():
    # tp=2, tn=1, fp=0, fn=1: MCC = (2*1 - 0)/sqrt(2*3*1*2) = 2/sqrt(12).
    y_true = [1, 1, 1, 0]
    y_score = [0.9, 0.8, 0.2, 0.1]
    m = compute_binary_classification_metrics(y_true, y_score, threshold=0.5)
    assert m["confusion_matrix"] == {"tp": 2, "fp": 0, "tn": 1, "fn": 1}
    assert m["mcc"] == pytest.approx(2 / math.sqrt(12))


def test_all_same_label_mcc_zero_and_auc_none():
    y_true = [0, 0, 0]
    y_score = [0.1, 0.2, 0.3]
    m = compute_binary_classification_metrics(y_true, y_score)
    assert m["mcc"] == 0.0
    # Single-class target: AUCs undefined regardless of sklearn presence.
    assert m["roc_auc"] is None
    assert m["pr_auc"] is None


def test_no_positive_predictions():
    y_true = [1, 0, 1]
    y_score = [0.1, 0.2, 0.3]  # all below threshold
    m = compute_binary_classification_metrics(y_true, y_score, threshold=0.5)
    assert m["confusion_matrix"]["tp"] == 0
    assert m["precision"] == 0.0
    assert m["recall"] == 0.0
    assert m["f1"] == 0.0


def test_empty_input_raises():
    with pytest.raises(ValueError):
        compute_binary_classification_metrics([], [])


def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        compute_binary_classification_metrics([1, 0], [0.5])


def test_auc_keys_present():
    m = compute_binary_classification_metrics([1, 0, 1, 0], [0.9, 0.1, 0.8, 0.2])
    # Keys always exist; value is float (sklearn) or None (no sklearn).
    assert "roc_auc" in m
    assert "pr_auc" in m
    assert m["roc_auc"] is None or 0.0 <= m["roc_auc"] <= 1.0
