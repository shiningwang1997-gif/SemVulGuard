"""Fusion runner: load all upstream artifacts and emit FinalFinding records.

Joins, per ``sample_id``, the feature records, ranker scores, static alerts, and
LLM verdicts, then fuses them into :class:`FinalFinding` records via
:func:`build_final_finding`. The CLI additionally writes a ``fusion_scores``
JSONL that records the component scores behind each decision.

The feature records define the candidate set: every feature record yields one
finding, with missing rank scores / alerts / verdicts treated as absent signals
(rank score 0.0, no alerts, no verdict). Output order follows the feature file.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from semvulguard.models.fusion.scoring import (
    build_final_finding,
    compute_final_score,
    compute_llm_score,
    compute_static_score,
)
from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import (
    FinalFinding,
    LLMVerdict,
    StaticAlertRecord,
)
from semvulguard.utils.jsonl import read_jsonl, read_models, write_jsonl
from semvulguard.utils.logging import get_logger

LOGGER = get_logger("semvulguard.models.fusion.run")


def _index_rank_scores(path: Path) -> dict[str, float]:
    """Map sample_id -> rank_score from a rank-scores JSONL."""
    return {row["sample_id"]: float(row["rank_score"]) for row in read_jsonl(path)}


def _group_alerts(path: Path) -> dict[str, list[StaticAlertRecord]]:
    """Group static alerts by sample_id."""
    grouped: dict[str, list[StaticAlertRecord]] = defaultdict(list)
    for alert in read_models(path, StaticAlertRecord):
        grouped[alert.sample_id].append(alert)
    return grouped


def _index_verdicts(path: Path) -> dict[str, LLMVerdict]:
    """Map sample_id -> LLMVerdict from an LLM verdicts JSONL."""
    return {v.sample_id: v for v in read_models(path, LLMVerdict)}


def fuse(
    features_path: Path,
    rank_scores_path: Path,
    alerts_path: Path,
    llm_verdicts_path: Path,
    threshold: float = 0.5,
    weights: dict | None = None,
) -> tuple[list[FinalFinding], list[dict]]:
    """Fuse all upstream artifacts into findings + per-sample score rows.

    Returns ``(findings, fusion_score_rows)``; both lists are aligned and follow
    the order of the feature records.
    """
    features = read_models(features_path, FeatureRecord)
    rank_scores = _index_rank_scores(rank_scores_path)
    alerts_by_sample = _group_alerts(alerts_path)
    verdicts = _index_verdicts(llm_verdicts_path)

    findings: list[FinalFinding] = []
    score_rows: list[dict] = []
    for feature in features:
        sid = feature.sample_id
        rank_score = rank_scores.get(sid, 0.0)
        alerts = alerts_by_sample.get(sid, [])
        verdict = verdicts.get(sid)

        finding = build_final_finding(
            feature_record=feature,
            rank_score=rank_score,
            alerts=alerts,
            llm_verdict=verdict,
            threshold=threshold,
            weights=weights,
        )
        findings.append(finding)

        static_score = compute_static_score(alerts)
        llm_score = compute_llm_score(verdict)
        score_rows.append(
            {
                "sample_id": sid,
                "static_score": static_score,
                "rank_score": rank_score,
                "llm_score": llm_score,
                "final_score": compute_final_score(
                    static_score, rank_score, llm_score, weights=weights
                ),
                "final_label": finding.final_label,
            }
        )

    return findings, score_rows


def write_fusion_scores(score_rows: list[dict], output_path: Path) -> int:
    """Write the per-sample fusion-score rows as JSONL."""
    return write_jsonl(output_path, score_rows)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="semvulguard.models.fusion.run",
        description="Fuse static/ranker/LLM signals into FinalFinding records.",
    )
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument("--rank-scores", required=True, type=Path)
    parser.add_argument("--alerts", required=True, type=Path)
    parser.add_argument("--llm-verdicts", required=True, type=Path)
    parser.add_argument("--findings-output", required=True, type=Path)
    parser.add_argument("--scores-output", required=True, type=Path)
    parser.add_argument("--threshold", type=float, default=0.5)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    findings, score_rows = fuse(
        features_path=args.features,
        rank_scores_path=args.rank_scores,
        alerts_path=args.alerts,
        llm_verdicts_path=args.llm_verdicts,
        threshold=args.threshold,
    )
    n = write_jsonl(args.findings_output, findings)
    write_fusion_scores(score_rows, args.scores_output)
    print(f"fused {n} findings -> {args.findings_output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["fuse", "write_fusion_scores", "main"]
