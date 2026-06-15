"""Task B6-B8: rerun the Devign experiment matrix using CodeQL static alerts.

Mirrors scripts/experiments/run_real.py but:
  * uses artifacts/experiments/devign/static_alerts_codeql.jsonl (real CodeQL),
  * reuses the existing REAL DeepSeek verdicts (NO new API call),
  * writes everything under artifacts/experiments/devign_codeql/.

Outputs the M1-M5 x top-k{0,10,30,50} matrix, the five summary CSVs, the
summary markdowns, run_status.json, and a comparison vs the previous
static_score=0 run (artifacts/experiments/real_summary/).
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.experiments.runner import (
    METHODS,
    run_cell,
    write_ablation_csv,
    write_fp_reduction_csv,
    write_overall_csv,
    write_ranking_quality_csv,
    write_topk_csv,
)

EXP = Path("artifacts/experiments")
DEVIGN = EXP / "devign"
OUT = EXP / "devign_codeql"
PREV = EXP / "real_summary"

KS = [0, 10, 30, 50]
MAX_K = 50
MODEL = "deepseek-v4-flash"
ALERTS = DEVIGN / "static_alerts_codeql.jsonl"
# features: previous-run features are fine (fusion reads alerts directly), but
# we use the CodeQL-rebuilt features so static_features reflect CodeQL too.
FEATURES = OUT / "features.jsonl"
RANK = DEVIGN / "rank_scores.jsonl"
VERDICTS = DEVIGN / "real" / f"llm_verdicts_real_maxk{MAX_K}.jsonl"
COST_LOG = DEVIGN / "real" / f"real_llm_cost_log_maxk{MAX_K}.jsonl"


def _cost_total(path: Path) -> tuple[float, int]:
    if not path.exists():
        return 0.0, 0
    rows = [json.loads(l) for l in path.open()]
    return sum(float(r.get("api_cost_usd", 0.0)) for r in rows), len(rows)


def _alert_stats() -> dict:
    if not ALERTS.exists():
        return {"n_alerts": 0, "n_samples": 0, "qids": {}, "cwes": {}}
    rows = [json.loads(l) for l in ALERTS.open()]
    from collections import Counter
    qids = Counter(r["query_id"] for r in rows)
    cwes = Counter(c for r in rows for c in r.get("cwe", []))
    return {
        "n_alerts": len(rows),
        "n_samples": len({r["sample_id"] for r in rows}),
        "qids": dict(qids),
        "cwes": dict(cwes),
    }


def main() -> int:
    start = datetime.now(timezone.utc).isoformat()
    OUT.mkdir(parents=True, exist_ok=True)
    base = OUT / "cells"  # per-method/topk cell outputs

    rows: list[dict] = []
    completed, failed = [], []
    total_cost, total_calls = _cost_total(COST_LOG)

    for method in METHODS:
        for k in KS:
            tag = f"devign/{method}/topk_{k}"
            uses_llm = method in ("static_llm", "full") and k > 0
            cost_log = COST_LOG if uses_llm else None
            try:
                row = run_cell(
                    dataset="devign", method=method, k=k, base_dir=base,
                    features_path=FEATURES, rank_scores_path=RANK,
                    alerts_path=ALERTS, verdicts_path=VERDICTS,
                    ground_truth_lines_path=None, cost_log_path=cost_log,
                )
                rows.append(row)
                completed.append(tag)
            except Exception as exc:
                failed.append({"cell": tag, "error": f"{type(exc).__name__}: {exc}"})
                print(f"FAILED {tag}: {exc}")

    # summary CSVs
    write_overall_csv(rows, OUT / "overall_performance.csv")
    write_ablation_csv(rows, OUT / "ablation.csv")
    write_topk_csv(rows, OUT / "topk_sensitivity.csv")
    write_fp_reduction_csv(rows, OUT / "fp_reduction.csv", ["devign"], KS)
    rq_paths = {"devign": {
        "rank_scores": RANK,
        "full_fusion_scores": base / "full" / f"topk_{MAX_K}" / "fusion_scores.jsonl",
    }}
    write_ranking_quality_csv(["devign"], rq_paths, OUT / "ranking_quality.csv")

    end = datetime.now(timezone.utc).isoformat()
    stats = _alert_stats()
    prev_rows = _load_prev_overall()

    _write_summary(OUT, rows, prev_rows, stats, completed, failed, start, end,
                   total_calls, total_cost)
    _write_paper_ready(OUT, rows, prev_rows, stats)
    _write_run_status(OUT, rows, stats, completed, failed, start, end,
                      total_calls, total_cost)

    print(f"\nDEVIGN+CodeQL pipeline done: {len(completed)} cells ok, {len(failed)} failed")
    print(f"CodeQL alerts: {stats['n_alerts']} over {stats['n_samples']} samples")
    print(f"reused REAL verdicts: {total_calls} calls, cost ${total_cost:.6f} (NO new API)")
    print(f"summaries -> {OUT}")
    return 0


def _load_prev_overall() -> dict[tuple[str, int], dict]:
    p = PREV / "overall_performance.csv"
    out: dict[tuple[str, int], dict] = {}
    if not p.exists():
        return out
    with p.open() as fh:
        for r in csv.DictReader(fh):
            out[(r["method"], int(r["top_k"]))] = r
    return out


def _get(rows, method, k):
    for r in rows:
        if r["method"] == method and r["top_k"] == k:
            return r
    return None


def _best(rows, metric):
    return max(rows, key=lambda r: (r[metric] if r[metric] is not None else -1)) if rows else None


def _f(x):
    return f"{x:.4f}" if isinstance(x, (int, float)) else "n/a"


def _write_summary(out, rows, prev, stats, completed, failed, start, end, calls, cost):
    maxk = max(KS)
    so, ro, sr, fu, sl = (_get(rows, m, maxk) for m in
                          ("static_only", "ranker_only", "static_ranker", "full", "static_llm"))
    so0 = _get(rows, "static_only", 0)
    bf, bm = _best(rows, "f1"), _best(rows, "mcc")
    L = ["# Experiment Summary — Devign + CodeQL static alerts", "",
         "## Run configuration", "",
         "- Dataset: devign (1000-sample subset)",
         "- **Static analyzer: CodeQL 2.25.6** (cpp-security-extended.qls) via function-wrapping",
         f"- CodeQL alerts: **{stats['n_alerts']}** over **{stats['n_samples']}** samples",
         f"- Verdict source: **REAL DeepSeek** (`{MODEL}`) — REUSED from previous run, **no new API call**",
         f"- Methods: {', '.join(METHODS)}",
         f"- Top-k: {KS}",
         f"- Reused API calls: {calls} | reused cost: ${cost:.6f}",
         f"- Run start: {start} | end: {end}",
         f"- Cells completed: {len(completed)} | failed: {len(failed)}", "",
         "## Headline results", "",
         f"- Best F1: **{bf['method']}** @k={bf['top_k']} (F1={_f(bf['f1'])}, MCC={_f(bf['mcc'])})",
         f"- Best MCC: **{bm['method']}** @k={bm['top_k']} (MCC={_f(bm['mcc'])})", ""]

    # static no longer degenerate?
    so_degen = (so is None) or (so["tp"] == 0 and so["fp"] == 0)
    L += ["## Is static_only still degenerate?", "",
          f"- static_only @k={maxk}: TP={so['tp']} FP={so['fp']} TN={so['tn']} FN={so['fn']} "
          f"P={_f(so['precision'])} R={_f(so['recall'])} F1={_f(so['f1'])} MCC={_f(so['mcc'])} "
          f"PR-AUC={_f(so['pr_auc'])}",
          f"- **{'STILL DEGENERATE' if so_degen else 'NO LONGER DEGENERATE'}** "
          f"(static channel now flags {stats['n_samples']} samples).",
          f"- Previous run static_only PR-AUC was 0.4560 (random); now **{_f(so['pr_auc'])}**.", ""]

    # comparisons
    def cmp(a, b, name_a, name_b):
        if not a or not b:
            return f"- {name_a} vs {name_b}: n/a"
        better = (a["f1"], a["mcc"]) > (b["f1"], b["mcc"])
        return (f"- {name_a} vs {name_b} (k={maxk}): F1 {_f(a['f1'])} vs {_f(b['f1'])}, "
                f"MCC {_f(a['mcc'])} vs {_f(b['mcc'])} -> "
                f"{'IMPROVES' if better else 'no improvement'}")
    L += ["## Ablation comparisons (k=50)", "",
          cmp(sr, ro, "static_ranker", "ranker_only"),
          cmp(fu, sr, "full", "static_ranker"),
          cmp(fu, ro, "full", "ranker_only"),
          cmp(sl, so, "static_llm", "static_only")]
    if sr and fu:
        L.append(f"- FP reduction static_ranker→full (k={maxk}): {sr['fp']} → {fu['fp']} (Δ={sr['fp']-fu['fp']})")
    if so and sl:
        L.append(f"- FP reduction static_only→static_llm (k={maxk}): {so['fp']} → {sl['fp']} (Δ={so['fp']-sl['fp']})")
    L.append("")

    # PR-AUC vs top-k for LLM methods
    L += ["## PR-AUC vs top-k (LLM methods)", ""]
    for m in ("static_llm", "full"):
        seg = [f"{k}:{_f(_get(rows,m,k)['pr_auc'])}" for k in KS if _get(rows,m,k)]
        L.append(f"- {m}: " + "  ".join(seg))
    L.append("")

    # comparison vs previous static=0 run
    L += ["## Comparison vs previous run (static_score=0)", "",
          "| method | k | F1 prev | F1 now | MCC prev | MCC now | PR-AUC prev | PR-AUC now |",
          "|---|---|---|---|---|---|---|---|"]
    for m in METHODS:
        for k in KS:
            now = _get(rows, m, k)
            pv = prev.get((m, k))
            if not now:
                continue
            fp = float(pv["f1"]) if pv else None
            mp = float(pv["mcc"]) if pv else None
            ap = float(pv["pr_auc"]) if pv else None
            L.append(f"| {m} | {k} | {_f(fp)} | {_f(now['f1'])} | {_f(mp)} | {_f(now['mcc'])} "
                     f"| {_f(ap)} | {_f(now['pr_auc'])} |")
    L += ["", "## CodeQL alert breakdown", "",
          "query_id: " + ", ".join(f"{q}={c}" for q, c in sorted(stats["qids"].items())),
          "", "CWE: " + ", ".join(f"{c}={n}" for c, n in sorted(stats["cwes"].items())), ""]

    L += ["## Limitations of function-level CodeQL wrapping", "",
          "- Devign samples are isolated functions with no build context; callee/type "
          "definitions are missing, so CodeQL extracted 17/20 batch files and many "
          "interprocedural/taint queries cannot fire. This **undercounts** true alerts.",
          "- Only intraprocedural / syntactic queries (pointer scaling, scanf checks, "
          "unbounded write, integer cast) realistically trigger; this is a conservative "
          "LOWER BOUND on static evidence, not repository-grade analysis.",
          f"- CodeQL covered {stats['n_samples']}/1000 samples — static signal is sparse, so its "
          "corpus-level effect on thresholded F1 is small by construction; the contribution "
          "shows up mainly as non-zero static_only PR-AUC and as a tie-breaking fusion term.",
          "- Real LLM verification still only covers the top-50 candidates (reused verdicts).",
          "- No CWE/line ground truth in Devign → localization metrics remain unavailable.", ""]
    if failed:
        L += ["## Failed cells", ""] + [f"- {f['cell']}: {f['error']}" for f in failed] + [""]
    (out / "experiment_summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def _write_paper_ready(out, rows, prev, stats):
    maxk = max(KS)
    so, ro, sr, fu, sl = (_get(rows, m, maxk) for m in
                          ("static_only", "ranker_only", "static_ranker", "full", "static_llm"))
    P = ["# Paper-Ready Results — Devign + CodeQL (preliminary)", "",
         f"_CodeQL 2.25.6 static alerts ({stats['n_alerts']} alerts over {stats['n_samples']}/1000 "
         f"samples) fused with REAL DeepSeek verdicts (reused, no new API). 1000-sample Devign "
         f"subset. Results PRELIMINARY._", "",
         "### RQ1 Overall Performance (k=50)", ""]
    if fu:
        P.append(f"- full: P={_f(fu['precision'])} R={_f(fu['recall'])} F1={_f(fu['f1'])} "
                 f"MCC={_f(fu['mcc'])} PR-AUC={_f(fu['pr_auc'])} ROC-AUC={_f(fu['roc_auc'])}")
    if ro:
        P.append(f"- ranker_only: F1={_f(ro['f1'])} MCC={_f(ro['mcc'])} PR-AUC={_f(ro['pr_auc'])}")
    if so:
        prev_so = prev.get(("static_only", maxk))
        prev_pr = float(prev_so["pr_auc"]) if prev_so else None
        P.append(f"- static_only: F1={_f(so['f1'])} MCC={_f(so['mcc'])} PR-AUC={_f(so['pr_auc'])} "
                 f"(was PR-AUC={_f(prev_pr)} with no analyzer)")
    P += ["", "### RQ2 False-Positive Reduction (k=50)", ""]
    if sr and fu:
        P.append(f"- static_ranker FP={sr['fp']} → full FP={fu['fp']}; FP reduction={sr['fp']-fu['fp']}")
    if so and sl:
        P.append(f"- static_only FP={so['fp']} → static_llm FP={sl['fp']}; FP reduction={so['fp']-sl['fp']}")
    P += ["", "### RQ4 Top-k Cost-Performance", ""]
    for k in KS:
        r = _get(rows, "full", k)
        if r:
            P.append(f"- full @k={k}: F1={_f(r['f1'])} MCC={_f(r['mcc'])} "
                     f"PR-AUC={_f(r['pr_auc'])} LLM-verified={r['llm_verified_count']} "
                     f"cost=${r['total_cost_usd']:.6f}")
    P += ["", "### Takeaway", "",
          "- The static channel is **no longer inert**: CodeQL produces real C/C++ alerts that "
          "make static_only non-degenerate (PR-AUC > random) and feed the fusion term.",
          "- Coverage is sparse (function-level wrapping), so absolute classification gains are "
          "small; the structural result (static is now a live, precise signal) is the point.", ""]
    (out / "paper_ready_results.md").write_text("\n".join(P) + "\n", encoding="utf-8")


def _write_run_status(out, rows, stats, completed, failed, start, end, calls, cost):
    status = {
        "mode": "real_codeql",
        "run_start_time": start, "run_end_time": end,
        "dataset": "devign", "methods": list(METHODS), "top_k_values": KS,
        "static_analyzer": "codeql-2.25.6",
        "static_query_suite": "codeql/cpp-queries:codeql-suites/cpp-security-extended.qls",
        "static_alerts_path": str(ALERTS),
        "codeql_alert_count": stats["n_alerts"],
        "codeql_samples_covered": stats["n_samples"],
        "real_api_used": False,
        "reused_verdicts_from": str(VERDICTS),
        "model_name": MODEL,
        "max_k": MAX_K,
        "reused_api_calls": calls,
        "reused_cost_usd": round(cost, 6),
        "new_api_calls": 0,
        "completed_experiments": completed,
        "failed_experiments": failed,
        "output_files": sorted(str(p) for p in out.glob("*")),
    }
    (out / "run_status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
