"""Tests for ranking metrics: Recall@K, MRR, nDCG@K, grouped."""

from __future__ import annotations

import math

import pytest

from semvulguard.eval.ranking import (
    compute_grouped_ranking_metrics,
    compute_mrr,
    compute_ndcg_at_k,
    compute_recall_at_k,
)

LABELS = {"a": 1, "b": 0, "c": 1, "d": 0}
SCORES = {"a": 0.9, "b": 0.3, "c": 0.6, "d": 0.1}
# Ranked order by score: a (1), c (1), b (0), d (0).


def test_recall_at_k():
    assert compute_recall_at_k(LABELS, SCORES, 1) == pytest.approx(0.5)
    assert compute_recall_at_k(LABELS, SCORES, 2) == pytest.approx(1.0)
    assert compute_recall_at_k(LABELS, SCORES, 4) == pytest.approx(1.0)


def test_recall_at_k_no_positives_is_zero():
    assert compute_recall_at_k({"a": 0, "b": 0}, {"a": 0.9, "b": 0.1}, 2) == 0.0


def test_recall_at_k_non_positive_k():
    assert compute_recall_at_k(LABELS, SCORES, 0) == 0.0


def test_mrr_first_positive_at_rank_one():
    assert compute_mrr(LABELS, SCORES) == pytest.approx(1.0)


def test_mrr_first_positive_at_rank_two():
    labels = {"a": 0, "b": 1}
    scores = {"a": 0.9, "b": 0.5}
    assert compute_mrr(labels, scores) == pytest.approx(0.5)


def test_mrr_no_positive_is_zero():
    assert compute_mrr({"a": 0}, {"a": 0.9}) == 0.0


def test_ndcg_in_unit_interval():
    val = compute_ndcg_at_k(LABELS, SCORES, 4)
    assert 0.0 <= val <= 1.0


def test_ndcg_perfect_ranking_is_one():
    # Positives ranked strictly first -> nDCG = 1.
    labels = {"a": 1, "b": 1, "c": 0, "d": 0}
    scores = {"a": 0.9, "b": 0.8, "c": 0.2, "d": 0.1}
    assert compute_ndcg_at_k(labels, scores, 4) == pytest.approx(1.0)


def test_ndcg_known_value():
    # Ranked: a(1), c(1), b(0), d(0). DCG@2 = 1/log2(2) + 1/log2(3).
    # Ideal@2 = same since two positives. -> 1.0
    assert compute_ndcg_at_k(LABELS, SCORES, 2) == pytest.approx(1.0)
    # DCG@1 = 1; ideal@1 = 1 -> 1.0
    assert compute_ndcg_at_k(LABELS, SCORES, 1) == pytest.approx(1.0)


def test_ndcg_suboptimal_below_one():
    # Positive at rank 2 only: DCG = 1/log2(3); ideal = 1/log2(2)=1.
    labels = {"a": 0, "b": 1}
    scores = {"a": 0.9, "b": 0.5}
    expected = (1 / math.log2(3)) / 1.0
    assert compute_ndcg_at_k(labels, scores, 2) == pytest.approx(expected)


def test_tie_break_is_deterministic():
    # Equal scores -> ascending sample_id; positive "a" outranks negative "b".
    labels = {"a": 1, "b": 0}
    scores = {"a": 0.5, "b": 0.5}
    assert compute_mrr(labels, scores) == pytest.approx(1.0)


def test_grouped_ranking_metrics():
    records = [
        {"sample_id": "a", "label": 1, "score": 0.9, "repo": "alpha"},
        {"sample_id": "b", "label": 0, "score": 0.2, "repo": "alpha"},
        {"sample_id": "c", "label": 1, "score": 0.7, "repo": "beta"},
        {"sample_id": "d", "label": 0, "score": 0.4, "repo": "beta"},
    ]
    result = compute_grouped_ranking_metrics(records, group_key="repo", k_values=[1, 2])
    assert result["num_groups"] == 2
    assert set(result["per_group"]) == {"alpha", "beta"}
    # Each group has its positive at rank 1.
    assert result["macro_avg"]["mrr"] == pytest.approx(1.0)
    assert result["macro_avg"]["recall_at_1"] == pytest.approx(1.0)
    assert "overall" in result
