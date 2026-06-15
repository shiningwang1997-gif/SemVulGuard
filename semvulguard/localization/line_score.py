"""Line-level vulnerability localization.

Combines static alert lines, taint trace lines, the LLM's flagged lines, and
graph-node static flags into a per-line score over absolute (1-indexed) source
line numbers, then exposes a stable Top-K selection.

Pure and deterministic: no I/O, no randomness.
"""

from __future__ import annotations

from collections import defaultdict

from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import LLMVerdict, StaticAlertRecord

# Per-component contribution to a line's score. A line may accumulate several
# components; the total is capped at 1.0.
DEFAULT_LINE_WEIGHTS: dict[str, float] = {
    "static_alert_line": 0.35,
    "trace_line": 0.20,
    "llm_vote": 0.35,
    "graph_flag": 0.10,
}


def _alert_lines(alerts: list[StaticAlertRecord]) -> set[int]:
    """Absolute lines covered by an alert's primary [start, end] region."""
    lines: set[int] = set()
    for alert in alerts:
        lines.update(range(alert.start_line, alert.end_line + 1))
    return lines


def _trace_lines(alerts: list[StaticAlertRecord]) -> set[int]:
    """Absolute lines appearing in any alert's taint trace."""
    lines: set[int] = set()
    for alert in alerts:
        lines.update(alert.trace_lines)
    return lines


def _graph_flag_lines(feature_record: FeatureRecord) -> set[int]:
    """Absolute lines of graph nodes carrying any non-zero static flag."""
    lines: set[int] = set()
    for node in feature_record.nodes:
        if node.line is None:
            continue
        if any(float(v) > 0 for v in node.static_flags.values()):
            lines.add(node.line)
    return lines


def compute_line_scores(
    feature_record: FeatureRecord,
    alerts: list[StaticAlertRecord],
    llm_verdict: LLMVerdict | None,
    weights: dict[str, float] | None = None,
) -> dict[int, float]:
    """Score each implicated source line in ``[0, 1]`` by combining evidence.

    Lines are absolute (1-indexed). Alert/trace lines fall back to the feature
    record's pre-computed lines so the localization works even when the raw
    alerts are not threaded through. Scores are capped at 1.0.
    """
    w = weights or DEFAULT_LINE_WEIGHTS

    alert_lines = _alert_lines(alerts) | set(feature_record.alert_lines)
    trace_lines = _trace_lines(alerts) | set(feature_record.trace_lines)
    llm_lines = set(llm_verdict.vulnerable_lines) if llm_verdict else set()
    graph_lines = _graph_flag_lines(feature_record)

    scores: dict[int, float] = defaultdict(float)
    for line in alert_lines:
        scores[line] += w["static_alert_line"]
    for line in trace_lines:
        scores[line] += w["trace_line"]
    for line in llm_lines:
        scores[line] += w["llm_vote"]
    for line in graph_lines:
        scores[line] += w["graph_flag"]

    return {line: min(1.0, score) for line, score in scores.items()}


def top_k_lines(line_scores: dict[int, float], k: int = 5) -> list[int]:
    """Return the Top-K lines by descending score, ties broken by line number.

    A non-positive ``k`` yields an empty list.
    """
    if k <= 0:
        return []
    ordered = sorted(line_scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [line for line, _ in ordered[:k]]


__all__ = ["compute_line_scores", "top_k_lines", "DEFAULT_LINE_WEIGHTS"]
