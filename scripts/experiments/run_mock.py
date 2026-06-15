"""Mock experiment pipeline (Phase 5).

Runs the M1-M5 x top-k{0,10,30,50} matrix for every ready dataset using the
mock LLM verdicts (no API), writes per-cell artifacts under
``artifacts/experiments/{dataset}/mock/{method}/topk_{k}/`` and the summary
bundle under ``artifacts/experiments/mock_summary/``.

All results are explicitly labeled MOCK / pipeline-validation only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.experiments.runner import (
    EXP,
    METHODS,
    run_cell,
    write_ablation_csv,
    write_fp_reduction_csv,
    write_overall_csv,
    write_ranking_quality_csv,
    write_topk_csv,
)

READY = ["devign"]
KS = [0, 10, 30, 50]
MOCK_BANNER = "MOCK VERDICTS / PIPELINE VALIDATION ONLY / NOT FINAL SCIENTIFIC RESULTS"


def dataset_paths(ds: str) -> dict:
    d = EXP / ds
    return {
        "features": d / "features.jsonl",
        "rank_scores": d / "rank_scores.jsonl",
        "alerts": d / "static_alerts.jsonl",
        "verdicts": d / "llm_verdicts_mock.jsonl",
        "base": d / "mock",
    }


def main() -> int:
    start = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []
    completed, failed = [], []
    rq_paths: dict[str, dict] = {}

    for ds in READY:
        p = dataset_paths(ds)
        rq_paths[ds] = {"rank_scores": p["rank_scores"]}
        for method in METHODS:
            for k in KS:
                tag = f"{ds}/{method}/topk_{k}"
                try:
                    row = run_cell(
                        dataset=ds, method=method, k=k, base_dir=p["base"],
                        features_path=p["features"], rank_scores_path=p["rank_scores"],
                        alerts_path=p["alerts"], verdicts_path=p["verdicts"],
                        ground_truth_lines_path=None, cost_log_path=None,
                    )
                    rows.append(row)
                    completed.append(tag)
                except Exception as exc:
                    failed.append({"cell": tag, "error": f"{type(exc).__name__}: {exc}"})
                    print(f"FAILED {tag}: {exc}")
        # path to full-fusion final scores at largest k for ranking-quality table
        rq_paths[ds]["full_fusion_scores"] = (
            p["base"] / "full" / f"topk_{max(KS)}" / "fusion_scores.jsonl"
        )

    out = EXP / "mock_summary"
    out.mkdir(parents=True, exist_ok=True)
    write_overall_csv(rows, out / "overall_performance.csv")
    write_ablation_csv(rows, out / "ablation.csv")
    write_topk_csv(rows, out / "topk_sensitivity.csv")
    write_fp_reduction_csv(rows, out / "fp_reduction.csv", READY, KS)
    write_ranking_quality_csv(READY, rq_paths, out / "ranking_quality.csv")

    end = datetime.now(timezone.utc).isoformat()
    _write_markdowns(out, rows, READY, KS, completed, failed, start, end)
    _write_run_status(out, rows, READY, KS, completed, failed, start, end)

    print(f"\nMOCK pipeline done: {len(completed)} cells ok, {len(failed)} failed")
    print(f"summaries -> {out}")
    return 0


def _best(rows, ds, metric):
    cand = [r for r in rows if r["dataset"] == ds]
    if not cand:
        return None
    return max(cand, key=lambda r: (r[metric] if r[metric] is not None else -1))


def _get(rows, ds, method, k):
    for r in rows:
        if r["dataset"] == ds and r["method"] == method and r["top_k"] == k:
            return r
    return None


def _write_markdowns(out, rows, datasets, ks, completed, failed, start, end):
    maxk = max(ks)
    lines = [f"# Experiment Summary (MOCK)", "", f"> **{MOCK_BANNER}**", ""]
    lines += [
        "## Run configuration", "",
        f"- Datasets used: {', '.join(datasets)}",
        f"- Verdict source: **MOCK** (offline rule-based MockLLMClient; no DeepSeek API)",
        f"- Methods: {', '.join(METHODS)}",
        f"- Top-k settings: {ks}",
        f"- Threshold: 0.5",
        f"- Run start: {start}",
        f"- Run end: {end}",
        f"- Cells completed: {len(completed)} | failed: {len(failed)}",
        "",
    ]
    for ds in datasets:
        sub = [r for r in rows if r["dataset"] == ds]
        if not sub:
            continue
        n = sub[0]["sample_count"]
        bf, bm = _best(rows, ds, "f1"), _best(rows, ds, "mcc")
        so = _get(rows, ds, "static_only", maxk)
        ro = _get(rows, ds, "ranker_only", maxk)
        sr = _get(rows, ds, "static_ranker", maxk)
        fu = _get(rows, ds, "full", maxk)
        lines += [f"## {ds} (n={n})", ""]
        lines.append(f"- Best method by F1: **{bf['method']}** @k={bf['top_k']} (F1={bf['f1']:.4f})")
        lines.append(f"- Best method by MCC: **{bm['method']}** @k={bm['top_k']} (MCC={bm['mcc']:.4f})")
        if fu and so:
            lines.append(f"- full vs static_only (k={maxk}): F1 {fu['f1']:.4f} vs {so['f1']:.4f} "
                         f"-> {'IMPROVES' if fu['f1']>so['f1'] else 'no improvement'}")
        if fu and ro:
            lines.append(f"- full vs ranker_only (k={maxk}): F1 {fu['f1']:.4f} vs {ro['f1']:.4f} "
                         f"-> {'IMPROVES' if fu['f1']>ro['f1'] else 'no improvement'}")
        if fu and sr:
            lines.append(f"- full vs static_ranker (k={maxk}): F1 {fu['f1']:.4f} vs {sr['f1']:.4f} "
                         f"-> {'IMPROVES' if fu['f1']>sr['f1'] else 'no improvement'}")
            lines.append(f"- FP reduction static_ranker->full (k={maxk}): "
                         f"{sr['fp']} -> {fu['fp']} (Δ={sr['fp']-fu['fp']})")
        lines.append("")
    lines += [
        "## Skipped samples / excluded datasets", "",
        "- Devign: 0 skipped during normalization.",
        "- BigVul: excluded (raw MSR CSV, no function-level label/code; see bigvul/normalization_error.md).",
        "- DiverseVul: excluded (no local data file; see diversevul/normalization_error.md).",
        "",
        "## Limitations", "",
        "- **Mock verdicts**: LLM column is a deterministic offline heuristic, NOT DeepSeek. Use only to validate the pipeline.",
        "- **No static analyzers** (CodeQL/Joern absent): static_alerts is empty, so static_score=0 for all samples; `static_only` is degenerate and the static term contributes nothing to fusion.",
        "- **Ranker** runs on the dependency-light hashing fallback encoder (no GraphCodeBERT/GATv2), so ranking signal is weak.",
        "- **No CWE / line ground truth** in Devign: localization metrics are unavailable.",
        "- Single dataset only (Devign); BigVul/DiverseVul unavailable.",
        "",
    ]
    if failed:
        lines.append("## Failed cells")
        lines.append("")
        for f in failed:
            lines.append(f"- {f['cell']}: {f['error']}")
        lines.append("")
    (out / "experiment_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # paper-ready
    pr = [f"# Paper-Ready Results (MOCK — preliminary)", "", f"> **{MOCK_BANNER}**", ""]
    pr += ["_All numbers below come from MOCK verdicts on a single small dataset "
           "(Devign, n=1000 subset) and are PRELIMINARY pipeline-validation outputs, "
           "not scientific findings._", ""]
    for ds in datasets:
        maxk = max(ks)
        so, ro, sr, fu = (_get(rows, ds, m, maxk) for m in
                          ("static_only", "ranker_only", "static_ranker", "full"))
        sl = _get(rows, ds, "static_llm", maxk)
        pr += [f"## {ds}", ""]
        pr += ["### RQ1 Overall Performance", ""]
        if fu:
            pr.append(f"- full method @k={maxk}: P={fu['precision']:.4f} R={fu['recall']:.4f} "
                      f"F1={fu['f1']:.4f} MCC={fu['mcc']:.4f}")
        if so:
            pr.append(f"- static_only baseline: F1={so['f1']:.4f} MCC={so['mcc']:.4f}")
        if ro:
            pr.append(f"- ranker_only baseline: F1={ro['f1']:.4f} MCC={ro['mcc']:.4f}")
        pr.append("")
        pr += ["### RQ2 False Positive Reduction", ""]
        if sr and fu:
            pr.append(f"- static_ranker FP={sr['fp']} -> full FP={fu['fp']} "
                      f"(reduction {sr['fp']-fu['fp']}); precision {sr['precision']:.4f} -> {fu['precision']:.4f}")
        if so and sl:
            pr.append(f"- static_only FP={so['fp']} -> static_llm FP={sl['fp']} "
                      f"(reduction {so['fp']-sl['fp']})")
        pr.append("")
        pr += ["### RQ3 Ranker Effectiveness", "",
               "- See ranking_quality.csv (Recall@K / MRR / nDCG of rank_score vs full fusion).", ""]
        pr += ["### RQ4 Top-k Cost-Performance", ""]
        for k in ks:
            r = _get(rows, ds, "full", k)
            if r:
                pr.append(f"- full @k={k}: F1={r['f1']:.4f} verified={r['llm_verified_count']} "
                          f"cost=${r['total_cost_usd']:.4f}")
        pr.append("")
    pr += ["## Notes", "",
           "- Results are PRELIMINARY: small single dataset, mock LLM, no static analyzer, fallback encoder.",
           "- Real DeepSeek verification is run separately (Phase 7) and reported under real_summary/.", ""]
    (out / "paper_ready_results.md").write_text("\n".join(pr) + "\n", encoding="utf-8")


def _write_run_status(out, rows, datasets, ks, completed, failed, start, end):
    status = {
        "mode": "mock",
        "banner": MOCK_BANNER,
        "run_start_time": start,
        "run_end_time": end,
        "datasets": datasets,
        "methods": list(METHODS),
        "top_k_values": ks,
        "real_api_used": False,
        "model_name": "mock-rule",
        "total_api_calls": 0,
        "estimated_total_cost_usd": 0.0,
        "completed_experiments": completed,
        "failed_experiments": failed,
        "skipped_experiments": [
            {"dataset": "bigvul", "reason": "raw MSR CSV; no function-level label/code"},
            {"dataset": "diversevul", "reason": "no local data file (README only)"},
        ],
        "output_files": sorted(str(p) for p in out.glob("*")),
    }
    (out / "run_status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
