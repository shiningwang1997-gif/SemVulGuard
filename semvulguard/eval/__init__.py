"""Evaluation harness: classification, ranking, localization, cost, ablation.

Consumes existing pipeline artifacts (feature labels, rank scores, LLM verdicts,
final findings, optional cost logs) and computes deterministic metrics. No
models are trained or invoked here.
"""

from semvulguard.eval.ablation import compare_ablation_results
from semvulguard.eval.classification import (
    compute_binary_classification_metrics,
)
from semvulguard.eval.cost import compute_cost_metrics
from semvulguard.eval.localization import (
    compute_iou,
    compute_localization_metrics,
    compute_topk_line_hit,
)
from semvulguard.eval.ranking import (
    compute_grouped_ranking_metrics,
    compute_mrr,
    compute_ndcg_at_k,
    compute_recall_at_k,
)

__all__ = [
    "compute_binary_classification_metrics",
    "compute_recall_at_k",
    "compute_mrr",
    "compute_ndcg_at_k",
    "compute_grouped_ranking_metrics",
    "compute_topk_line_hit",
    "compute_iou",
    "compute_localization_metrics",
    "compute_cost_metrics",
    "compare_ablation_results",
]
