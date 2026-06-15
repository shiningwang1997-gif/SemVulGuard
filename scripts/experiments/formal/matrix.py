"""Shared method x top-k matrix runner for the formal experiment.

Wraps the existing ``scripts.experiments.runner.run_cell`` (the validated fusion
+ eval driver) and adds an optional ``llm_only`` method. Provides per-dataset
summary writers (overall/ablation/topk/fp_reduction/ranking_quality CSVs plus
experiment_summary.md / run_status.json) for both mock and real runs.

Every metric here is computed on whatever artifacts are passed in; the callers
(mock.py / real_eval.py) always pass test_only/ artifacts, so all numbers are
test-only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.experiments.runner import (
    METHODS as BASE_METHODS,
)
from scripts.experiments.runner import (
    METHOD_FLAGS as BASE_FLAGS,
)
from scripts.experiments.runner import (
    run_cell,
    write_ablation_csv,
    write_fp_reduction_csv,
    write_overall_csv,
    write_ranking_quality_csv,
    write_topk_csv,
)
from scripts.experiments import runner as _runner

BANNER_MOCK = "MOCK VERDICTS / PIPELINE VALIDATION ONLY / NOT FINAL SCIENTIFIC LLM RESULTS"

# Register llm_only (static=0, ranker=0, llm=1) on top of the existing 5 methods.
# We mutate the runner's module-level dicts so run_cell recognizes it.
if "llm_only" not in BASE_METHODS:
    BASE_METHODS["llm_only"] = {"static": 0.0, "ranker": 0.0, "llm": 1.0}
    BASE_FLAGS["llm_only"] = (False, False, True)

METHODS_ALL = ["static_only", "ranker_only", "static_ranker",
               "static_llm", "full", "llm_only"]


def run_matrix(*, dataset, base_dir, features_path, rank_scores_path,
               alerts_path, verdicts_path, ks, cost_log_path=None,
               methods=None, ground_truth_lines_path=None):
    """Run methods x ks. Returns (rows, completed, failed)."""
    methods = methods or METHODS_ALL
    rows, completed, failed = [], [], []
    for method in methods:
        uses_llm = method in ("static_llm", "full", "llm_only")
        for k in ks:
            tag = f"{dataset}/{method}/topk_{k}"
            cl = cost_log_path if (uses_llm and k > 0) else None
            try:
                row = run_cell(
                    dataset=dataset, method=method, k=k, base_dir=base_dir,
                    features_path=features_path, rank_scores_path=rank_scores_path,
                    alerts_path=alerts_path, verdicts_path=verdicts_path,
                    ground_truth_lines_path=ground_truth_lines_path,
                    cost_log_path=cl,
                )
                rows.append(row)
                completed.append(tag)
            except Exception as exc:  # noqa: BLE001
                failed.append({"cell": tag, "error": f"{type(exc).__name__}: {exc}"})
                print(f"FAILED {tag}: {exc}")
    return rows, completed, failed


def _get(rows, method, k):
    for r in rows:
        if r["method"] == method and r["top_k"] == k:
            return r
    return None


def _best(rows, metric):
    return max(rows, key=lambda r: (r[metric] if r[metric] is not None else -1)) if rows else None


def _f(x):
    if isinstance(x, str):
        try:
            x = float(x)
        except ValueError:
            return x
    return f"{x:.4f}" if isinstance(x, (int, float)) else "n/a"


def write_dataset_summaries(*, ds, out, rows, ks, completed, failed, banner,
                            mode, rank_scores_path, full_fusion_scores,
                            api_calls, cost):
    """Write the standard 5 CSVs + experiment_summary.md + run_status.json."""
    out.mkdir(parents=True, exist_ok=True)
    write_overall_csv(rows, out / "overall_performance.csv")
    write_ablation_csv(rows, out / "ablation.csv")
    write_topk_csv(rows, out / "topk_sensitivity.csv")
    write_fp_reduction_csv(rows, out / "fp_reduction.csv", [ds], ks)
    rq_paths = {ds: {"rank_scores": rank_scores_path}}
    if Path(full_fusion_scores).exists():
        rq_paths[ds]["full_fusion_scores"] = full_fusion_scores
    write_ranking_quality_csv([ds], rq_paths, out / "ranking_quality.csv")

    maxk = max(ks)
    so, ro, sr, fu, sl = (_get(rows, m, maxk) for m in
                          ("static_only", "ranker_only", "static_ranker",
                           "full", "static_llm"))
    bf, bm = _best(rows, "f1"), _best(rows, "mcc")
    n = rows[0]["sample_count"] if rows else 0

    banner_line = f"> **{banner}**\n\n" if banner else ""
    L = [f"# Experiment Summary ({mode.upper()}) — {ds}", "", banner_line.strip(), "",
         "## Configuration", "",
         f"- Evaluation set: **TEST ONLY** (n={n})",
         f"- Methods: {', '.join(METHODS_ALL)}",
         f"- Top-k: {ks}",
         f"- API calls: {api_calls} | cost: ${cost:.6f}",
         f"- Cells: {len(completed)} ok / {len(failed)} failed", ""]
    if bf:
        L += [f"- Best F1: **{bf['method']}**@k={bf['top_k']} (F1={_f(bf['f1'])}, MCC={_f(bf['mcc'])})",
              f"- Best MCC: **{bm['method']}**@k={bm['top_k']} (MCC={_f(bm['mcc'])})", ""]
    L += ["## Ablation (k=" + str(maxk) + ", test-only)", ""]
    def cmp(a, b, na, nb):
        if not a or not b:
            return f"- {na} vs {nb}: n/a"
        better = (a["f1"], a["mcc"]) > (b["f1"], b["mcc"])
        return (f"- {na} vs {nb}: F1 {_f(a['f1'])} vs {_f(b['f1'])}, "
                f"MCC {_f(a['mcc'])} vs {_f(b['mcc'])} -> "
                f"{'IMPROVES' if better else 'no improvement'}")
    L += [cmp(fu, so, "full", "static_only"),
          cmp(fu, ro, "full", "ranker_only"),
          cmp(fu, sr, "full", "static_ranker")]
    if sr and fu:
        L.append(f"- FP static_ranker->full (k={maxk}): {sr['fp']} -> {fu['fp']} (Δ={sr['fp']-fu['fp']})")
    if so and sl:
        L.append(f"- FP static_only->static_llm (k={maxk}): {so['fp']} -> {sl['fp']} (Δ={so['fp']-sl['fp']})")
    L += ["", "## Top-k cost-performance (full)", ""]
    for k in ks:
        r = _get(rows, "full", k)
        if r:
            L.append(f"- full@k={k}: F1={_f(r['f1'])} MCC={_f(r['mcc'])} "
                     f"PR-AUC={_f(r['pr_auc'])} verified={r['llm_verified_count']} "
                     f"cost=${r['total_cost_usd']:.6f}")
    if failed:
        L += ["", "## Failed cells", ""] + [f"- {fc['cell']}: {fc['error']}" for fc in failed]
    L.append("")
    (out / "experiment_summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    status = {
        "mode": mode, "banner": banner, "dataset": ds,
        "evaluation_set": "test_only", "sample_count": n,
        "methods": METHODS_ALL, "top_k_values": ks,
        "api_calls": api_calls, "cost_usd": round(cost, 6),
        "completed": completed, "failed": failed,
        "generated": datetime.now(timezone.utc).isoformat(),
        "output_files": sorted(str(p) for p in out.glob("*")),
    }
    (out / "run_status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")


__all__ = ["run_matrix", "write_dataset_summaries", "METHODS_ALL", "BANNER_MOCK"]
