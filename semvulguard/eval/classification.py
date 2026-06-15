"""Function-level binary classification metrics.

Computes the standard suite (accuracy, precision, recall, F1, MCC) by hand so
the harness has no hard dependency, and adds ROC-AUC / PR-AUC via scikit-learn
when it is installed (``None`` otherwise). All metrics are deterministic.
"""

from __future__ import annotations

import math

try:  # optional: only used for ROC-AUC / PR-AUC
    from sklearn.metrics import average_precision_score, roc_auc_score

    _HAVE_SKLEARN = True
except ImportError:  # pragma: no cover - exercised only when sklearn is absent
    _HAVE_SKLEARN = False


def _confusion(y_true: list[int], y_pred: list[int]) -> tuple[int, int, int, int]:
    """Return ``(tp, fp, tn, fn)`` for binary predictions."""
    tp = fp = tn = fn = 0
    for true, pred in zip(y_true, y_pred, strict=True):
        if pred == 1 and true == 1:
            tp += 1
        elif pred == 1 and true == 0:
            fp += 1
        elif pred == 0 and true == 0:
            tn += 1
        else:
            fn += 1
    return tp, fp, tn, fn


def _mcc(tp: int, fp: int, tn: int, fn: int) -> float:
    """Matthews correlation coefficient; 0.0 when the denominator vanishes."""
    numerator = (tp * tn) - (fp * fn)
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    if denominator == 0:
        return 0.0
    return numerator / denominator


def compute_binary_classification_metrics(
    y_true: list[int],
    y_score: list[float],
    threshold: float = 0.5,
) -> dict:
    """Compute the binary classification metric suite.

    ``y_score`` holds continuous scores thresholded at ``threshold`` (``>=`` ->
    positive). ROC-AUC / PR-AUC are populated only when scikit-learn is present
    and both classes appear in ``y_true``; otherwise they are ``None``.

    Raises ``ValueError`` on empty input or a length mismatch.
    """
    if not y_true or not y_score:
        raise ValueError("y_true and y_score must be non-empty")
    if len(y_true) != len(y_score):
        raise ValueError(
            f"length mismatch: {len(y_true)} labels vs {len(y_score)} scores"
        )

    y_pred = [1 if score >= threshold else 0 for score in y_score]
    tp, fp, tn, fn = _confusion(y_true, y_pred)
    total = tp + fp + tn + fn

    accuracy = (tp + tn) / total
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )
    mcc = _mcc(tp, fp, tn, fn)

    roc_auc, pr_auc = _ranking_aucs(y_true, y_score)

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "mcc": mcc,
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "support": total,
    }


def _ranking_aucs(
    y_true: list[int], y_score: list[float]
) -> tuple[float | None, float | None]:
    """Return ``(roc_auc, pr_auc)`` when computable, else ``(None, None)``.

    Both require scikit-learn and at least one positive and one negative label;
    a single-class target leaves them undefined.
    """
    if not _HAVE_SKLEARN:
        return None, None
    positives = sum(y_true)
    if positives == 0 or positives == len(y_true):
        return None, None
    roc_auc = float(roc_auc_score(y_true, y_score))
    pr_auc = float(average_precision_score(y_true, y_score))
    return roc_auc, pr_auc


__all__ = ["compute_binary_classification_metrics"]
