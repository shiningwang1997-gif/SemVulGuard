"""Verification-packet assembly for the LLM verifier.

Bridges the feature-builder / static-analysis artifacts to the compressed
:class:`~semvulguard.schemas.records.VerificationPacket` consumed by the LLM,
and provides Top-K candidate selection over ranker scores.

The packet carries the function code, span, and static alerts directly; the
structured static-evidence summary (built by :class:`EvidenceCollector`) is
placed under ``context["evidence_summary"]`` so the public ``VerificationPacket``
schema does not need to change.

Pure and deterministic: the only I/O is reading the rank-scores JSONL.
"""

from __future__ import annotations

from pathlib import Path

from semvulguard.llm.evidence import EvidenceCollector
from semvulguard.llm.prompt_builder import EVIDENCE_SUMMARY_KEY
from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import StaticAlertRecord, VerificationPacket
from semvulguard.utils.jsonl import read_jsonl

_COLLECTOR = EvidenceCollector()


def build_verification_packet(
    feature_record: FeatureRecord,
    alerts: list[StaticAlertRecord],
    rank_score: float | None = None,
    joern_evidence: dict | None = None,
    context: dict | None = None,
) -> VerificationPacket:
    """Assemble a verification packet for a single candidate.

    The function code and span come from the feature record; ``alerts`` are the
    static-analysis findings for the same sample. ``rank_score`` and
    ``joern_evidence`` feed the structured evidence summary, which is stored
    under ``context["evidence_summary"]``. Any caller-supplied ``context`` keys
    are preserved alongside it.
    """
    evidence_summary = _COLLECTOR.collect(
        feature_record=feature_record,
        alerts=alerts,
        rank_score=rank_score,
        joern_evidence=joern_evidence,
    )

    merged_context = dict(context or {})
    merged_context[EVIDENCE_SUMMARY_KEY] = evidence_summary

    return VerificationPacket(
        sample_id=feature_record.sample_id,
        language=str(feature_record.static_features.get("language", "c")),
        function_code=feature_record.function_code,
        span=feature_record.span,
        static_alerts=list(alerts),
        joern_evidence=joern_evidence or {},
        context=merged_context,
    )


def select_topk_candidates(rank_scores_path: Path, k: int) -> list[str]:
    """Return the Top-K ``sample_id``s by descending rank score.

    Ties are broken stably by ascending ``sample_id`` so the selection is
    deterministic regardless of input order. Raises ``ValueError`` for
    non-positive ``k``.
    """
    if k <= 0:
        raise ValueError(f"k must be a positive integer, got {k}")

    rows = list(read_jsonl(rank_scores_path))
    ordered = sorted(rows, key=lambda r: (-float(r["rank_score"]), r["sample_id"]))
    return [r["sample_id"] for r in ordered[:k]]


__all__ = ["build_verification_packet", "select_topk_candidates"]
