"""Cost and latency aggregation over LLM call logs.

Summarizes per-sample token usage, dollar cost, and latency into totals,
per-sample averages, and a p95 latency. Every field is optional: missing values
are skipped rather than assumed zero, so partial logs still produce sensible
aggregates. Deterministic given the same input.
"""

from __future__ import annotations


def _sum_field(records: list[dict], field: str) -> float:
    """Sum a numeric field over records that carry it (missing -> skipped)."""
    return sum(float(r[field]) for r in records if r.get(field) is not None)


def _values(records: list[dict], field: str) -> list[float]:
    """Collect present numeric values for a field, in record order."""
    return [float(r[field]) for r in records if r.get(field) is not None]


def _percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile over ``values`` (``pct`` in [0, 100])."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return ordered[low] + (ordered[high] - ordered[low]) * frac


def _total_tokens(records: list[dict]) -> float:
    """Total tokens, preferring ``total_tokens`` and falling back to parts."""
    total = 0.0
    for r in records:
        if r.get("total_tokens") is not None:
            total += float(r["total_tokens"])
        else:
            total += float(r.get("prompt_tokens") or 0)
            total += float(r.get("completion_tokens") or 0)
    return total


def compute_cost_metrics(cost_records: list[dict]) -> dict:
    """Aggregate token / cost / latency stats over a list of cost records.

    Returns zeros for an empty log. Per-sample averages divide by the number of
    records; latency averages and p95 use only records that report latency.
    """
    count = len(cost_records)
    if count == 0:
        return {
            "total_tokens": 0.0,
            "avg_tokens_per_sample": 0.0,
            "total_cost_usd": 0.0,
            "avg_cost_per_sample": 0.0,
            "avg_latency_seconds": 0.0,
            "p95_latency_seconds": 0.0,
            "samples_count": 0,
        }

    total_tokens = _total_tokens(cost_records)
    total_cost = _sum_field(cost_records, "api_cost_usd")
    latencies = _values(cost_records, "latency_seconds")

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    return {
        "total_tokens": total_tokens,
        "avg_tokens_per_sample": total_tokens / count,
        "total_cost_usd": total_cost,
        "avg_cost_per_sample": total_cost / count,
        "avg_latency_seconds": avg_latency,
        "p95_latency_seconds": _percentile(latencies, 95.0),
        "samples_count": count,
    }


__all__ = ["compute_cost_metrics"]
