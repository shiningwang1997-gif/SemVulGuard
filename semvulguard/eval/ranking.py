"""Ranking-quality metrics over per-sample risk scores.

Treats vulnerability discovery as a retrieval problem: samples are ranked by
score and judged by how early the truly vulnerable ones surface (Recall@K, MRR,
nDCG@K). A grouped variant averages the metrics across repositories/groups so a
few large projects do not dominate. All ranking is deterministic: ties are
broken by ascending ``sample_id``.
"""

from __future__ import annotations

import math


def _rank_sample_ids(
    labels_by_sample: dict[str, int],
    scores_by_sample: dict[str, float],
) -> list[str]:
    """Order sample ids by descending score, ties broken by sample id."""
    return sorted(
        labels_by_sample,
        key=lambda sid: (-scores_by_sample.get(sid, 0.0), sid),
    )


def compute_recall_at_k(
    labels_by_sample: dict[str, int],
    scores_by_sample: dict[str, float],
    k: int,
) -> float:
    """Fraction of all positives that appear in the top-``k`` ranked samples.

    Returns 0.0 when there are no positives or ``k <= 0``.
    """
    total_positives = sum(1 for v in labels_by_sample.values() if v == 1)
    if total_positives == 0 or k <= 0:
        return 0.0
    ranked = _rank_sample_ids(labels_by_sample, scores_by_sample)
    hits = sum(1 for sid in ranked[:k] if labels_by_sample[sid] == 1)
    return hits / total_positives


def compute_mrr(
    labels_by_sample: dict[str, int],
    scores_by_sample: dict[str, float],
) -> float:
    """Mean reciprocal rank of the first positive (single-list convention).

    Returns the reciprocal rank of the highest-ranked positive, or 0.0 when no
    positive exists.
    """
    ranked = _rank_sample_ids(labels_by_sample, scores_by_sample)
    for index, sid in enumerate(ranked, start=1):
        if labels_by_sample[sid] == 1:
            return 1.0 / index
    return 0.0


def compute_ndcg_at_k(
    labels_by_sample: dict[str, int],
    scores_by_sample: dict[str, float],
    k: int,
) -> float:
    """Normalized DCG at ``k`` with binary relevance, in ``[0, 1]``.

    Returns 0.0 when there are no positives or ``k <= 0``.
    """
    if k <= 0:
        return 0.0
    ranked = _rank_sample_ids(labels_by_sample, scores_by_sample)
    dcg = _dcg([labels_by_sample[sid] for sid in ranked[:k]])
    total_positives = sum(1 for v in labels_by_sample.values() if v == 1)
    if total_positives == 0:
        return 0.0
    # Ideal ranking puts all positives first.
    ideal = _dcg([1] * min(total_positives, k))
    if ideal == 0:
        return 0.0
    return dcg / ideal


def _dcg(relevances: list[int]) -> float:
    """Discounted cumulative gain with the ``log2(rank + 1)`` discount."""
    return sum(
        rel / math.log2(index + 1)
        for index, rel in enumerate(relevances, start=1)
        if rel
    )


def compute_grouped_ranking_metrics(
    records: list[dict],
    group_key: str = "repo",
    k_values: list[int] | None = None,
) -> dict:
    """Macro-average ranking metrics across groups (e.g. per repository).

    Each record needs ``sample_id``, ``label``, ``score``, and the ``group_key``
    field (missing group ids fall back to ``"__ungrouped__"``). Returns the
    per-group metrics plus their macro-average and a global (ungrouped) view.
    """
    if k_values is None:
        k_values = [1, 5, 10, 20]

    groups: dict[str, dict] = {}
    for record in records:
        group = str(record.get(group_key, "__ungrouped__"))
        bucket = groups.setdefault(group, {"labels": {}, "scores": {}})
        sid = record["sample_id"]
        bucket["labels"][sid] = int(record["label"])
        bucket["scores"][sid] = float(record["score"])

    per_group: dict[str, dict] = {}
    for group in sorted(groups):
        labels = groups[group]["labels"]
        scores = groups[group]["scores"]
        per_group[group] = _ranking_metric_block(labels, scores, k_values)

    macro = _macro_average(per_group, k_values)

    # Global view: treat all samples as a single ranked list.
    all_labels = {
        r["sample_id"]: int(r["label"]) for r in records
    }
    all_scores = {
        r["sample_id"]: float(r["score"]) for r in records
    }
    overall = _ranking_metric_block(all_labels, all_scores, k_values)

    return {
        "num_groups": len(per_group),
        "per_group": per_group,
        "macro_avg": macro,
        "overall": overall,
    }


def _ranking_metric_block(
    labels: dict[str, int],
    scores: dict[str, float],
    k_values: list[int],
) -> dict:
    """Recall@K / nDCG@K for each K, plus MRR, for one ranked list."""
    block: dict[str, float] = {"mrr": compute_mrr(labels, scores)}
    for k in k_values:
        block[f"recall_at_{k}"] = compute_recall_at_k(labels, scores, k)
        block[f"ndcg_at_{k}"] = compute_ndcg_at_k(labels, scores, k)
    return block


def _macro_average(per_group: dict[str, dict], k_values: list[int]) -> dict:
    """Average each metric uniformly across groups."""
    if not per_group:
        return {}
    keys = ["mrr"]
    for k in k_values:
        keys += [f"recall_at_{k}", f"ndcg_at_{k}"]
    macro: dict[str, float] = {}
    for key in keys:
        values = [block[key] for block in per_group.values()]
        macro[key] = sum(values) / len(values)
    return macro


__all__ = [
    "compute_recall_at_k",
    "compute_mrr",
    "compute_ndcg_at_k",
    "compute_grouped_ranking_metrics",
]
