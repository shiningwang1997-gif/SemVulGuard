"""Line-level localization metrics.

Compares predicted suspect lines (e.g. a finding's ``vulnerable_lines``) against
ground-truth vulnerable lines via Top-K hit rate and Intersection-over-Union.
``compute_localization_metrics`` aggregates these over a set of samples that
have ground truth available. All metrics are deterministic.
"""

from __future__ import annotations


def compute_topk_line_hit(
    predicted_lines: list[int],
    ground_truth_lines: list[int],
    k: int,
) -> int:
    """Return 1 if any of the top-``k`` predicted lines is a true line, else 0.

    Prediction order is significant: only the first ``k`` predictions count. A
    non-positive ``k`` or empty ground truth yields 0.
    """
    if k <= 0 or not ground_truth_lines:
        return 0
    truth = set(ground_truth_lines)
    return int(any(line in truth for line in predicted_lines[:k]))


def compute_iou(
    predicted_lines: list[int],
    ground_truth_lines: list[int],
) -> float:
    """Intersection-over-Union of predicted and true line sets.

    Returns 0.0 when both sets are empty (nothing to localize).
    """
    pred = set(predicted_lines)
    truth = set(ground_truth_lines)
    union = pred | truth
    if not union:
        return 0.0
    return len(pred & truth) / len(union)


def compute_localization_metrics(
    predictions: dict[str, list[int]],
    ground_truth: dict[str, list[int]],
    k_values: list[int] | None = None,
) -> dict:
    """Aggregate localization quality over all samples that have ground truth.

    Each ground-truth sample contributes a Top-K hit (per K) and an IoU; a
    sample with no prediction contributes zeros. ``coverage`` is the fraction of
    ground-truth samples for which a (non-empty) prediction was supplied.

    Returns ``top{K}_hit_rate`` keys for each K, ``mean_iou``, ``coverage``, and
    ``num_samples``. With no ground truth, all rates are 0.0.
    """
    if k_values is None:
        k_values = [1, 3, 5]

    sample_ids = sorted(ground_truth)
    num = len(sample_ids)

    metrics: dict[str, float] = {}
    for k in k_values:
        if num == 0:
            metrics[f"top{k}_hit_rate"] = 0.0
            continue
        hits = sum(
            compute_topk_line_hit(predictions.get(sid, []), ground_truth[sid], k)
            for sid in sample_ids
        )
        metrics[f"top{k}_hit_rate"] = hits / num

    if num == 0:
        metrics["mean_iou"] = 0.0
        metrics["coverage"] = 0.0
    else:
        iou_sum = sum(
            compute_iou(predictions.get(sid, []), ground_truth[sid])
            for sid in sample_ids
        )
        metrics["mean_iou"] = iou_sum / num
        covered = sum(1 for sid in sample_ids if predictions.get(sid))
        metrics["coverage"] = covered / num

    metrics["num_samples"] = num
    return metrics


__all__ = [
    "compute_topk_line_hit",
    "compute_iou",
    "compute_localization_metrics",
]
