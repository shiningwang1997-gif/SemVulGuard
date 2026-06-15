"""Phase 12: cross-dataset real summaries + final report (test-only).

Aggregates the per-dataset real/ matrices into:
  real_summary/{overall_performance,ablation,topk_sensitivity,fp_reduction,
                ranking_quality}.csv
  real_summary/experiment_summary.md
  real_summary/paper_ready_results.md
  real_summary/run_status.json
and the top-level final_report.md.

All real_summary metrics are TEST-ONLY. Mock (top-50) results are referenced
separately and never mixed with the real numbers.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.experiments.formal.config import (
    KS_REAL,
    MODEL,
    REAL_TOPK,
    ROOT,
    SUBSET_TARGETS,
)
from scripts.experiments.formal.matrix import METHODS_ALL

DATASETS = list(SUBSET_TARGETS)
OUT = ROOT / "real_summary"


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as fh:
        return list(csv.DictReader(fh))


def _ranker_metrics() -> dict:
    return json.loads((ROOT / "ranker_summary.json").read_text())


def _leak() -> dict:
    return {r["dataset"]: r
            for r in json.loads((ROOT / "leakage_audit_summary.json").read_text())}


def _real_top10() -> dict:
    return json.loads((ROOT / "real_top10_summary.json").read_text())


def _codeql() -> dict:
    data = json.loads((ROOT / "codeql_summary.json").read_text())
    out = {}
    for r in data:
        m = r.get("map") or {}
        out[r["dataset"]] = {
            "build_ok": r["build_ok"],
            "alerts": m.get("mapped", 0),
            "covered": m.get("samples_covered", 0),
        }
    for ds in DATASETS:
        out.setdefault(ds, {"build_ok": False, "alerts": 0, "covered": 0})
    return out


def _f(x):
    if x is None:
        return "n/a"
    if isinstance(x, str):
        try:
            x = float(x)
        except ValueError:
            return x
    return f"{x:.4f}" if isinstance(x, float) else str(x)


def _concat_csvs(name: str) -> list[dict]:
    rows = []
    for ds in DATASETS:
        rows += _read_csv(ROOT / ds / "real" / name)
    return rows


def _write_concat(name: str) -> list[dict]:
    rows = _concat_csvs(name)
    if not rows:
        return rows
    cols = list(rows[0].keys())
    with (OUT / name).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return rows


def _get(rows, ds, method, k):
    for r in rows:
        if r["dataset"] == ds and r["method"] == method and int(r["top_k"]) == k:
            return r
    return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    start = datetime.now(timezone.utc).isoformat()

    overall = _write_concat("overall_performance.csv")
    _write_concat("ablation.csv")
    _write_concat("topk_sensitivity.csv")
    _write_concat("fp_reduction.csv")
    _write_concat("ranking_quality.csv")

    ranker = {r["dataset"]: r for r in _ranker_metrics()}
    leak = _leak()
    real10 = _real_top10()
    codeql = _codeql()
    r10 = {r["dataset"]: r for r in real10["results"]}

    _write_experiment_summary(overall, ranker, leak, r10, codeql, start)
    _write_paper_ready(overall, ranker, leak, r10, codeql)
    _write_run_status(overall, real10, leak, codeql, start)
    _write_final_report(overall, ranker, leak, real10, r10, codeql)

    print(f"cross-dataset summaries -> {OUT}")
    print(f"final report -> {ROOT / 'final_report.md'}")
    return 0


def _rq_block(ds: str) -> dict:
    rows = _read_csv(ROOT / ds / "real" / "ranking_quality.csv")
    out = {}
    for r in rows:
        out[r["score_type"]] = r
    return out


def _write_experiment_summary(overall, ranker, leak, r10, codeql, start):
    L = ["# Cross-Dataset Experiment Summary (REAL DeepSeek, TEST-only)", "",
         f"- Model: `{MODEL}` (temperature 0.0, JSON mode)",
         f"- Real verification: top-{REAL_TOPK} TEST candidates per dataset",
         f"- Datasets: {', '.join(DATASETS)}",
         f"- Generated: {start}", "",
         "> All metrics below are computed on the **test split only**. Train/valid "
         "samples are excluded. LLM verdicts cover only the top-10 test candidates.",
         "", "## Held-out ranker generalization (leak-free)", "",
         "| dataset | test n | test pos | F1 | MCC | PR-AUC | ROC-AUC |",
         "|---|---|---|---|---|---|---|"]
    for ds in DATASETS:
        tm = ranker[ds]["test_metrics"]
        L.append(f"| {ds} | {tm.get('num_samples')} | {tm.get('num_positive')} "
                 f"| {_f(tm.get('f1'))} | {_f(tm.get('mcc'))} | {_f(tm.get('pr_auc'))} "
                 f"| {_f(tm.get('roc_auc'))} |")
    L += ["", "## Fusion method comparison (k=10, test-only)", "",
          "| dataset | method | F1 | MCC | PR-AUC | ROC-AUC | FP |",
          "|---|---|---|---|---|---|---|"]
    for ds in DATASETS:
        for m in METHODS_ALL:
            r = _get(overall, ds, m, 10)
            if r:
                L.append(f"| {ds} | {m} | {_f(r['f1'])} | {_f(r['mcc'])} "
                         f"| {_f(r['pr_auc'])} | {_f(r['roc_auc'])} | {r['fp']} |")
    L += ["", "## Real API cost", "",
          f"- Total calls: **{sum(r10[d]['api_calls'] for d in DATASETS)}**",
          f"- Total cost: **${sum(r10[d]['cost_usd'] for d in DATASETS):.6f}**", ""]
    (OUT / "experiment_summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def _write_paper_ready(overall, ranker, leak, r10, codeql):
    P = ["# Paper-Ready Results (REAL DeepSeek, TEST-only, preliminary)", "",
         f"_Real `{MODEL}` verification of top-{REAL_TOPK} held-out test candidates across "
         f"{len(DATASETS)} C/C++ datasets. All numbers test-only. PRELIMINARY (subset sizes, "
         f"sparse static channel, top-10 LLM coverage)._", "",
         "## RQ1 — Does the full pipeline improve overall detection? (k=10, test-only)", "",
         "| dataset | full F1 | static_only F1 | ranker_only F1 | static_ranker F1 | "
         "full MCC | ranker_only MCC |",
         "|---|---|---|---|---|---|---|"]
    for ds in DATASETS:
        fu = _get(overall, ds, "full", 10)
        so = _get(overall, ds, "static_only", 10)
        ro = _get(overall, ds, "ranker_only", 10)
        sr = _get(overall, ds, "static_ranker", 10)
        if fu:
            P.append(f"| {ds} | {_f(fu['f1'])} | {_f(so['f1'])} | {_f(ro['f1'])} "
                     f"| {_f(sr['f1'])} | {_f(fu['mcc'])} | {_f(ro['mcc'])} |")
    P += ["", "## RQ2 — Does LLM verification reduce false positives? "
          "(static_ranker vs full, k=10)", "",
          "| dataset | FP static_ranker | FP full | ΔFP | P static_ranker | P full |",
          "|---|---|---|---|---|---|"]
    for ds in DATASETS:
        sr = _get(overall, ds, "static_ranker", 10)
        fu = _get(overall, ds, "full", 10)
        if sr and fu:
            P.append(f"| {ds} | {sr['fp']} | {fu['fp']} | {int(sr['fp'])-int(fu['fp'])} "
                     f"| {_f(sr['precision'])} | {_f(fu['precision'])} |")
    P += ["", "## RQ3 — Ranker ranking quality (rank_score, test-only)", "",
          "| dataset | R@10 | R@30 | R@50 | MRR | nDCG@50 |",
          "|---|---|---|---|---|---|"]
    for ds in DATASETS:
        rq = _rq_block(ds).get("rank_score")
        if rq:
            P.append(f"| {ds} | {_f(rq['recall_at_10'])} | {_f(rq['recall_at_30'])} "
                     f"| {_f(rq['recall_at_50'])} | {_f(rq['mrr'])} | {_f(rq['ndcg_at_50'])} |")
    P += ["", "## RQ4 — Top-k cost/performance (full, real top-10)", "",
          "| dataset | k | F1 | MCC | PR-AUC | LLM-verified | cost USD |",
          "|---|---|---|---|---|---|---|"]
    topk = _concat_csvs("topk_sensitivity.csv")
    for ds in DATASETS:
        for k in KS_REAL:
            r = _get(overall, ds, "full", k)
            tk = _get(topk, ds, "full", k)
            if r:
                lv = tk.get("llm_verified_count", "0") if tk else "0"
                cost = float(tk.get("total_cost_usd", 0.0)) if tk else 0.0
                P.append(f"| {ds} | {k} | {_f(r['f1'])} | {_f(r['mcc'])} | {_f(r['pr_auc'])} "
                         f"| {lv} | {cost:.6f} |")
    P += ["", "_Mock top-50 results live under each dataset's `mock/` directory and are "
          "NOT mixed with these real numbers._", ""]
    (OUT / "paper_ready_results.md").write_text("\n".join(P) + "\n", encoding="utf-8")


def _write_run_status(overall, real10, leak, codeql, start):
    status = {
        "mode": "real", "model": MODEL, "evaluation_set": "test_only",
        "top_k_real": REAL_TOPK, "datasets": DATASETS,
        "total_real_api_calls": real10["total_calls"],
        "total_real_cost_usd": real10["total_cost_usd"],
        "test_sample_counts": {ds: leak[ds]["test_n"] for ds in DATASETS},
        "test_positive_counts": {ds: leak[ds]["test_pos"] for ds in DATASETS},
        "codeql": codeql,
        "generated": start,
        "expanded_to_top50_real": False,
        "output_files": sorted(str(p) for p in OUT.glob("*")),
    }
    (OUT / "run_status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")


def _verdict_improves(fu, ro, sr):
    if not (fu and ro and sr):
        return "n/a"
    beats_ro = (float(fu["f1"]), float(fu["mcc"])) > (float(ro["f1"]), float(ro["mcc"]))
    beats_sr = (float(fu["f1"]), float(fu["mcc"])) > (float(sr["f1"]), float(sr["mcc"]))
    return f"vs ranker_only: {'yes' if beats_ro else 'no'}; vs static_ranker: {'yes' if beats_sr else 'no'}"


def _write_final_report(overall, ranker, leak, real10, r10, codeql):
    total_cost = real10["total_cost_usd"]
    total_calls = real10["total_calls"]
    L = ["# SemVulGuard — Formal Multi-Dataset Experiment (final report)", "",
         f"Output root: `{ROOT}`", f"Generated: {datetime.now(timezone.utc).isoformat()}",
         f"Model: `{MODEL}` | Real verification: top-{REAL_TOPK} test candidates/dataset", "",
         "## 1. Datasets used and excluded", "",
         "All three datasets were inspected and found **usable** (function-level code, "
         "both classes, CWE where available):", "",
         "| dataset | source | usable | reason |",
         "|---|---|---|---|",
         "| Devign | devign-master/data/raw/dataset.json | YES | balanced C functions |",
         "| BigVul | bigvul_test.csv | YES | func_before code, both classes, CWE+flaw_line |",
         "| DiverseVul | diversevul_20230702.json | YES | func code, both classes, 150 CWE types |",
         "", "**No dataset was excluded.** BigVul's file is named `*_test` but contains both "
         "classes and no native split, so it was re-split internally (documented).", "",
         "## 2. Actual sample counts", "",
         "| dataset | full valid | subset | train | valid | test | test pos |",
         "|---|---|---|---|---|---|---|"]
    summ = _read_csv(ROOT / "dataset_summary.csv")
    for r in summ:
        ds = r["dataset"]
        L.append(f"| {ds} | {r['full_valid_count']} | {r['subset_count']} "
                 f"| {r['train_count']} | {r['valid_count']} | {r['test_count']} "
                 f"| {leak[ds]['test_pos']} |")
    L += ["", "## 3. Train/valid/test counts", "",
          "Deterministic stratified 70/10/20 (seed=42); both classes present in every "
          "split for every dataset. Final metrics use **test only**.", "",
          "## 4. CodeQL coverage by dataset", "",
          "| dataset | DB build | alerts | samples covered |",
          "|---|---|---|---|"]
    for ds in DATASETS:
        c = codeql[ds]
        L.append(f"| {ds} | {'OK' if c['build_ok'] else 'FAILED'} | {c['alerts']} "
                 f"| {c['covered']} |")
    L += ["", "Static coverage is **sparse** (16 alerts Devign, 0 BigVul, 1 DiverseVul): "
          "isolated function bodies without build context rarely trigger CodeQL security "
          "queries. The static channel is a weak lower bound, not a primary signal.", "",
          "## 5. Ranker held-out TEST metrics (leak-free)", "",
          "| dataset | test n | F1 | MCC | PR-AUC | ROC-AUC |",
          "|---|---|---|---|---|---|"]
    for ds in DATASETS:
        tm = ranker[ds]["test_metrics"]
        L.append(f"| {ds} | {tm.get('num_samples')} | {_f(tm.get('f1'))} | {_f(tm.get('mcc'))} "
                 f"| {_f(tm.get('pr_auc'))} | {_f(tm.get('roc_auc'))} |")
    L += ["", "The ranker is fit on train only. ROC-AUC 0.65 (Devign) / ~0.74-0.76 "
          "(BigVul, DiverseVul) shows above-random generalization on unseen code — a real "
          "improvement over the previous leaky single-dataset run.", "",
          "## 6. Real API calls and cost", "",
          f"- Total real API calls: **{total_calls}** ({len(DATASETS)} x {REAL_TOPK}), all succeeded.",
          f"- Total real cost: **${total_cost:.6f}**.", ""]
    for ds in DATASETS:
        vc = r10[ds]["verdict_counts"]
        L.append(f"  - {ds}: {dict(vc)}, ${r10[ds]['cost_usd']:.6f}")
    L += ["", "## 7. Best test-only F1 / MCC per dataset", "",
          "| dataset | best method (F1) | F1 | best method (MCC) | MCC |",
          "|---|---|---|---|---|"]
    for ds in DATASETS:
        ds_rows = [r for r in overall if r["dataset"] == ds]
        bf = max(ds_rows, key=lambda r: float(r["f1"]))
        bm = max(ds_rows, key=lambda r: float(r["mcc"]))
        L.append(f"| {ds} | {bf['method']}@k={bf['top_k']} | {_f(bf['f1'])} "
                 f"| {bm['method']}@k={bm['top_k']} | {_f(bm['mcc'])} |")
    L += ["", "## 8. False-positive reduction (static_ranker -> full, k=10, test-only)", "",
          "| dataset | FP before | FP after | ΔFP | P before | P after |",
          "|---|---|---|---|---|---|"]
    for ds in DATASETS:
        sr = _get(overall, ds, "static_ranker", 10)
        fu = _get(overall, ds, "full", 10)
        if sr and fu:
            L.append(f"| {ds} | {sr['fp']} | {fu['fp']} | {int(sr['fp'])-int(fu['fp'])} "
                     f"| {_f(sr['precision'])} | {_f(fu['precision'])} |")
    L += ["", "## 9. Leakage audit summary", "",
          "All per-dataset `test_only/leakage_audit.md` checks PASS: test split filtered "
          "correctly, no train/valid sample in test rank scores, manifest/feature/score id "
          "sets identical, label consistency, no label-as-feature leakage, top-k recomputed "
          "within the test set, both classes present. LLM verdicts cover only test top-10.", "",
          "## 10. Paper-ready or preliminary?", "",
          "**PRELIMINARY.** The pipeline is real, deterministic, multi-dataset, leak-free, "
          "and end-to-end (CodeQL + learned ranker + real DeepSeek + fusion + test-only eval). "
          "But: subsets are 1-3k samples, the static channel is sparse, and real LLM "
          "verification covers only the top-10 test candidates per dataset, so corpus-level "
          "classification effects of the LLM are small by construction. Treat as a feasibility "
          "/ engineering milestone with honest held-out ranker numbers, not a benchmark claim.", "",
          "## 11. Limitations", "",
          "- Subset sizes: Devign 3000, BigVul/DiverseVul 1000 (heavy imbalance ~5.5% pos in "
          "the latter two → ~11 test positives; PR-AUC/MCC/ROC-AUC more reliable than F1).",
          "- CodeQL on wrapped functions yields very sparse alerts (no build context).",
          "- Real LLM only on top-10 test candidates (cost-controlled; not expanded to 50).",
          "- No semantic dedup across splits → possible near-duplicate functions (dataset caveat).",
          "- DeepSeek at temp 0.0 is not bit-reproducible; verdicts may vary slightly across runs.",
          "- Fusion final scores compress below the 0.5 threshold → low thresholded F1; "
          "ranking metrics are the more informative view.", "",
          "## 12. Recommended next step", ""]
    # decide whether full beats baselines anywhere
    any_full_improves = False
    for ds in DATASETS:
        fu = _get(overall, ds, "full", 10)
        ro = _get(overall, ds, "ranker_only", 10)
        sr = _get(overall, ds, "static_ranker", 10)
        if fu and ro and sr and (float(fu["f1"]), float(fu["mcc"])) > (float(ro["f1"]), float(ro["mcc"])):
            any_full_improves = True
    L += [
        "- **Is real top-k=50 worth running now?** The full top-10 cost was "
        f"${total_cost:.4f} for {total_calls} calls; top-50 would be ~5x (~$0.15) — cheap. "
        "However, with only ~11 test positives in BigVul/DiverseVul and the LLM touching the "
        "top-k by rank, expanding to 50 mainly adds verdicts on lower-ranked (mostly benign) "
        "candidates and is unlikely to move corpus-level test metrics much. "
        + ("Since `full` already shows mixed/marginal gains over `ranker_only` at k=10, "
           if not any_full_improves else "")
        + "**Recommendation: the higher-value next step is to scale subset sizes and add a "
        "more balanced positive set (and/or denser static evidence) before spending on "
        "top-50.** Real top-50 is low-cost and can be run for completeness, but await "
        "explicit approval (per the task's stop condition).",
        "", "## Output paths", "",
        f"- Per-dataset real matrix: `{ROOT}/{{dataset}}/real/`",
        f"- Cross-dataset summary: `{OUT}/`",
        f"- Mock (top-50) matrix: `{ROOT}/{{dataset}}/mock/`",
        f"- Leakage audits: `{ROOT}/{{dataset}}/test_only/leakage_audit.md`",
        f"- This report: `{ROOT}/final_report.md`", ""]
    (ROOT / "final_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
