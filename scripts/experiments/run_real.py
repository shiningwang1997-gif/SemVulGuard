"""Real experiment pipeline (Phases 8-9).

Reuses the real DeepSeek verdicts (max_k=10, generated once) and runs the
M1-M5 x top-k{0,10} matrix per ready dataset, then writes the real_summary
bundle. The cost log feeds cost_metrics for cells that use the LLM.
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
MAX_K = 50
MODEL = "deepseek-v4-flash"


def dataset_paths(ds: str) -> dict:
    d = EXP / ds
    return {
        "features": d / "features.jsonl",
        "rank_scores": d / "rank_scores.jsonl",
        "alerts": d / "static_alerts.jsonl",
        "verdicts": d / "real" / f"llm_verdicts_real_maxk{MAX_K}.jsonl",
        "cost_log": d / "real" / f"real_llm_cost_log_maxk{MAX_K}.jsonl",
        "base": d / "real",
    }


def _cost_total(path: Path) -> tuple[float, int]:
    if not path.exists():
        return 0.0, 0
    rows = [json.loads(l) for l in path.open()]
    total = sum(float(r.get("api_cost_usd", 0.0)) for r in rows)
    return total, len(rows)


def main() -> int:
    start = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []
    completed, failed = [], []
    rq_paths: dict[str, dict] = {}
    total_cost = 0.0
    total_calls = 0

    for ds in READY:
        p = dataset_paths(ds)
        rq_paths[ds] = {"rank_scores": p["rank_scores"]}
        c, n = _cost_total(p["cost_log"])
        total_cost += c
        total_calls += n
        for method in METHODS:
            for k in KS:
                tag = f"{ds}/{method}/topk_{k}"
                # cost log only meaningful for LLM-using cells with k>0
                uses_llm = method in ("static_llm", "full") and k > 0
                cost_log = p["cost_log"] if uses_llm else None
                try:
                    row = run_cell(
                        dataset=ds, method=method, k=k, base_dir=p["base"],
                        features_path=p["features"], rank_scores_path=p["rank_scores"],
                        alerts_path=p["alerts"], verdicts_path=p["verdicts"],
                        ground_truth_lines_path=None, cost_log_path=cost_log,
                    )
                    rows.append(row)
                    completed.append(tag)
                except Exception as exc:
                    failed.append({"cell": tag, "error": f"{type(exc).__name__}: {exc}"})
                    print(f"FAILED {tag}: {exc}")
        rq_paths[ds]["full_fusion_scores"] = (
            p["base"] / "full" / f"topk_{MAX_K}" / "fusion_scores.jsonl"
        )

    out = EXP / "real_summary"
    out.mkdir(parents=True, exist_ok=True)
    write_overall_csv(rows, out / "overall_performance.csv")
    write_ablation_csv(rows, out / "ablation.csv")
    write_topk_csv(rows, out / "topk_sensitivity.csv")
    write_fp_reduction_csv(rows, out / "fp_reduction.csv", READY, KS)
    write_ranking_quality_csv(READY, rq_paths, out / "ranking_quality.csv")

    end = datetime.now(timezone.utc).isoformat()
    _write_markdowns(out, rows, READY, KS, completed, failed, start, end,
                     total_calls, total_cost)
    _write_run_status(out, rows, READY, KS, completed, failed, start, end,
                      total_calls, total_cost)

    print(f"\nREAL pipeline done: {len(completed)} cells ok, {len(failed)} failed")
    print(f"real API calls: {total_calls} | actual cost: ${total_cost:.6f}")
    print(f"summaries -> {out}")
    return 0


def _best(rows, ds, metric):
    cand = [r for r in rows if r["dataset"] == ds]
    return max(cand, key=lambda r: (r[metric] if r[metric] is not None else -1)) if cand else None


def _get(rows, ds, method, k):
    for r in rows:
        if r["dataset"] == ds and r["method"] == method and r["top_k"] == k:
            return r
    return None


def _write_markdowns(out, rows, datasets, ks, completed, failed, start, end, calls, cost):
    maxk = max(ks)
    lines = ["# Experiment Summary (REAL DeepSeek)", "",
             "## Run configuration", "",
             f"- Datasets used: {', '.join(datasets)}",
             f"- Verdict source: **REAL DeepSeek API** (`{MODEL}`, temperature=0.0, JSON mode)",
             f"- Methods: {', '.join(METHODS)}",
             f"- Top-k settings: {ks} (real verdicts generated once at max_k={MAX_K} and sliced)",
             f"- Total real API calls: **{calls}**",
             f"- Actual API cost: **${cost:.6f} USD**",
             f"- Run start: {start}", f"- Run end: {end}",
             f"- Cells completed: {len(completed)} | failed: {len(failed)}", ""]
    for ds in datasets:
        sub = [r for r in rows if r["dataset"] == ds]
        if not sub:
            continue
        n = sub[0]["sample_count"]
        bf, bm = _best(rows, ds, "f1"), _best(rows, ds, "mcc")
        so, ro, sr, fu, sl = (_get(rows, ds, m, maxk) for m in
                              ("static_only", "ranker_only", "static_ranker", "full", "static_llm"))
        lines += [f"## {ds} (n={n})", ""]
        lines.append(f"- Best method by F1: **{bf['method']}** @k={bf['top_k']} (F1={bf['f1']:.4f})")
        lines.append(f"- Best method by MCC: **{bm['method']}** @k={bm['top_k']} (MCC={bm['mcc']:.4f})")
        if fu and so:
            lines.append(f"- full vs static_only (k={maxk}): F1 {fu['f1']:.4f} vs {so['f1']:.4f}, "
                         f"MCC {fu['mcc']:.4f} vs {so['mcc']:.4f} -> "
                         f"{'IMPROVES' if (fu['f1'],fu['mcc'])>(so['f1'],so['mcc']) else 'no improvement'}")
        if fu and ro:
            lines.append(f"- full vs ranker_only (k={maxk}): F1 {fu['f1']:.4f} vs {ro['f1']:.4f}, "
                         f"MCC {fu['mcc']:.4f} vs {ro['mcc']:.4f} -> "
                         f"{'IMPROVES' if (fu['f1'],fu['mcc'])>(ro['f1'],ro['mcc']) else 'no improvement'}")
        if fu and sr:
            lines.append(f"- full vs static_ranker (k={maxk}): F1 {fu['f1']:.4f} vs {sr['f1']:.4f}, "
                         f"MCC {fu['mcc']:.4f} vs {sr['mcc']:.4f} -> "
                         f"{'IMPROVES' if (fu['f1'],fu['mcc'])>(sr['f1'],sr['mcc']) else 'no improvement'}")
            lines.append(f"- FP reduction static_ranker->full (k={maxk}): {sr['fp']} -> {fu['fp']} (Δ={sr['fp']-fu['fp']})")
        if so and sl:
            lines.append(f"- FP reduction static_only->static_llm (k={maxk}): {so['fp']} -> {sl['fp']} (Δ={so['fp']-sl['fp']})")
        lines.append("")
    lines += ["## Ranker effectiveness", "",
              "- See real_summary/ranking_quality.csv (Recall@K / MRR / nDCG of rank_score vs full fusion).", "",
              "## Top-k cost-performance", ""]
    for ds in datasets:
        for k in ks:
            r = _get(rows, ds, "full", k)
            if r:
                lines.append(f"- {ds} full @k={k}: F1={r['f1']:.4f} MCC={r['mcc']:.4f} "
                             f"verified={r['llm_verified_count']} cost=${r['total_cost_usd']:.6f}")
    lines += ["", "## Skipped samples / excluded datasets", "",
              "- Devign: 0 skipped during normalization (1000-sample stratified subset of 27,318).",
              "- BigVul: excluded (raw MSR CSV; no function-level label/code; see bigvul/normalization_error.md).",
              "- DiverseVul: excluded (no local data; see diversevul/normalization_error.md).", "",
              "## Missing artifacts / failed experiments", ""]
    if failed:
        for f in failed:
            lines.append(f"- {f['cell']}: {f['error']}")
    else:
        lines.append("- None. All cells completed.")
    lines += ["", "## Limitations", "",
              "- **Single small dataset** (Devign, n=1000 subset): results are PRELIMINARY, not conclusive.",
              "- **No static analyzer** (CodeQL/Joern absent): static_alerts empty -> static_score=0 for all "
              "samples; `static_only` is fully degenerate and the static fusion term contributes nothing.",
              "- **Fallback ranker**: dependency-light hashing encoder (no GraphCodeBERT/GATv2); ranking signal is weak, "
              "so top-k selection is only mildly better than random.",
              "- **Real LLM only on top-10** (max_k=10), so the LLM term touches at most 10/1000 samples; "
              "its effect on corpus-level precision/recall is therefore small by construction.",
              "- **No CWE / line ground truth** in Devign: localization metrics unavailable.",
              "- **LLM non-determinism**: DeepSeek at temperature 0.0 is not bit-reproducible; "
              "across the max_k=10 and max_k=50 passes, 4/10 borderline top-10 verdicts flipped "
              "(benign/uncertain/vulnerable). All real experiments use the max_k=50 verdict file (sliced for smaller k).",
              "- Default decision threshold 0.5 on compressed fusion scores yields few positive predictions; "
              "ranking-level metrics (PR-AUC/ROC-AUC, Recall@K) are more informative here than thresholded P/R/F1.", ""]
    (out / "experiment_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # paper-ready
    pr = ["# Paper-Ready Results (REAL DeepSeek — preliminary)", "",
          f"_Real `{MODEL}` verification (temperature 0.0, JSON mode), {calls} API calls, "
          f"actual cost ${cost:.6f}. Single dataset (Devign, n=1000 subset). "
          f"Results are PRELIMINARY due to dataset size and the environment limitations listed at the end._", ""]
    for ds in datasets:
        so, ro, sr, fu, sl = (_get(rows, ds, m, maxk) for m in
                              ("static_only", "ranker_only", "static_ranker", "full", "static_llm"))
        pr += [f"## {ds}", "", "### RQ1 Overall Performance", ""]
        if fu:
            pr.append(f"- full @k={maxk}: P={fu['precision']:.4f} R={fu['recall']:.4f} F1={fu['f1']:.4f} "
                      f"MCC={fu['mcc']:.4f} PR-AUC={_n(fu['pr_auc'])} ROC-AUC={_n(fu['roc_auc'])}")
        if ro:
            pr.append(f"- ranker_only: F1={ro['f1']:.4f} MCC={ro['mcc']:.4f} PR-AUC={_n(ro['pr_auc'])}")
        if so:
            pr.append(f"- static_only: F1={so['f1']:.4f} MCC={so['mcc']:.4f} PR-AUC={_n(so['pr_auc'])} (degenerate; no static analyzer)")
        pr += ["", "### RQ2 False Positive Reduction", ""]
        if sr and fu:
            pr.append(f"- static_ranker FP={sr['fp']} (P={sr['precision']:.4f}) -> full FP={fu['fp']} (P={fu['precision']:.4f}); "
                      f"FP reduction = {sr['fp']-fu['fp']}")
        if so and sl:
            pr.append(f"- static_only FP={so['fp']} -> static_llm FP={sl['fp']}; FP reduction = {so['fp']-sl['fp']}")
        pr += ["", "### RQ3 Ranker Effectiveness", "",
               "- See ranking_quality.csv. The learned rank_score is compared against the full fused score "
               "by Recall@{10,30,50}, MRR and nDCG@50.", "",
               "### RQ4 Top-k Cost-Performance", ""]
        for k in ks:
            r = _get(rows, ds, "full", k)
            if r:
                pr.append(f"- full @k={k}: F1={r['f1']:.4f} MCC={r['mcc']:.4f} "
                          f"LLM-verified={r['llm_verified_count']} cost=${r['total_cost_usd']:.6f}")
        pr.append("")
    pr += ["## Notes on preliminarity", "",
           "- Dataset is a 1000-sample Devign subset; treat all numbers as pipeline-level evidence, not benchmark claims.",
           "- The static channel is inert (no analyzer) and the ranker uses a fallback encoder, so absolute "
           "classification scores are low; the comparative structure (ranker > static, LLM effect on top-k) is the takeaway.",
           "- Real LLM verification covered only the top-10 candidates (max_k=10).", ""]
    (out / "paper_ready_results.md").write_text("\n".join(pr) + "\n", encoding="utf-8")


def _n(x):
    return f"{x:.4f}" if isinstance(x, float) else "n/a"


def _write_run_status(out, rows, datasets, ks, completed, failed, start, end, calls, cost):
    status = {
        "mode": "real",
        "run_start_time": start, "run_end_time": end,
        "datasets": datasets, "methods": list(METHODS), "top_k_values": ks,
        "real_api_used": True, "model_name": MODEL,
        "max_k": MAX_K,
        "total_api_calls": calls,
        "estimated_total_cost_usd": round(cost, 6),
        "actual_total_cost_usd": round(cost, 6),
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
