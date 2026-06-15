"""SemVulGuard experiment runner (orchestration only -- no architecture change).

Drives the existing library functions (`fuse`, the report writers, and the eval
harness) across the method x top-k matrix with method-specific late-fusion
weights and per-k LLM masking, then assembles the paper-ready summary tables.

Method weights (sum to 1.0 before renormalization):

    static_only  : static=1.0  ranker=0.0  llm=0.0
    ranker_only  : static=0.0  ranker=1.0  llm=0.0
    static_ranker: static=0.4  ranker=0.6  llm=0.0
    static_llm   : static=0.5  ranker=0.0  llm=0.5
    full         : static=0.25 ranker=0.45 llm=0.30

Rules:
* k == 0          -> llm weight forced to 0 and the remaining weights renormalized.
* k  > 0          -> LLM verdicts applied ONLY to the top-k samples by rank score
                     (the verdicts file is sliced to those sample_ids).
* methods without an llm term always receive an empty verdicts file.

Everything is deterministic.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from semvulguard.eval.ranking import (
    compute_mrr,
    compute_ndcg_at_k,
    compute_recall_at_k,
)
from semvulguard.eval.run import evaluate, write_reports
from semvulguard.models.fusion.run import fuse, write_fusion_scores
from semvulguard.report.json_report import write_findings_json, write_findings_jsonl
from semvulguard.report.sarif_report import write_sarif
from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import LLMVerdict
from semvulguard.utils.jsonl import read_jsonl, read_models, write_jsonl

EXP = Path("artifacts/experiments")
THRESHOLD = 0.5

METHODS: dict[str, dict[str, float]] = {
    "static_only":   {"static": 1.0,  "ranker": 0.0,  "llm": 0.0},
    "ranker_only":   {"static": 0.0,  "ranker": 1.0,  "llm": 0.0},
    "static_ranker": {"static": 0.4,  "ranker": 0.6,  "llm": 0.0},
    "static_llm":    {"static": 0.5,  "ranker": 0.0,  "llm": 0.5},
    "full":          {"static": 0.25, "ranker": 0.45, "llm": 0.30},
}
METHOD_FLAGS = {
    "static_only":   (True,  False, False),
    "ranker_only":   (False, True,  False),
    "static_ranker": (True,  True,  False),
    "static_llm":    (True,  False, True),
    "full":          (True,  True,  True),
}


def _renormalize_no_llm(weights: dict[str, float]) -> dict[str, float]:
    """Drop the llm term and renormalize static+ranker to sum to 1.0."""
    w = {"static": weights["static"], "ranker": weights["ranker"], "llm": 0.0}
    s = w["static"] + w["ranker"]
    if s > 0:
        w["static"] /= s
        w["ranker"] /= s
    return w


def _topk_sample_ids(rank_scores_path: Path, k: int) -> list[str]:
    rows = list(read_jsonl(rank_scores_path))
    ordered = sorted(rows, key=lambda r: (-float(r["rank_score"]), r["sample_id"]))
    return [r["sample_id"] for r in ordered[:k]]


def _slice_verdicts(verdicts_path: Path, keep_ids: set[str], out_path: Path) -> int:
    """Write a verdicts file containing only verdicts for keep_ids."""
    kept = [v for v in read_models(verdicts_path, LLMVerdict) if v.sample_id in keep_ids]
    return write_jsonl(out_path, kept)


def run_cell(
    *,
    dataset: str,
    method: str,
    k: int,
    base_dir: Path,
    features_path: Path,
    rank_scores_path: Path,
    alerts_path: Path,
    verdicts_path: Path | None,
    ground_truth_lines_path: Path | None,
    cost_log_path: Path | None,
) -> dict:
    """Run fusion + eval for one (method, k) cell. Returns a flat result row."""
    out_dir = base_dir / method / f"topk_{k}"
    out_dir.mkdir(parents=True, exist_ok=True)

    use_static, use_ranker, use_llm = METHOD_FLAGS[method]
    weights = dict(METHODS[method])
    if k == 0:
        weights = _renormalize_no_llm(weights)

    # Build the verdicts file this cell sees.
    cell_verdicts = out_dir / "_llm_verdicts_used.jsonl"
    llm_verified_count = 0
    if use_llm and k > 0 and verdicts_path is not None and verdicts_path.exists():
        keep = set(_topk_sample_ids(rank_scores_path, k))
        llm_verified_count = _slice_verdicts(verdicts_path, keep, cell_verdicts)
    else:
        write_jsonl(cell_verdicts, [])  # empty -> no LLM contribution

    # Fuse with method weights.
    findings, score_rows = fuse(
        features_path=features_path,
        rank_scores_path=rank_scores_path,
        alerts_path=alerts_path,
        llm_verdicts_path=cell_verdicts,
        threshold=THRESHOLD,
        weights=weights,
    )

    # Report artifacts.
    features_by_id = {f.sample_id: f for f in read_models(features_path, FeatureRecord)}
    write_findings_json(
        findings, out_dir / "findings.json",
        metadata={
            "dataset": dataset, "method": method, "top_k": k,
            "weights": weights, "threshold": THRESHOLD,
            "static_enabled": use_static, "ranker_enabled": use_ranker,
            "llm_enabled": use_llm and k > 0,
        },
    )
    write_findings_jsonl(findings, out_dir / "findings.jsonl")
    write_sarif(findings, features_by_id, out_dir / "findings.sarif")
    write_fusion_scores(score_rows, out_dir / "fusion_scores.jsonl")

    # Evaluate.
    metrics = evaluate(
        features_path=features_path,
        findings_path=out_dir / "findings.jsonl",
        rank_scores_path=rank_scores_path,
        ground_truth_lines_path=ground_truth_lines_path,
        cost_log_path=cost_log_path if (cost_log_path and cost_log_path.exists()) else None,
        threshold=THRESHOLD,
    )
    write_reports(metrics, out_dir)

    # Honor "conditional" deliverables: drop empties when inputs absent.
    if not ground_truth_lines_path:
        (out_dir / "localization_metrics.json").unlink(missing_ok=True)
    if not (cost_log_path and cost_log_path.exists()):
        (out_dir / "cost_metrics.json").unlink(missing_ok=True)

    cls = metrics["classification"]
    cm = cls["confusion_matrix"]
    cost = metrics.get("cost") or {}
    row = {
        "dataset": dataset, "method": method, "top_k": k,
        "sample_count": metrics["num_samples"],
        "precision": cls["precision"], "recall": cls["recall"], "f1": cls["f1"],
        "mcc": cls["mcc"], "pr_auc": cls["pr_auc"], "roc_auc": cls["roc_auc"],
        "tp": cm["tp"], "fp": cm["fp"], "tn": cm["tn"], "fn": cm["fn"],
        "static_enabled": use_static, "ranker_enabled": use_ranker,
        "llm_enabled": use_llm and k > 0,
        "total_cost_usd": cost.get("total_cost_usd", 0.0),
        "avg_latency_seconds": cost.get("avg_latency_seconds", 0.0),
        "llm_verified_count": llm_verified_count,
    }
    return row


def _fmt(x) -> str:
    if x is None:
        return ""
    if isinstance(x, float):
        return f"{x:.6f}"
    return str(x)


def write_overall_csv(rows: list[dict], path: Path) -> None:
    cols = ["dataset", "method", "top_k", "sample_count", "precision", "recall",
            "f1", "mcc", "pr_auc", "roc_auc", "tp", "fp", "tn", "fn"]
    _write_csv(rows, cols, path)


def write_ablation_csv(rows: list[dict], path: Path) -> None:
    cols = ["dataset", "method", "top_k", "static_enabled", "ranker_enabled",
            "llm_enabled", "precision", "recall", "f1", "mcc", "fp"]
    _write_csv(rows, cols, path)


def write_topk_csv(rows: list[dict], path: Path) -> None:
    cols = ["dataset", "method", "top_k", "precision", "recall", "f1", "mcc",
            "total_cost_usd", "avg_latency_seconds", "llm_verified_count"]
    _write_csv(rows, cols, path)


def _write_csv(rows: list[dict], cols: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow([_fmt(r.get(c)) for c in cols])


def write_fp_reduction_csv(rows: list[dict], path: Path, datasets: list[str], ks: list[int]) -> None:
    """static_ranker vs full and static_only vs static_llm, per dataset/top_k."""
    idx = {(r["dataset"], r["method"], r["top_k"]): r for r in rows}
    pairs = [("static_ranker", "full"), ("static_only", "static_llm")]
    out: list[dict] = []
    for ds in datasets:
        for k in ks:
            for base, llm in pairs:
                b = idx.get((ds, base, k))
                a = idx.get((ds, llm, k))
                if not b or not a:
                    continue
                out.append({
                    "dataset": ds, "baseline_method": base, "llm_method": llm,
                    "top_k": k,
                    "fp_before": b["fp"], "fp_after": a["fp"],
                    "fp_reduction": b["fp"] - a["fp"],
                    "precision_before": b["precision"], "precision_after": a["precision"],
                    "precision_gain": a["precision"] - b["precision"],
                })
    cols = ["dataset", "baseline_method", "llm_method", "top_k", "fp_before",
            "fp_after", "fp_reduction", "precision_before", "precision_after",
            "precision_gain"]
    _write_csv(out, cols, path)


def write_ranking_quality_csv(datasets: list[str], paths: dict, path: Path) -> None:
    """Ranking quality of the rank_score and the full-fusion final score."""
    out: list[dict] = []
    for ds in datasets:
        p = paths[ds]
        labels = {r["sample_id"]: int(r["label"]) for r in read_jsonl(p["rank_scores"])}
        rank = {r["sample_id"]: float(r["rank_score"]) for r in read_jsonl(p["rank_scores"])}
        score_types = {"rank_score": rank}
        # full-fusion final score at the largest k, if available
        full_fs = p.get("full_fusion_scores")
        if full_fs and Path(full_fs).exists():
            fs = {r["sample_id"]: float(r["final_score"]) for r in read_jsonl(full_fs)}
            score_types["full_fusion"] = fs
        for st, scores in score_types.items():
            out.append({
                "dataset": ds, "score_type": st,
                "recall_at_10": compute_recall_at_k(labels, scores, 10),
                "recall_at_30": compute_recall_at_k(labels, scores, 30),
                "recall_at_50": compute_recall_at_k(labels, scores, 50),
                "mrr": compute_mrr(labels, scores),
                "ndcg_at_50": compute_ndcg_at_k(labels, scores, 50),
            })
    cols = ["dataset", "score_type", "recall_at_10", "recall_at_30",
            "recall_at_50", "mrr", "ndcg_at_50"]
    _write_csv(out, cols, path)
