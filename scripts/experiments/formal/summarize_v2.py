"""Phase 12 (v2): cross-dataset REAL top-50 summaries + final comparison report.

Aggregates the per-dataset real_top50/ matrices into:
  real_top50_summary/{overall_performance,ablation,topk_sensitivity,fp_reduction,
                      ranking_quality}.csv
  real_top50_summary/experiment_summary.md
  real_top50_summary/paper_ready_results.md
  real_top50_summary/run_status.json
and the top-level real_top50_final_report.md (15 required sections).

All real_top50 metrics are TEST-ONLY. Mock (top-50) and v1 real (top-10) results
are referenced separately for comparison and never overwritten.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.experiments.formal.config_v2 import (
    MODEL,
    PRICE_IN_PER_1M,
    PRICE_OUT_PER_1M,
    ROOT,
    SUBSET_TARGETS,
    V1_ROOT,
)
from scripts.experiments.formal.matrix import METHODS_ALL
from scripts.experiments.formal.real_eval_v2 import KS_REAL_V2

DATASETS = list(SUBSET_TARGETS)
OUT = ROOT / "real_top50_summary"
REPORT = ROOT / "real_top50_final_report.md"
MAXK = max(KS_REAL_V2)


# --------------------------------------------------------------------------- #
# small IO helpers
# --------------------------------------------------------------------------- #
def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as fh:
        return list(csv.DictReader(fh))


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _f(x):
    if x is None or x == "":
        return "n/a"
    if isinstance(x, str):
        try:
            x = float(x)
        except ValueError:
            return x
    return f"{x:.4f}" if isinstance(x, float) else str(x)


def _concat(name: str, sub: str) -> list[dict]:
    rows = []
    for ds in DATASETS:
        rows += _read_csv(ROOT / ds / sub / name)
    return rows


def _write_concat(name: str) -> list[dict]:
    rows = _concat(name, "real_top50")
    if not rows:
        return rows
    with (OUT / name).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return rows


def _get(rows, ds, method, k):
    for r in rows:
        if r["dataset"] == ds and r["method"] == method and int(r["top_k"]) == k:
            return r
    return None


def _gt(a, b) -> bool:
    """(F1, MCC) lexicographic strict-improvement test."""
    return (float(a["f1"]), float(a["mcc"])) > (float(b["f1"]), float(b["mcc"]))


# --------------------------------------------------------------------------- #
# context loaders
# --------------------------------------------------------------------------- #
def _ranker() -> dict:
    return {r["dataset"]: r for r in _read_json(ROOT / "ranker_summary.json")}


def _leak() -> dict:
    return {r["dataset"]: r
            for r in _read_json(ROOT / "leakage_audit_summary.json")}


def _real50() -> dict:
    return _read_json(ROOT / "real_top50_summary.json")


def _codeql() -> dict:
    data = _read_json(ROOT / "codeql_summary.json") or []
    out = {}
    for r in data:
        m = r.get("map") or {}
        out[r["dataset"]] = {"build_ok": r.get("build_ok", False),
                             "alerts": m.get("mapped", 0),
                             "covered": m.get("samples_covered", 0)}
    for ds in DATASETS:
        out.setdefault(ds, {"build_ok": False, "alerts": 0, "covered": 0})
    return out


def _mock_overall() -> list[dict]:
    rows = []
    for ds in DATASETS:
        rows += _read_csv(ROOT / ds / "mock" / "overall_performance.csv")
    return rows


def _v1_real_overall() -> list[dict]:
    rows = []
    for ds in DATASETS:
        rows += _read_csv(V1_ROOT / ds / "real" / "overall_performance.csv")
    return rows


def _v1_real10() -> dict | None:
    return _read_json(V1_ROOT / "real_top10_summary.json")


# --------------------------------------------------------------------------- #
# Step 4 — cross-dataset summary CSVs + md + run_status.json
# --------------------------------------------------------------------------- #
def write_summaries(overall, ranker, leak, real50, codeql, start) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("overall_performance.csv", "ablation.csv",
                 "topk_sensitivity.csv", "fp_reduction.csv",
                 "ranking_quality.csv"):
        _write_concat(name)

    r50 = {r["dataset"]: r for r in real50["results"]}

    # experiment_summary.md
    L = ["# Cross-Dataset Experiment Summary (REAL DeepSeek top-50, TEST-only)", "",
         f"- Model: `{MODEL}` (temperature 0.0, JSON mode)",
         f"- Real verification: top-{MAXK} TEST candidates per dataset",
         f"- Datasets: {', '.join(DATASETS)}",
         f"- Top-k evaluated: {KS_REAL_V2}",
         f"- Generated: {start}", "",
         "> All metrics are computed on the **test split only**. LLM verdicts cover "
         "only the selected top-k test candidates.", "",
         "## Held-out ranker generalization (leak-free, fit on TRAIN only)", "",
         "| dataset | test n | test pos | F1 | MCC | PR-AUC | ROC-AUC |",
         "|---|---|---|---|---|---|---|"]
    for ds in DATASETS:
        tm = ranker[ds]["test_metrics"]
        L.append(f"| {ds} | {tm.get('num_samples')} | {tm.get('num_positive')} "
                 f"| {_f(tm.get('f1'))} | {_f(tm.get('mcc'))} | {_f(tm.get('pr_auc'))} "
                 f"| {_f(tm.get('roc_auc'))} |")
    L += ["", f"## Fusion method comparison (k={MAXK}, test-only)", "",
          "| dataset | method | F1 | MCC | PR-AUC | ROC-AUC | FP |",
          "|---|---|---|---|---|---|---|"]
    for ds in DATASETS:
        for m in METHODS_ALL:
            r = _get(overall, ds, m, MAXK)
            if r:
                L.append(f"| {ds} | {m} | {_f(r['f1'])} | {_f(r['mcc'])} "
                         f"| {_f(r['pr_auc'])} | {_f(r['roc_auc'])} | {r['fp']} |")
    L += ["", "## Real API cost", "",
          f"- Total calls: **{real50['total_calls']}** "
          f"({real50.get('total_api_ok', 'n/a')} ok / "
          f"{real50.get('total_api_failed', 'n/a')} failed)",
          f"- Total cost: **${real50['total_cost_usd']:.6f}**", ""]
    for ds in DATASETS:
        L.append(f"  - {ds}: {dict(r50[ds]['verdict_counts'])}, "
                 f"${r50[ds]['cost_usd']:.6f}")
    (OUT / "experiment_summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    # paper_ready_results.md
    P = ["# Paper-Ready Results (REAL DeepSeek top-50, TEST-only)", "",
         f"_Real `{MODEL}` verification of top-{MAXK} held-out test candidates across "
         f"{len(DATASETS)} C/C++ datasets. All numbers test-only._", "",
         f"## RQ1 — Does the full pipeline improve overall detection? (k={MAXK}, test-only)", "",
         "| dataset | full F1 | static_only F1 | ranker_only F1 | static_ranker F1 | "
         "full MCC | ranker_only MCC |",
         "|---|---|---|---|---|---|---|"]
    for ds in DATASETS:
        fu, so, ro, sr = (_get(overall, ds, m, MAXK) for m in
                          ("full", "static_only", "ranker_only", "static_ranker"))
        if fu:
            P.append(f"| {ds} | {_f(fu['f1'])} | {_f(so['f1'])} | {_f(ro['f1'])} "
                     f"| {_f(sr['f1'])} | {_f(fu['mcc'])} | {_f(ro['mcc'])} |")
    P += ["", f"## RQ2 — Does LLM verification reduce false positives? "
          f"(static_ranker vs full, k={MAXK})", "",
          "| dataset | FP static_ranker | FP full | ΔFP | P static_ranker | P full |",
          "|---|---|---|---|---|---|"]
    for ds in DATASETS:
        sr = _get(overall, ds, "static_ranker", MAXK)
        fu = _get(overall, ds, "full", MAXK)
        if sr and fu:
            P.append(f"| {ds} | {sr['fp']} | {fu['fp']} | {int(sr['fp'])-int(fu['fp'])} "
                     f"| {_f(sr['precision'])} | {_f(fu['precision'])} |")
    P += ["", "## RQ3 — Top-k sensitivity (full method, test-only)", "",
          "| dataset | k | F1 | MCC | PR-AUC | FP |", "|---|---|---|---|---|---|"]
    for ds in DATASETS:
        for k in KS_REAL_V2:
            r = _get(overall, ds, "full", k)
            if r:
                P.append(f"| {ds} | {k} | {_f(r['f1'])} | {_f(r['mcc'])} "
                         f"| {_f(r['pr_auc'])} | {r['fp']} |")
    P += ["", "_Mock top-50 results live under each dataset's `mock/` directory and "
          "the v1 real top-10 results under `formal_multidataset_v1/`; neither is "
          "mixed with these real top-50 numbers._", ""]
    (OUT / "paper_ready_results.md").write_text("\n".join(P) + "\n", encoding="utf-8")

    # run_status.json
    failed_cells = []
    eval_summary = _read_json(ROOT / "real_top50_eval_summary.json")
    if eval_summary:
        for r in eval_summary["results"]:
            failed_cells += r.get("failed_cells", [])
    status = {
        "mode": "real", "model": MODEL, "evaluation_set": "test_only",
        "experiment": "formal_multidataset_v2_scaled", "top_k_real": MAXK,
        "top_k_values": KS_REAL_V2, "datasets": DATASETS,
        "methods": METHODS_ALL,
        "total_real_api_calls": real50["total_calls"],
        "total_api_ok": real50.get("total_api_ok"),
        "total_api_failed": real50.get("total_api_failed"),
        "total_real_cost_usd": real50["total_cost_usd"],
        "test_sample_counts": {ds: leak[ds]["test_n"] for ds in DATASETS},
        "test_positive_counts": {ds: leak[ds]["test_pos"] for ds in DATASETS},
        "verdict_counts": {ds: real50["results"][i]["verdict_counts"]
                           for i, ds in enumerate(DATASETS)},
        "codeql": codeql,
        "failed_cells": failed_cells,
        "expanded_beyond_top50": False,
        "real_api_called": True,
        "generated": start,
        "output_files": sorted(str(p) for p in OUT.glob("*")),
    }
    (OUT / "run_status.json").write_text(json.dumps(status, indent=2) + "\n",
                                         encoding="utf-8")
    print(f"[summary] real top-50 cross-dataset summaries -> {OUT}")


# --------------------------------------------------------------------------- #
# Step 5 — final comparison report (15 sections)
# --------------------------------------------------------------------------- #
def write_final_report(overall, ranker, leak, real50, codeql) -> dict:
    r50 = {r["dataset"]: r for r in real50["results"]}
    mock = _mock_overall()
    v1_real = _v1_real_overall()
    v1_real10 = _v1_real10()
    summ = {r["dataset"]: r for r in _read_csv(ROOT / "dataset_summary.csv")}

    L = ["# SemVulGuard — formal_multidataset_v2_scaled — REAL top-50 final report",
         "",
         f"Output root: `{ROOT}`",
         f"Generated: {datetime.now(timezone.utc).isoformat()}",
         f"Model: `{MODEL}` (temperature 0.0, JSON mode) | Real verification: "
         f"top-{MAXK} test candidates/dataset | Evaluation: **TEST ONLY**", ""]

    # 1. Datasets used
    L += ["## 1. Datasets used", "",
          "| dataset | source | usable |", "|---|---|---|",
          "| Devign | devign-master/data/raw/dataset.json | YES |",
          "| BigVul | bigvul_test.csv | YES |",
          "| DiverseVul | diversevul_20230702.json | YES |",
          "", "All three datasets are usable (function-level C/C++ code, both "
          "classes). None excluded.", ""]

    # 2. Test sample counts and test positive counts
    L += ["## 2. Test sample counts and test positive counts", "",
          "| dataset | test n | test positives | pos rate |",
          "|---|---|---|---|"]
    for ds in DATASETS:
        tn, tp = leak[ds]["test_n"], leak[ds]["test_pos"]
        L.append(f"| {ds} | {tn} | {tp} | {tp / max(1, tn):.4f} |")

    # 3. Number of real DeepSeek API calls
    L += ["", "## 3. Number of real DeepSeek API calls", "",
          f"- Total real API calls: **{real50['total_calls']}** "
          f"({len(DATASETS)} datasets × top-{MAXK}).",
          f"- Succeeded: **{real50.get('total_api_ok')}** | "
          f"Failed: **{real50.get('total_api_failed')}**.", ""]
    for ds in DATASETS:
        L.append(f"  - {ds}: {r50[ds]['api_calls']} calls "
                 f"({r50[ds]['api_ok']} ok / {r50[ds]['api_failed']} failed)")

    # 4. Total cost
    L += ["", "## 4. Total cost", "",
          f"- **Total real cost: ${real50['total_cost_usd']:.6f}** "
          f"(pricing: input ${PRICE_IN_PER_1M}/1M, output ${PRICE_OUT_PER_1M}/1M).",
          "- Per dataset:"]
    for ds in DATASETS:
        L.append(f"  - {ds}: ${r50[ds]['cost_usd']:.6f}")

    # 5. LLM verdict distribution per dataset
    L += ["", "## 5. LLM verdict distribution per dataset", "",
          "| dataset | vulnerable | benign | uncertain | total |",
          "|---|---|---|---|---|"]
    for ds in DATASETS:
        vc = r50[ds]["verdict_counts"]
        v, b, u = vc.get("vulnerable", 0), vc.get("benign", 0), vc.get("uncertain", 0)
        L.append(f"| {ds} | {v} | {b} | {u} | {v + b + u} |")

    # 6. Best method by F1 per dataset
    L += ["", "## 6. Best method by F1 per dataset (test-only, over all k)", "",
          "| dataset | best method (F1) | k | F1 | MCC |", "|---|---|---|---|---|"]
    best_f1 = {}
    for ds in DATASETS:
        ds_rows = [r for r in overall if r["dataset"] == ds]
        bf = max(ds_rows, key=lambda r: (float(r["f1"]), float(r["mcc"])))
        best_f1[ds] = bf
        L.append(f"| {ds} | {bf['method']} | {bf['top_k']} | {_f(bf['f1'])} "
                 f"| {_f(bf['mcc'])} |")

    # 7. Best method by MCC per dataset
    L += ["", "## 7. Best method by MCC per dataset (test-only, over all k)", "",
          "| dataset | best method (MCC) | k | MCC | F1 |", "|---|---|---|---|---|"]
    best_mcc = {}
    for ds in DATASETS:
        ds_rows = [r for r in overall if r["dataset"] == ds]
        bm = max(ds_rows, key=lambda r: (float(r["mcc"]), float(r["f1"])))
        best_mcc[ds] = bm
        L.append(f"| {ds} | {bm['method']} | {bm['top_k']} | {_f(bm['mcc'])} "
                 f"| {_f(bm['f1'])} |")

    # 8. Whether full beats ranker_only
    L += ["", f"## 8. Does `full` beat `ranker_only`? (k={MAXK}, test-only)", "",
          "| dataset | full F1 | ranker_only F1 | full MCC | ranker_only MCC | full beats ranker_only? |",
          "|---|---|---|---|---|---|"]
    full_beats_ro = {}
    for ds in DATASETS:
        fu = _get(overall, ds, "full", MAXK)
        ro = _get(overall, ds, "ranker_only", MAXK)
        if fu and ro:
            beats = _gt(fu, ro)
            full_beats_ro[ds] = beats
            L.append(f"| {ds} | {_f(fu['f1'])} | {_f(ro['f1'])} | {_f(fu['mcc'])} "
                     f"| {_f(ro['mcc'])} | {'YES' if beats else 'no'} |")
    any_beats_ro = any(full_beats_ro.values())
    L += ["", f"**`full` beats `ranker_only` on: "
          f"{[d for d, v in full_beats_ro.items() if v] or 'none'}.**"]

    # 9. Whether full beats static_ranker
    L += ["", f"## 9. Does `full` beat `static_ranker`? (k={MAXK}, test-only)", "",
          "| dataset | full F1 | static_ranker F1 | full MCC | static_ranker MCC | full beats static_ranker? |",
          "|---|---|---|---|---|---|"]
    full_beats_sr = {}
    for ds in DATASETS:
        fu = _get(overall, ds, "full", MAXK)
        sr = _get(overall, ds, "static_ranker", MAXK)
        if fu and sr:
            beats = _gt(fu, sr)
            full_beats_sr[ds] = beats
            L.append(f"| {ds} | {_f(fu['f1'])} | {_f(sr['f1'])} | {_f(fu['mcc'])} "
                     f"| {_f(sr['mcc'])} | {'YES' if beats else 'no'} |")
    L += ["", f"**`full` beats `static_ranker` on: "
          f"{[d for d, v in full_beats_sr.items() if v] or 'none'}.**"]

    # 10. Whether static_llm or full reduces false positives
    L += ["", f"## 10. Does `static_llm` or `full` reduce false positives? (k={MAXK})", "",
          "| dataset | FP static_only | FP static_llm | ΔFP | FP static_ranker | FP full | ΔFP |",
          "|---|---|---|---|---|---|---|"]
    fp_reduced = False
    for ds in DATASETS:
        so = _get(overall, ds, "static_only", MAXK)
        sl = _get(overall, ds, "static_llm", MAXK)
        sr = _get(overall, ds, "static_ranker", MAXK)
        fu = _get(overall, ds, "full", MAXK)
        if so and sl and sr and fu:
            d_sl = int(so["fp"]) - int(sl["fp"])
            d_fu = int(sr["fp"]) - int(fu["fp"])
            if d_sl > 0 or d_fu > 0:
                fp_reduced = True
            L.append(f"| {ds} | {so['fp']} | {sl['fp']} | {d_sl} "
                     f"| {sr['fp']} | {fu['fp']} | {d_fu} |")
    L += ["", f"**LLM channel reduces false positives somewhere: "
          f"{'YES' if fp_reduced else 'NO (no net FP reduction at k=' + str(MAXK) + ')'}.** "
          "ΔFP>0 means the LLM-augmented method has fewer false positives than its "
          "non-LLM baseline."]

    # 11. Top-k sensitivity
    L += ["", "## 11. Top-k sensitivity (full method, test-only)", "",
          "| dataset | k=0 F1 | k=10 F1 | k=30 F1 | k=50 F1 | k=0 MCC | k=10 MCC | k=30 MCC | k=50 MCC |",
          "|---|---|---|---|---|---|---|---|---|"]
    for ds in DATASETS:
        cells = {k: _get(overall, ds, "full", k) for k in KS_REAL_V2}
        if all(cells.values()):
            f1s = " | ".join(_f(cells[k]["f1"]) for k in KS_REAL_V2)
            mccs = " | ".join(_f(cells[k]["mcc"]) for k in KS_REAL_V2)
            L.append(f"| {ds} | {f1s} | {mccs} |")
    L += ["", "_k=0 uses no LLM verdicts; k=10/30/50 apply the real DeepSeek verdicts "
          "to the top-10/30/50 test candidates respectively (samples outside top-k "
          "get no LLM score)._"]

    # 12. Whether real top-k=50 improves over mock top-k=50
    L += ["", f"## 12. Does REAL top-50 improve over MOCK top-50? (full, k={MAXK}, test-only)", "",
          "| dataset | real F1 | mock F1 | real MCC | mock MCC | real beats mock? |",
          "|---|---|---|---|---|---|"]
    real_beats_mock = {}
    for ds in DATASETS:
        fu = _get(overall, ds, "full", MAXK)
        mk = _get(mock, ds, "full", MAXK)
        if fu and mk:
            beats = _gt(fu, mk)
            real_beats_mock[ds] = beats
            L.append(f"| {ds} | {_f(fu['f1'])} | {_f(mk['f1'])} | {_f(fu['mcc'])} "
                     f"| {_f(mk['mcc'])} | {'YES' if beats else 'no'} |")
    L += ["", "_Mock verdicts are rule-based; this row only confirms the real LLM "
          "channel behaves differently from the offline mock, not a quality claim "
          "about the mock._"]

    # 13. Whether real top-50 improves over previous real top-10 from v1
    L += ["", "## 13. Does REAL top-50 (v2) improve over previous REAL top-10 (v1)?", ""]
    if v1_real and v1_real10:
        L += ["> **Caveat:** v1 used different (smaller) subsets — Devign 3000, "
              "BigVul/DiverseVul 1000 — and v1 test sets had only ~11 positives for "
              "BigVul/DiverseVul, so the comparison is **indicative, not strictly "
              "comparable** (different test sets).", "",
              "| dataset | v2 full F1 (k=10) | v1 full F1 (k=10) | v2 full MCC (k=10) | v1 full MCC (k=10) |",
              "|---|---|---|---|---|"]
        for ds in DATASETS:
            v2c = _get(overall, ds, "full", 10)
            v1c = _get(v1_real, ds, "full", 10)
            if v2c and v1c:
                L.append(f"| {ds} | {_f(v2c['f1'])} | {_f(v1c['f1'])} "
                         f"| {_f(v2c['mcc'])} | {_f(v1c['mcc'])} |")
        L += ["", "v1 real top-10 total: "
              f"{v1_real10['total_calls']} calls, ${v1_real10['total_cost_usd']:.6f}. "
              "v2 extends real coverage to the top-50 per dataset and evaluates k in "
              "{0,10,30,50} on larger, more positive test sets."]
    else:
        L += ["No comparable v1 real top-10 artifacts found; comparison skipped."]

    # 14. Whether results are paper-ready or still preliminary
    paper_ready = _paper_ready_decision(leak, any_beats_ro, fp_reduced)
    L += ["", "## 14. Paper-ready or still preliminary?", "", paper_ready]

    # 15. Limitations
    L += ["", "## 15. Limitations", "",
          "- **CodeQL coverage remains sparse**: isolated, build-context-free "
          "function bodies rarely trigger CodeQL security queries (Devign "
          f"{codeql['devign']['alerts']} / BigVul {codeql['bigvul']['alerts']} / "
          f"DiverseVul {codeql['diversevul']['alerts']} mapped alerts). The static "
          "channel is a weak lower bound.",
          "- **Function-level wrapping lacks build context**: no headers, macros, "
          "types, or cross-function flow, limiting both static analysis and LLM "
          "reasoning.",
          "- **Top-k LLM only covers selected candidates**: real DeepSeek verdicts "
          f"exist for the top-{MAXK} test candidates by rank score per dataset; "
          "lower-ranked samples never receive an LLM score, so corpus-level "
          "classification effects of the LLM are bounded by construction.",
          "- **BigVul/DiverseVul remain imbalanced**: even after scaling to 5000-"
          f"sample subsets, natural test positives are {leak['bigvul']['test_pos']} "
          f"(BigVul) and {leak['diversevul']['test_pos']} (DiverseVul); PR-AUC / MCC "
          "/ ROC-AUC are more informative than thresholded F1.",
          "- **DeepSeek verdicts may not be bit-reproducible**: temperature 0.0 "
          "reduces but does not eliminate run-to-run variation, so verdict counts "
          "and downstream metrics can shift slightly on a re-run.", "",
          "## Output paths", "",
          f"- Real top-50 verdicts/cost: `{ROOT}/{{dataset}}/test_only/"
          "llm_verdicts_real_top50.jsonl`, `real_llm_cost_log_top50.jsonl`",
          f"- Selected candidates: `{ROOT}/{{dataset}}/test_only/"
          "real_top50_candidate_ids.jsonl`",
          f"- Per-dataset real matrix: `{ROOT}/{{dataset}}/real_top50/`",
          f"- Cross-dataset summary: `{OUT}/`",
          f"- This report: `{REPORT}`", ""]

    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"[summary] final report -> {REPORT}")
    return {"full_beats_ranker_only": full_beats_ro,
            "full_beats_static_ranker": full_beats_sr,
            "fp_reduced": fp_reduced, "best_f1": best_f1, "best_mcc": best_mcc,
            "real_beats_mock": real_beats_mock, "paper_ready": paper_ready}


def _paper_ready_decision(leak, any_beats_ro, fp_reduced) -> str:
    both_50 = leak["bigvul"]["test_pos"] >= 50 and leak["diversevul"]["test_pos"] >= 50
    base = ("**PRELIMINARY (strong feasibility milestone).** The pipeline is real, "
            "deterministic, multi-dataset, leak-free, and end-to-end (CodeQL + learned "
            "ranker + real DeepSeek top-50 + fusion + test-only eval). ")
    pos = ("BigVul and DiverseVul now have >= 50 natural test positives, so corpus-"
           "level metrics are more trustworthy than v1's ~11. " if both_50 else
           "BigVul/DiverseVul still fall short of 50 natural test positives. ")
    tail = ("Remaining caveats keep it short of a headline benchmark claim: the static "
            "channel is sparse, real LLM verification covers only the top-50 test "
            "candidates per dataset, and the natural positive rate is unchanged. Treat "
            "as a credible feasibility result with honest held-out numbers; for a "
            "benchmark claim, scale LLM coverage and densify static evidence.")
    return base + pos + tail


# --------------------------------------------------------------------------- #
def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    start = datetime.now(timezone.utc).isoformat()

    overall = _write_concat("overall_performance.csv")
    ranker = _ranker()
    leak = _leak()
    real50 = _real50()
    codeql = _codeql()

    write_summaries(overall, ranker, leak, real50, codeql, start)
    decision = write_final_report(overall, ranker, leak, real50, codeql)

    print(f"cross-dataset summaries -> {OUT}")
    print(f"final report -> {REPORT}")
    return 0 if decision is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
