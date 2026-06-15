"""Evaluation harness CLI: consume pipeline outputs and emit metric reports.

Joins, by ``sample_id``, the dataset labels (from feature records), the fused
:class:`~semvulguard.schemas.records.FinalFinding` confidences/labels, the
ranker scores, optional ground-truth vulnerable lines, and an optional LLM cost
log, then computes classification, ranking, localization, and cost metrics and
writes them to an output directory (JSON, CSV, and a markdown summary).

Consumes existing artifacts only -- no models are trained or invoked here.

Example::

    python -m semvulguard.eval.run \
        --features tests/fixtures/eval/features.jsonl \
        --findings tests/fixtures/eval/findings.jsonl \
        --rank-scores tests/fixtures/eval/rank_scores.jsonl \
        --ground-truth-lines tests/fixtures/eval/ground_truth_lines.jsonl \
        --cost-log tests/fixtures/eval/cost_log.jsonl \
        --output-dir artifacts/eval --threshold 0.5
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from semvulguard.eval.classification import compute_binary_classification_metrics
from semvulguard.eval.cost import compute_cost_metrics
from semvulguard.eval.localization import compute_localization_metrics
from semvulguard.eval.ranking import (
    compute_mrr,
    compute_ndcg_at_k,
    compute_recall_at_k,
)
from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import FinalFinding
from semvulguard.utils.jsonl import read_jsonl, read_models
from semvulguard.utils.logging import get_logger

LOGGER = get_logger("semvulguard.eval.run")

DEFAULT_K_VALUES = [1, 5, 10, 20]
DEFAULT_LINE_K_VALUES = [1, 3, 5]


def _load_labels(features_path: Path) -> dict[str, int]:
    """Map sample_id -> ground-truth label from feature records."""
    return {
        r.sample_id: int(r.label)
        for r in read_models(features_path, FeatureRecord)
    }


def _load_findings(findings_path: Path) -> dict[str, FinalFinding]:
    """Map sample_id -> FinalFinding."""
    return {f.sample_id: f for f in read_models(findings_path, FinalFinding)}


def _load_rank_scores(path: Path | None) -> dict[str, float]:
    """Map sample_id -> rank_score, or empty when no path is given."""
    if path is None:
        return {}
    return {row["sample_id"]: float(row["rank_score"]) for row in read_jsonl(path)}


def _load_ground_truth_lines(path: Path | None) -> dict[str, list[int]]:
    """Map sample_id -> vulnerable_lines from a ground-truth line file."""
    if path is None:
        return {}
    return {
        row["sample_id"]: list(row.get("vulnerable_lines", []))
        for row in read_jsonl(path)
    }


def evaluate(
    features_path: Path,
    findings_path: Path,
    rank_scores_path: Path | None = None,
    ground_truth_lines_path: Path | None = None,
    cost_log_path: Path | None = None,
    threshold: float = 0.5,
    k_values: list[int] | None = None,
    line_k_values: list[int] | None = None,
) -> dict:
    """Compute the full metric bundle from existing pipeline artifacts."""
    k_values = k_values or DEFAULT_K_VALUES
    line_k_values = line_k_values or DEFAULT_LINE_K_VALUES

    labels = _load_labels(features_path)
    findings = _load_findings(findings_path)
    rank_scores = _load_rank_scores(rank_scores_path)
    truth_lines = _load_ground_truth_lines(ground_truth_lines_path)

    classification = _classification_block(labels, findings, threshold)
    ranking = _ranking_block(labels, findings, rank_scores, k_values)
    localization = (
        _localization_block(findings, truth_lines, line_k_values)
        if truth_lines
        else None
    )
    cost = (
        compute_cost_metrics(list(read_jsonl(cost_log_path)))
        if cost_log_path is not None
        else None
    )

    return {
        "num_samples": len(labels),
        "threshold": threshold,
        "classification": classification,
        "ranking": ranking,
        "localization": localization,
        "cost": cost,
    }


def _classification_block(
    labels: dict[str, int],
    findings: dict[str, FinalFinding],
    threshold: float,
) -> dict:
    """Classification metrics over samples scored by FinalFinding confidence."""
    sample_ids = sorted(labels)
    y_true = [labels[sid] for sid in sample_ids]
    y_score = [
        findings[sid].final_confidence if sid in findings else 0.0
        for sid in sample_ids
    ]
    return compute_binary_classification_metrics(y_true, y_score, threshold)


def _ranking_block(
    labels: dict[str, int],
    findings: dict[str, FinalFinding],
    rank_scores: dict[str, float],
    k_values: list[int],
) -> dict:
    """Recall@K / nDCG@K / MRR using ranker scores (FinalFinding fallback)."""
    scores = {
        sid: rank_scores.get(
            sid,
            findings[sid].final_confidence if sid in findings else 0.0,
        )
        for sid in labels
    }
    block: dict[str, float] = {"mrr": compute_mrr(labels, scores)}
    for k in k_values:
        block[f"recall_at_{k}"] = compute_recall_at_k(labels, scores, k)
        block[f"ndcg_at_{k}"] = compute_ndcg_at_k(labels, scores, k)
    return block


def _localization_block(
    findings: dict[str, FinalFinding],
    truth_lines: dict[str, list[int]],
    line_k_values: list[int],
) -> dict:
    """Localization metrics: predicted vulnerable_lines vs ground truth."""
    predictions = {
        sid: finding.vulnerable_lines for sid, finding in findings.items()
    }
    return compute_localization_metrics(predictions, truth_lines, line_k_values)


# -- output writers ---------------------------------------------------------


def _write_json(obj: dict, path: Path) -> None:
    path.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _flatten(prefix: str, block: dict | None, out: dict) -> None:
    """Flatten a (possibly nested) metric block into ``section.metric`` keys."""
    if block is None:
        return
    for key, value in block.items():
        if isinstance(value, dict):
            _flatten(f"{prefix}.{key}", value, out)
        else:
            out[f"{prefix}.{key}"] = value


def _write_summary_csv(metrics: dict, path: Path) -> None:
    """Write a flat ``metric,value`` CSV across all sections."""
    flat: dict[str, object] = {"num_samples": metrics["num_samples"]}
    _flatten("classification", metrics["classification"], flat)
    _flatten("ranking", metrics["ranking"], flat)
    _flatten("localization", metrics.get("localization"), flat)
    _flatten("cost", metrics.get("cost"), flat)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["metric", "value"])
        for key in flat:
            writer.writerow([key, flat[key]])


def _fmt(value: object) -> str:
    """Format a metric value for the markdown table."""
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _write_markdown(metrics: dict, path: Path) -> None:
    """Render a human-readable evaluation summary."""
    lines = ["# SemVulGuard Evaluation Summary", ""]
    lines.append(f"- Samples evaluated: **{metrics['num_samples']}**")
    lines.append(f"- Decision threshold: **{metrics['threshold']}**")
    lines.append("")

    def section(title: str, block: dict | None) -> None:
        lines.append(f"## {title}")
        lines.append("")
        if block is None:
            lines.append("_not available_")
            lines.append("")
            return
        lines.append("| metric | value |")
        lines.append("| --- | --- |")
        for key, value in block.items():
            if isinstance(value, dict):
                for sub, sub_value in value.items():
                    lines.append(f"| {key}.{sub} | {_fmt(sub_value)} |")
            else:
                lines.append(f"| {key} | {_fmt(value)} |")
        lines.append("")

    section("Classification", metrics["classification"])
    section("Ranking", metrics["ranking"])
    section("Localization", metrics.get("localization"))
    section("Cost", metrics.get("cost"))

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_reports(metrics: dict, output_dir: Path) -> dict[str, Path]:
    """Write all metric artifacts to ``output_dir``. Returns their paths."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "metrics": output_dir / "metrics.json",
        "classification": output_dir / "classification_metrics.json",
        "ranking": output_dir / "ranking_metrics.json",
        "localization": output_dir / "localization_metrics.json",
        "cost": output_dir / "cost_metrics.json",
        "summary_csv": output_dir / "summary.csv",
        "markdown": output_dir / "evaluation_summary.md",
    }

    _write_json(metrics, paths["metrics"])
    _write_json(metrics["classification"], paths["classification"])
    _write_json(metrics["ranking"], paths["ranking"])
    _write_json(metrics.get("localization") or {}, paths["localization"])
    _write_json(metrics.get("cost") or {}, paths["cost"])
    _write_summary_csv(metrics, paths["summary_csv"])
    _write_markdown(metrics, paths["markdown"])
    return paths


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="semvulguard.eval.run",
        description="Evaluate SemVulGuard outputs and emit metric reports.",
    )
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument("--findings", required=True, type=Path)
    parser.add_argument("--rank-scores", type=Path, default=None)
    parser.add_argument("--ground-truth-lines", type=Path, default=None)
    parser.add_argument("--cost-log", type=Path, default=None)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--threshold", type=float, default=0.5)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    metrics = evaluate(
        features_path=args.features,
        findings_path=args.findings,
        rank_scores_path=args.rank_scores,
        ground_truth_lines_path=args.ground_truth_lines,
        cost_log_path=args.cost_log,
        threshold=args.threshold,
    )
    paths = write_reports(metrics, args.output_dir)
    print(f"evaluated {metrics['num_samples']} samples -> {paths['metrics']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["evaluate", "write_reports", "main"]
