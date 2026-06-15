"""Ablation comparison across configurations.

Turns a mapping of ``config_name -> metrics`` into a ranked, table-like list on
a chosen metric (default ``f1``), annotating each row with its delta against a
reference configuration (``full`` if present, else the top-ranked row, else an
explicit baseline). Deterministic: ties are broken by configuration name.
"""

from __future__ import annotations

DEFAULT_METRIC = "f1"
FULL_CONFIG = "full"


def compare_ablation_results(
    results: dict[str, dict],
    metric: str = DEFAULT_METRIC,
    baseline: str | None = None,
) -> list[dict]:
    """Rank ablation configurations by ``metric`` and annotate deltas.

    Rows are sorted by the selected metric descending (ties by config name). The
    delta is taken against ``baseline`` when given, otherwise against the
    ``full`` configuration when present, otherwise the best-scoring row. Missing
    metric values are treated as 0.0 for ordering and reported as ``None``.

    Each row carries: ``config``, ``metric``, the metric value, ``delta``, and
    ``rank`` (1-indexed), plus all original metric values for that config.
    """
    def _value(config: str) -> float:
        raw = results[config].get(metric)
        return float(raw) if raw is not None else 0.0

    ordered = sorted(results, key=lambda c: (-_value(c), c))

    reference = baseline
    if reference is None:
        reference = FULL_CONFIG if FULL_CONFIG in results else (
            ordered[0] if ordered else None
        )
    reference_value = _value(reference) if reference in results else None

    rows: list[dict] = []
    for rank, config in enumerate(ordered, start=1):
        raw = results[config].get(metric)
        value = float(raw) if raw is not None else None
        delta = (
            (value - reference_value)
            if value is not None and reference_value is not None
            else None
        )
        row = {
            "config": config,
            "metric": metric,
            "value": value,
            "delta": delta,
            "rank": rank,
            "is_reference": config == reference,
        }
        # Carry through the other recorded metrics for convenience.
        row["metrics"] = dict(results[config])
        rows.append(row)

    return rows


__all__ = ["compare_ablation_results", "DEFAULT_METRIC"]
