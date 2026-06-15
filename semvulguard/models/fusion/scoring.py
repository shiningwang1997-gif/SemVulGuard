"""Late-fusion scoring over static, ranker, and LLM signals.

Each candidate carries three independent risk signals: a static-analysis score
derived from its alerts, the learned ranker score, and the LLM verifier's
verdict. ``compute_final_score`` combines them with fixed default weights into a
calibrated ``[0, 1]`` risk, and ``build_final_finding`` assembles the fused,
localized :class:`FinalFinding` with an evidence trail.

Pure and deterministic: no I/O, no randomness.
"""

from __future__ import annotations

from collections import Counter

from semvulguard.localization.line_score import compute_line_scores, top_k_lines
from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import (
    FinalFinding,
    LLMVerdict,
    StaticAlertRecord,
)

# Severity -> weight. Keys are matched case-insensitively against the alert's
# severity string; unrecognized severities fall back to ``unknown``.
SEVERITY_WEIGHTS: dict[str, float] = {
    "high": 1.0,
    "error": 1.0,
    "critical": 1.0,
    "medium": 0.7,
    "warning": 0.7,
    "moderate": 0.7,
    "low": 0.4,
    "note": 0.4,
    "recommendation": 0.4,
}
UNKNOWN_SEVERITY_WEIGHT = 0.3

# Per-alert base contribution before severity weighting, and the bonus added
# once when any alert carries a taint trace.
ALERT_BASE = 0.4
TRACE_BONUS = 0.15

# Default fusion weights across the three signals (sum to 1.0).
DEFAULT_FUSION_WEIGHTS: dict[str, float] = {
    "static": 0.25,
    "ranker": 0.45,
    "llm": 0.30,
}

# LLM verdict shaping.
BENIGN_SCORE_CAP = 0.3
UNCERTAIN_SCORE = 0.3

UNKNOWN_CWE = "unknown"


def _clamp(value: float) -> float:
    """Clamp a score into the unit interval."""
    return max(0.0, min(1.0, value))


def _severity_weight(severity: str | None) -> float:
    """Map an alert severity onto its fusion weight."""
    if severity is None:
        return UNKNOWN_SEVERITY_WEIGHT
    return SEVERITY_WEIGHTS.get(severity.strip().lower(), UNKNOWN_SEVERITY_WEIGHT)


def compute_static_score(alerts: list[StaticAlertRecord]) -> float:
    """Aggregate a sample's static alerts into a ``[0, 1]`` risk score.

    The score grows with the number and severity of alerts and gains a one-time
    bonus when any alert provides taint-trace evidence. Empty input scores 0.
    """
    if not alerts:
        return 0.0

    score = 0.0
    for alert in alerts:
        score += ALERT_BASE * _severity_weight(alert.severity)

    if any(alert.trace_lines for alert in alerts):
        score += TRACE_BONUS

    return _clamp(score)


def compute_llm_score(verdict: LLMVerdict | None) -> float:
    """Translate an LLM verdict into a ``[0, 1]`` risk contribution.

    A ``vulnerable`` verdict contributes its confidence directly; ``benign``
    contributes a small, capped residual; ``uncertain`` sits at a fixed middling
    value; a missing verdict contributes nothing.
    """
    if verdict is None:
        return 0.0
    if verdict.verdict == "vulnerable":
        return _clamp(verdict.confidence)
    if verdict.verdict == "benign":
        return _clamp(min(BENIGN_SCORE_CAP, 1.0 - verdict.confidence))
    # uncertain: half the confidence, but never above the uncertain ceiling and
    # never collapsing to zero when the model gave no confidence.
    scaled = 0.5 * verdict.confidence
    return _clamp(min(UNCERTAIN_SCORE, scaled) if scaled > 0 else UNCERTAIN_SCORE)


def compute_final_score(
    static_score: float,
    rank_score: float,
    llm_score: float,
    weights: dict | None = None,
) -> float:
    """Weighted combination of the three signals, clamped to ``[0, 1]``."""
    w = weights or DEFAULT_FUSION_WEIGHTS
    score = (
        w["static"] * static_score
        + w["ranker"] * rank_score
        + w["llm"] * llm_score
    )
    return _clamp(score)


def final_label_from_score(score: float, threshold: float = 0.5) -> int:
    """Binarize a fused score at ``threshold`` (>= threshold => 1)."""
    return int(score >= threshold)


def _is_unknown_cwe(cwe: str | None) -> bool:
    return not cwe or cwe.strip().lower() in {"unknown", "cwe-unknown", ""}


def select_predicted_cwe(
    alerts: list[StaticAlertRecord],
    llm_verdict: LLMVerdict | None,
    feature_record: FeatureRecord,
) -> str:
    """Pick the most authoritative CWE id available.

    Priority: the LLM's predicted CWE, then the most common CWE across static
    alerts, then the sample's own first CWE, then ``"unknown"``.
    """
    if llm_verdict is not None and not _is_unknown_cwe(llm_verdict.predicted_cwe):
        return llm_verdict.predicted_cwe

    counter: Counter[str] = Counter()
    for alert in alerts:
        for cwe in alert.cwe:
            if not _is_unknown_cwe(cwe):
                counter[cwe] += 1
    if counter:
        # Highest count wins; ties broken by the lexicographically smaller CWE
        # id so the choice is deterministic regardless of alert order.
        best = min(counter.items(), key=lambda kv: (-kv[1], kv[0]))
        return best[0]

    if feature_record.cwe:
        return feature_record.cwe[0]

    return UNKNOWN_CWE


def build_final_finding(
    feature_record: FeatureRecord,
    rank_score: float,
    alerts: list[StaticAlertRecord],
    llm_verdict: LLMVerdict | None,
    threshold: float = 0.5,
    weights: dict | None = None,
) -> FinalFinding:
    """Fuse all signals for one sample into a localized :class:`FinalFinding`.

    The evidence list records the contributing static alerts, taint traces, the
    LLM's own evidence, the ranker score, and the individual fusion components
    so a downstream report can explain the decision.
    """
    static_score = compute_static_score(alerts)
    llm_score = compute_llm_score(llm_verdict)
    final_score = compute_final_score(
        static_score, rank_score, llm_score, weights=weights
    )
    final_label = final_label_from_score(final_score, threshold=threshold)

    line_scores = compute_line_scores(feature_record, alerts, llm_verdict)
    vulnerable_lines = top_k_lines(line_scores, k=5)

    predicted_cwe = select_predicted_cwe(alerts, llm_verdict, feature_record)
    patch_hint = llm_verdict.patch_hint if llm_verdict else ""

    evidence = _build_evidence(
        feature_record=feature_record,
        alerts=alerts,
        llm_verdict=llm_verdict,
        rank_score=rank_score,
        static_score=static_score,
        llm_score=llm_score,
        final_score=final_score,
        line_scores=line_scores,
        weights=weights or DEFAULT_FUSION_WEIGHTS,
    )

    return FinalFinding(
        sample_id=feature_record.sample_id,
        final_label=final_label,
        final_confidence=final_score,
        predicted_cwe=predicted_cwe,
        vulnerable_lines=vulnerable_lines,
        evidence=evidence,
        patch_hint=patch_hint,
    )


def _build_evidence(
    *,
    feature_record: FeatureRecord,
    alerts: list[StaticAlertRecord],
    llm_verdict: LLMVerdict | None,
    rank_score: float,
    static_score: float,
    llm_score: float,
    final_score: float,
    line_scores: dict[int, float],
    weights: dict,
) -> list[dict]:
    """Assemble the explainable evidence trail for a finding."""
    evidence: list[dict] = []

    for alert in alerts:
        evidence.append(
            {
                "kind": "static_alert",
                "tool": alert.tool,
                "query_id": alert.query_id,
                "severity": alert.severity,
                "message": alert.message,
                "file": alert.file,
                "start_line": alert.start_line,
                "end_line": alert.end_line,
                "cwe": alert.cwe,
            }
        )

    trace_lines = sorted(
        {line for alert in alerts for line in alert.trace_lines}
    )
    if trace_lines:
        evidence.append({"kind": "trace_lines", "lines": trace_lines})

    if llm_verdict is not None:
        evidence.append(
            {
                "kind": "llm_verdict",
                "verdict": llm_verdict.verdict,
                "confidence": llm_verdict.confidence,
                "predicted_cwe": llm_verdict.predicted_cwe,
                "vulnerable_lines": llm_verdict.vulnerable_lines,
                "llm_evidence": llm_verdict.evidence,
            }
        )

    evidence.append({"kind": "rank_score", "value": rank_score})
    evidence.append(
        {
            "kind": "fusion_scores",
            "static_score": static_score,
            "rank_score": rank_score,
            "llm_score": llm_score,
            "final_score": final_score,
            "weights": dict(weights),
        }
    )
    evidence.append(
        {
            "kind": "line_scores",
            "scores": {str(k): v for k, v in sorted(line_scores.items())},
        }
    )
    return evidence


__all__ = [
    "compute_static_score",
    "compute_llm_score",
    "compute_final_score",
    "final_label_from_score",
    "select_predicted_cwe",
    "build_final_finding",
    "DEFAULT_FUSION_WEIGHTS",
    "SEVERITY_WEIGHTS",
]
