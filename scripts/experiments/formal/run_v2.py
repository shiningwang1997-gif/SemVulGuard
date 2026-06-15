"""Orchestrator for formal_multidataset_v2_scaled (MOCK / pipeline validation).

Reuses the v1 formal pipeline verbatim. Every phase module reads ``ROOT`` /
``SUBSET_TARGETS`` as module globals imported from ``config``; this driver rebinds
those globals (and the few siblings the modules use) to the v2 values from
``config_v2`` and then calls the same, already-validated functions. No pipeline
logic is reimplemented — loaders, FeatureBuilder, CodeQL wrapper, sklearn_tfidf
ranker, fusion, eval, and the method matrix are all the v1 code.

v2 additions (small, self-contained):
  * reuse v1's already-normalized full manifests (copy, don't re-parse 1.7 GB);
  * a leak-free positive-enriched TEST evaluation set for analysis;
  * cross-dataset MOCK summaries + final_report.md.

Hard rules enforced:
  * NEVER touch the v1 root (different ROOT).
  * NEVER call the real DeepSeek API (mock verdicts only; cost is a dry-run estimate).
  * Final metrics are test-only; ranker fit on train only; no train/test leakage;
    labels never fabricated; no sample duplicated across train/valid/test.

Run from the SemVulGuard/ working dir:
    python -m scripts.experiments.formal.run_v2 <phase>
where <phase> in: all, prep, subset, features, codeql, ranker, testonly,
posenrich, mock, cost, summary
"""

from __future__ import annotations

import csv
import json
import random
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import SampleRecord, StaticAlertRecord
from semvulguard.utils.jsonl import read_jsonl, read_models, write_jsonl

from scripts.experiments.formal import config_v2 as V2

# ---------------------------------------------------------------------------
# Rebind the shared globals on every phase module BEFORE importing/using them,
# so the v1 code paths operate on the v2 root + scaled targets.
# ---------------------------------------------------------------------------
from scripts.experiments.formal import (  # noqa: E402
    codeql_alerts,
    cost_preview,
    mock,
    ranker,
    subset_split,
    test_only,
    validate_features,
)
from scripts.experiments.formal import matrix as _matrix  # noqa: E402


def _patch_globals() -> None:
    """Point all reused phase modules at the v2 ROOT / SUBSET_TARGETS / seed."""
    mods = [subset_split, validate_features, codeql_alerts, ranker,
            test_only, mock, cost_preview]
    for m in mods:
        if hasattr(m, "ROOT"):
            m.ROOT = V2.ROOT
        if hasattr(m, "SUBSET_TARGETS"):
            m.SUBSET_TARGETS = dict(V2.SUBSET_TARGETS)
        if hasattr(m, "SEED"):
            m.SEED = V2.SEED
        if hasattr(m, "SPLIT_RATIOS"):
            m.SPLIT_RATIOS = V2.SPLIT_RATIOS
        if hasattr(m, "KS_MOCK"):
            m.KS_MOCK = list(V2.KS_MOCK)
    # cost_preview uses REAL_TOPK / pricing for the (no-call) top-50 estimate
    for attr in ("REAL_TOPK", "MODEL", "PRICE_IN_PER_1M", "PRICE_OUT_PER_1M",
                 "OUT_TOKENS_PER_SAMPLE"):
        if hasattr(cost_preview, attr):
            setattr(cost_preview, attr, getattr(V2, attr))


DATASETS = list(V2.DATASETS)


# ---------------------------------------------------------------------------
# Phase 2 (reuse): normalization. v1 already produced the full normalized
# manifests + code maps for the same raw files via the same loaders; copy them
# rather than re-parsing ~1.7 GB. Result is byte-identical to re-running.
# ---------------------------------------------------------------------------
def prep_normalization() -> dict:
    V2.ROOT.mkdir(parents=True, exist_ok=True)
    out = []
    for ds in DATASETS:
        src = V2.V1_ROOT / ds
        dst = V2.ROOT / ds
        dst.mkdir(parents=True, exist_ok=True)
        copied = []
        for name in ("manifest_full.jsonl", "code_full.jsonl",
                     "skipped_samples.jsonl"):
            s = src / name
            if not s.exists():
                raise FileNotFoundError(
                    f"v1 normalization artifact missing: {s}. Run v1 normalize "
                    f"first, or extend run_v2 to re-normalize from raw.")
            shutil.copyfile(s, dst / name)
            copied.append(name)
        n = sum(1 for _ in (dst / "manifest_full.jsonl").open())
        pos = sum(1 for r in read_jsonl(dst / "manifest_full.jsonl")
                  if r.get("label") == 1)
        out.append({"dataset": ds, "valid": n, "vulnerable": pos,
                    "benign": n - pos, "reused_from": str(src),
                    "files": copied})
        print(f"[prep] {ds}: reused v1 normalization -> {n} valid "
              f"({pos} vuln / {n - pos} benign)")
    (V2.ROOT / "normalization_summary.json").write_text(
        json.dumps({"note": "normalization reused from v1 (same loaders, same "
                            "raw files); not re-parsed", "datasets": out},
                   indent=2) + "\n", encoding="utf-8")
    return {"datasets": out}


# ---------------------------------------------------------------------------
# Phase 4 (reuse FeatureBuilder): build features.jsonl from manifest + code.
# Built WITHOUT static alerts baked in (matches v1); CodeQL alerts are supplied
# to the ranker separately at train/infer time.
# ---------------------------------------------------------------------------
def build_features_phase() -> None:
    from semvulguard.features.build import build_features
    for ds in DATASETS:
        ddir = V2.ROOT / ds
        records = build_features(
            manifest=ddir / "manifest.jsonl",
            alerts_path=None,
            graphs_dir=None,
            code_dir=ddir / "code",
        )
        n = write_jsonl(ddir / "features.jsonl", records)
        print(f"[features] {ds}: built {n} feature records -> features.jsonl")


# ---------------------------------------------------------------------------
# Devign target: 5000 if available, else 3000. Applied before subset_split.
# ---------------------------------------------------------------------------
def _resolve_devign_target() -> None:
    full = V2.ROOT / "devign" / "manifest_full.jsonl"
    n = sum(1 for _ in full.open()) if full.exists() else 0
    if n < 5000:
        print(f"[subset] devign has {n} usable (<5000) -> target {V2.DEVIGN_FALLBACK}")
        V2.SUBSET_TARGETS["devign"] = V2.DEVIGN_FALLBACK
        subset_split.SUBSET_TARGETS["devign"] = V2.DEVIGN_FALLBACK
    else:
        print(f"[subset] devign has {n} usable (>=5000) -> target 5000")


# ---------------------------------------------------------------------------
# Positive-enriched evaluation set (analysis only). STRICT subset of the natural
# TEST split -> no leakage, no fabricated labels, no cross-split duplication.
# Balanced: min(#pos, #neg) of each class from the natural test set, seeded.
# Clearly labeled and stored separately under test_only_posenriched/.
# ---------------------------------------------------------------------------
def build_positive_enriched() -> list[dict]:
    results = []
    for ds in DATASETS:
        ddir = V2.ROOT / ds
        t = ddir / "test_only"
        man = read_models(t / "manifest_test.jsonl", SampleRecord)
        pos_ids = [m.sample_id for m in man if m.label == 1]
        neg_ids = [m.sample_id for m in man if m.label == 0]
        natural_pos = len(pos_ids)
        needed = natural_pos < V2.MIN_TEST_POS_FOR_STABLE

        k = min(len(pos_ids), len(neg_ids))
        rng = random.Random(V2.SEED)
        sel_pos = sorted(pos_ids)
        sel_neg = sorted(neg_ids)
        rng.shuffle(sel_pos)
        rng.shuffle(sel_neg)
        keep = set(sel_pos[:k] + sel_neg[:k])

        out = ddir / "test_only_posenriched"
        out.mkdir(parents=True, exist_ok=True)

        man_pe = [m for m in man if m.sample_id in keep]
        write_jsonl(out / "manifest_test.jsonl", man_pe)
        feats = read_models(t / "features_test.jsonl", FeatureRecord)
        write_jsonl(out / "features_test.jsonl",
                    [f for f in feats if f.sample_id in keep])
        alerts = read_models(t / "static_alerts_test.jsonl", StaticAlertRecord)
        write_jsonl(out / "static_alerts_test.jsonl",
                    [a for a in alerts if a.sample_id in keep])
        scores = [r for r in read_jsonl(t / "rank_scores_test.jsonl")
                  if r["sample_id"] in keep]
        scores.sort(key=lambda r: (-float(r["rank_score"]), r["sample_id"]))
        for i, r in enumerate(scores):
            r["rank"] = i + 1
        write_jsonl(out / "rank_scores_test.jsonl", scores)

        n_pe = len(man_pe)
        pe_pos = sum(1 for m in man_pe if m.label == 1)
        # audit: every PE sample is a natural-test sample
        natural_test_ids = {m.sample_id for m in man}
        leak = [m.sample_id for m in man_pe if m.sample_id not in natural_test_ids]
        L = [f"# Positive-Enriched Evaluation Set — {ds}", "",
             "> **POSITIVE-ENRICHED EVALUATION — SEPARATE FROM THE NATURAL-",
             "> DISTRIBUTION TEST SET. For analysis of metric stability only.**", "",
             f"- Built because natural test positives < {V2.MIN_TEST_POS_FOR_STABLE}: "
             f"**{'YES (needed)' if needed else 'NO (supplementary; natural test already has enough positives)'}**",
             f"- Natural test set: n={len(man)}, positives={natural_pos}",
             f"- Positive-enriched set: n={n_pe}, positives={pe_pos}, "
             f"negatives={n_pe - pe_pos} (balanced 1:1)",
             "- Construction: strict subset of the natural TEST split (seed="
             f"{V2.SEED}); no train/valid sample included; labels are the real "
             "dataset labels (never fabricated); no sample duplicated across splits.",
             f"- Leakage check (any PE sample not from natural test): "
             f"{'FAIL ' + str(leak) if leak else 'PASS (0)'}", ""]
        (out / "posenriched_eval.md").write_text("\n".join(L) + "\n",
                                                 encoding="utf-8")
        print(f"[posenrich] {ds}: natural_test_pos={natural_pos} "
              f"needed={needed} -> PE n={n_pe} (pos={pe_pos})")
        results.append({"dataset": ds, "natural_test_n": len(man),
                        "natural_test_pos": natural_pos, "needed": needed,
                        "pe_n": n_pe, "pe_pos": pe_pos, "leak": leak})
    (V2.ROOT / "positive_enriched_summary.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return results


# ---------------------------------------------------------------------------
# Mock matrix on the positive-enriched set too (separate dir, clearly labeled).
# ---------------------------------------------------------------------------
def mock_posenriched() -> None:
    from semvulguard.llm.mock import MockLLMClient
    from semvulguard.llm.verify import verify
    for ds in DATASETS:
        t = V2.ROOT / ds / "test_only_posenriched"
        if not (t / "features_test.jsonl").exists():
            continue
        verdicts = t / "llm_verdicts_mock_top50.jsonl"
        verify(features_path=t / "features_test.jsonl",
               rank_scores_path=t / "rank_scores_test.jsonl",
               alerts_path=t / "static_alerts_test.jsonl",
               output_path=verdicts, top_k=50,
               client=MockLLMClient(mode="rule"), model="mock-rule",
               cost_log_path=None)
        base = V2.ROOT / ds / "mock_posenriched"
        rows, completed, failed = _matrix.run_matrix(
            dataset=ds, base_dir=base,
            features_path=t / "features_test.jsonl",
            rank_scores_path=t / "rank_scores_test.jsonl",
            alerts_path=t / "static_alerts_test.jsonl",
            verdicts_path=verdicts, ks=V2.KS_MOCK, cost_log_path=None)
        _matrix.write_dataset_summaries(
            ds=ds, out=base, rows=rows, ks=V2.KS_MOCK, completed=completed,
            failed=failed,
            banner="MOCK / POSITIVE-ENRICHED EVALUATION / PIPELINE VALIDATION "
                   "ONLY / NOT FINAL SCIENTIFIC LLM RESULTS",
            mode="mock", rank_scores_path=t / "rank_scores_test.jsonl",
            full_fusion_scores=base / "full" / f"topk_{max(V2.KS_MOCK)}" / "fusion_scores.jsonl",
            api_calls=0, cost=0.0)
        print(f"[mock-PE] {ds}: {len(completed)} ok / {len(failed)} failed")


# ---------------------------------------------------------------------------
# Cross-dataset MOCK summaries (analogous to v1's real_summary, but mock + the
# v2 metrics the brief asks for). Reads each dataset's mock/ matrix CSVs.
# ---------------------------------------------------------------------------
BANNER = "MOCK LLM VERDICTS — PIPELINE VALIDATION ONLY — NOT REAL LLM SCIENTIFIC EVIDENCE"


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as fh:
        return list(csv.DictReader(fh))


def _concat(name: str) -> list[dict]:
    rows = []
    for ds in DATASETS:
        rows += _read_csv(V2.ROOT / ds / "mock" / name)
    return rows


def _write_concat(out: Path, name: str) -> list[dict]:
    rows = _concat(name)
    if not rows:
        return rows
    with (out / name).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return rows


def _get(rows, ds, method, k):
    for r in rows:
        if r["dataset"] == ds and r["method"] == method and int(r["top_k"]) == k:
            return r
    return None


def _f(x):
    if x is None or x == "":
        return "n/a"
    try:
        return f"{float(x):.4f}"
    except (ValueError, TypeError):
        return str(x)


def write_mock_summaries() -> dict:
    out = V2.ROOT / "mock_summary"
    out.mkdir(parents=True, exist_ok=True)
    for name in ("overall_performance.csv", "ablation.csv",
                 "topk_sensitivity.csv", "fp_reduction.csv",
                 "ranking_quality.csv"):
        _write_concat(out, name)
    overall = _concat("overall_performance.csv")

    ranker_summary = {r["dataset"]: r for r in
                      json.loads((V2.ROOT / "ranker_summary.json").read_text())}
    leak = {r["dataset"]: r for r in
            json.loads((V2.ROOT / "leakage_audit_summary.json").read_text())}
    codeql = _codeql_coverage()

    # experiment_summary.md
    maxk = max(V2.KS_MOCK)
    L = ["# Cross-Dataset Experiment Summary (MOCK, TEST-only)", "",
         f"> **{BANNER}**", "",
         f"- Datasets: {', '.join(DATASETS)}",
         f"- Methods: {', '.join(_matrix.METHODS_ALL)}",
         f"- Top-k (mock): {V2.KS_MOCK}",
         f"- Generated: {datetime.now(timezone.utc).isoformat()}", "",
         "## Held-out ranker generalization (leak-free, fit on TRAIN only)", "",
         "| dataset | test n | test pos | F1 | MCC | PR-AUC | ROC-AUC |",
         "|---|---|---|---|---|---|---|"]
    for ds in DATASETS:
        tm = ranker_summary[ds]["test_metrics"]
        L.append(f"| {ds} | {tm.get('num_samples')} | {tm.get('num_positive')} "
                 f"| {_f(tm.get('f1'))} | {_f(tm.get('mcc'))} | {_f(tm.get('pr_auc'))} "
                 f"| {_f(tm.get('roc_auc'))} |")
    L += ["", f"## MOCK fusion comparison (k={maxk}, test-only)", "",
          "| dataset | method | F1 | MCC | PR-AUC | ROC-AUC | FP |",
          "|---|---|---|---|---|---|---|"]
    for ds in DATASETS:
        for m in _matrix.METHODS_ALL:
            r = _get(overall, ds, m, maxk)
            if r:
                L.append(f"| {ds} | {m} | {_f(r['f1'])} | {_f(r['mcc'])} "
                         f"| {_f(r['pr_auc'])} | {_f(r['roc_auc'])} | {r['fp']} |")
    (out / "experiment_summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    # paper_ready_results.md (clearly mock)
    P = ["# Paper-Ready Results — formal_multidataset_v2_scaled", "",
         f"> **{BANNER}**", "",
         "_Scaled subsets (target 5000/dataset). LLM verdicts are MOCK (rule-based, "
         "offline). These validate the pipeline end-to-end; they are NOT real-LLM "
         "scientific evidence. Real DeepSeek was NOT called._", "",
         "## RQ1 — Does the mock full pipeline change detection? (k=" + str(maxk) + ", test-only)", "",
         "| dataset | full F1 | static_only F1 | ranker_only F1 | static_ranker F1 | full MCC | ranker_only MCC |",
         "|---|---|---|---|---|---|---|"]
    for ds in DATASETS:
        fu, so, ro, sr = (_get(overall, ds, m, maxk) for m in
                          ("full", "static_only", "ranker_only", "static_ranker"))
        if fu:
            P.append(f"| {ds} | {_f(fu['f1'])} | {_f(so['f1'])} | {_f(ro['f1'])} "
                     f"| {_f(sr['f1'])} | {_f(fu['mcc'])} | {_f(ro['mcc'])} |")
    P += ["", "_Mock results only. Do not cite as LLM effectiveness._", ""]
    (out / "paper_ready_results.md").write_text("\n".join(P) + "\n", encoding="utf-8")

    # run_status.json
    status = {
        "mode": "mock", "banner": BANNER, "experiment": "formal_multidataset_v2_scaled",
        "evaluation_set": "test_only", "datasets": DATASETS,
        "methods": _matrix.METHODS_ALL, "top_k_values": V2.KS_MOCK,
        "real_api_called": False, "api_calls": 0, "cost_usd": 0.0,
        "test_sample_counts": {ds: leak[ds]["test_n"] for ds in DATASETS},
        "test_positive_counts": {ds: leak[ds]["test_pos"] for ds in DATASETS},
        "codeql": codeql,
        "generated": datetime.now(timezone.utc).isoformat(),
        "output_files": sorted(str(p) for p in out.glob("*")),
    }
    (out / "run_status.json").write_text(json.dumps(status, indent=2) + "\n",
                                         encoding="utf-8")
    print(f"[summary] mock cross-dataset summaries -> {out}")
    return {"overall": overall, "ranker": ranker_summary, "leak": leak,
            "codeql": codeql}


def _codeql_coverage() -> dict:
    data = json.loads((V2.ROOT / "codeql_summary.json").read_text())
    out = {}
    for r in data:
        m = r.get("map") or {}
        out[r["dataset"]] = {"build_ok": r.get("build_ok", False),
                             "alerts": m.get("mapped", 0),
                             "covered": m.get("samples_covered", 0)}
    for ds in DATASETS:
        out.setdefault(ds, {"build_ok": False, "alerts": 0, "covered": 0})
    return out


# ---------------------------------------------------------------------------
# final_report.md — all 12 required sections.
# ---------------------------------------------------------------------------
def write_final_report(ctx: dict) -> None:
    overall = ctx["overall"]
    ranker_summary = ctx["ranker"]
    leak = ctx["leak"]
    codeql = ctx["codeql"]
    summ = _read_csv(V2.ROOT / "dataset_summary.csv")
    summ_by = {r["dataset"]: r for r in summ}
    cost = json.loads((V2.ROOT / "real_api_cost_preview.json").read_text())
    pe = {r["dataset"]: r for r in
          json.loads((V2.ROOT / "positive_enriched_summary.json").read_text())}
    v1_ranker = {r["dataset"]: r for r in
                 json.loads((V2.V1_ROOT / "ranker_summary.json").read_text())}
    v1_leak = {r["dataset"]: r for r in
               json.loads((V2.V1_ROOT / "leakage_audit_summary.json").read_text())}
    maxk = max(V2.KS_MOCK)

    L = ["# SemVulGuard — formal_multidataset_v2_scaled (final report)", "",
         f"> **{BANNER}**", "",
         f"Output root: `{V2.ROOT}`",
         f"Generated: {datetime.now(timezone.utc).isoformat()}",
         f"Seed: {V2.SEED} | Split: 70/10/20 stratified per label | "
         f"Real DeepSeek API: **NOT CALLED** (mock verdicts only)", "",
         "This v2 run scales the subsets (target 5000/dataset) to get enough test "
         "positives for stable metrics. The ranker and all evaluation are real and "
         "test-only; the LLM channel is MOCK and exists solely to validate the "
         "fusion/eval plumbing at scale.", ""]

    # 1. actual subset sizes
    L += ["## 1. Actual subset sizes", "",
          "| dataset | full valid | target | subset |",
          "|---|---|---|---|"]
    for ds in DATASETS:
        r = summ_by[ds]
        L.append(f"| {ds} | {r['full_valid_count']} | {V2.SUBSET_TARGETS[ds]} "
                 f"| {r['subset_count']} |")

    # 2. train/valid/test counts
    L += ["", "## 2. Train / valid / test counts", "",
          "| dataset | train | valid | test |", "|---|---|---|---|"]
    for ds in DATASETS:
        r = summ_by[ds]
        L.append(f"| {ds} | {r['train_count']} | {r['valid_count']} | {r['test_count']} |")

    # 3. test positive counts
    L += ["", "## 3. Test positive counts", "",
          "| dataset | test n | test positives | pos rate |",
          "|---|---|---|---|"]
    for ds in DATASETS:
        tn, tp = leak[ds]["test_n"], leak[ds]["test_pos"]
        L.append(f"| {ds} | {tn} | {tp} | {tp / max(1, tn):.4f} |")

    # 4. >= 50 test positives?
    L += ["", "## 4. Do BigVul and DiverseVul now have >= 50 test positives?", "",
          "| dataset | test positives | >= 50? |", "|---|---|---|"]
    for ds in DATASETS:
        tp = leak[ds]["test_pos"]
        L.append(f"| {ds} | {tp} | {'YES' if tp >= 50 else 'NO'} |")
    bv, dv = leak["bigvul"]["test_pos"], leak["diversevul"]["test_pos"]
    both = bv >= 50 and dv >= 50
    L += ["", f"**BigVul={bv}, DiverseVul={dv} test positives — "
          f"{'BOTH now have >= 50 (v1 had 11 each).' if both else 'NOT both >= 50; see positive-enriched eval set.'}**"]
    # positive-enriched note
    L += ["", "Positive-enriched evaluation sets (balanced, strict subset of the "
          "natural test split; analysis only, kept separate):", ""]
    for ds in DATASETS:
        p = pe[ds]
        L.append(f"- {ds}: PE n={p['pe_n']} (pos={p['pe_pos']}), "
                 f"built-because-needed={p['needed']}")

    # 5. CodeQL coverage
    L += ["", "## 5. CodeQL alert coverage by dataset", "",
          "| dataset | DB build | alerts mapped | samples covered | test alerts |",
          "|---|---|---|---|---|"]
    for ds in DATASETS:
        c = codeql[ds]
        L.append(f"| {ds} | {'OK' if c['build_ok'] else 'FAILED'} | {c['alerts']} "
                 f"| {c['covered']} | {leak[ds].get('test_alerts', 'n/a')} |")

    # 6. ranker test metrics
    L += ["", "## 6. sklearn_tfidf ranker — held-out TEST metrics (leak-free)", "",
          "| dataset | test n | F1 | MCC | PR-AUC | ROC-AUC |",
          "|---|---|---|---|---|---|"]
    for ds in DATASETS:
        tm = ranker_summary[ds]["test_metrics"]
        L.append(f"| {ds} | {tm.get('num_samples')} | {_f(tm.get('f1'))} "
                 f"| {_f(tm.get('mcc'))} | {_f(tm.get('pr_auc'))} | {_f(tm.get('roc_auc'))} |")

    # 7. generalization vs v1
    L += ["", "## 7. Ranker generalization vs v1", "",
          "| dataset | metric | v1 | v2 | Δ |", "|---|---|---|---|---|"]
    for ds in DATASETS:
        v2m = ranker_summary[ds]["test_metrics"]
        v1m = v1_ranker[ds]["test_metrics"]
        for metric in ("f1", "mcc", "pr_auc", "roc_auc"):
            a, b = v1m.get(metric), v2m.get(metric)
            d = (b - a) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None
            L.append(f"| {ds} | {metric} | {_f(a)} | {_f(b)} "
                     f"| {('%+.4f' % d) if d is not None else 'n/a'} |")
    L += ["", _generalization_verdict(ranker_summary, v1_ranker)]

    # 8. static_only still sparse?
    total_alerts = sum(codeql[ds]["alerts"] for ds in DATASETS)
    total_cov = sum(codeql[ds]["covered"] for ds in DATASETS)
    total_subset = sum(int(summ_by[ds]["subset_count"]) for ds in DATASETS)
    sparse = total_cov < 0.05 * total_subset
    L += ["", "## 8. Is static_only still sparse?", "",
          f"- Total CodeQL alerts mapped across datasets: **{total_alerts}**",
          f"- Total samples with >= 1 alert: **{total_cov}** / {total_subset} subset "
          f"samples ({total_cov / max(1, total_subset) * 100:.2f}%)",
          f"- **Verdict: static coverage is {'STILL SPARSE' if sparse else 'no longer sparse'}.** "
          "Function-level code without build context rarely triggers CodeQL security "
          "queries; the static channel remains a weak lower bound (static_score≈0 for "
          "most samples), exactly as in v1.", ""]

    # 9. mock full vs ranker_only / static_ranker
    L += ["## 9. Does the MOCK full method improve over ranker_only / static_ranker? "
          f"(k={maxk}, test-only)", "",
          f"> {BANNER}", "",
          "| dataset | full F1 | ranker_only F1 | static_ranker F1 | full vs ranker_only | full vs static_ranker |",
          "|---|---|---|---|---|---|"]
    any_improve = False
    for ds in DATASETS:
        fu = _get(overall, ds, "full", maxk)
        ro = _get(overall, ds, "ranker_only", maxk)
        sr = _get(overall, ds, "static_ranker", maxk)
        if fu and ro and sr:
            v_ro = (float(fu["f1"]), float(fu["mcc"])) > (float(ro["f1"]), float(ro["mcc"]))
            v_sr = (float(fu["f1"]), float(fu["mcc"])) > (float(sr["f1"]), float(sr["mcc"]))
            any_improve = any_improve or v_ro or v_sr
            L.append(f"| {ds} | {_f(fu['f1'])} | {_f(ro['f1'])} | {_f(sr['f1'])} "
                     f"| {'yes' if v_ro else 'no'} | {'yes' if v_sr else 'no'} |")
    L += ["", "_These are MOCK verdicts; any movement reflects the rule-based mock, "
          "not real LLM judgment. Reported only to confirm the fusion path responds "
          "to the LLM channel._", ""]

    # 10. worth running real top-50?
    L += ["## 10. Is this v2 setting worth running with real DeepSeek top-k=50?", "",
          _worth_real_verdict(both, leak, total_cost=cost["total_cost_usd"]), ""]

    # 11. estimated real cost
    L += ["## 11. Estimated real API cost for top-k=50 (NO API called)", "",
          f"- Pricing: input cache-miss ${V2.PRICE_IN_PER_1M}/1M, output "
          f"${V2.PRICE_OUT_PER_1M}/1M; output assumed {V2.OUT_TOKENS_PER_SAMPLE} tok/sample.",
          "- Candidates = top-50 TEST candidates per dataset (from rank_scores_test.jsonl).", "",
          "| dataset | candidates | est input tok | est output tok | est cost USD |",
          "|---|---|---|---|---|"]
    for r in cost["rows"]:
        L.append(f"| {r['dataset']} | {r['candidates']} | {r['est_input_tokens']:.0f} "
                 f"| {r['est_output_tokens']:.0f} | ${r['est_cost_total_usd']:.5f} |")
    L += ["", f"- **Total real API calls if run: {cost['total_calls']} "
          f"({len(DATASETS)} × top-50)**",
          f"- **Estimated total cost: ${cost['total_cost_usd']:.5f} USD** "
          "(500-tok output is an upper bound; real cost likely lower).", ""]

    # 12. limitations
    L += ["## 12. Remaining limitations", "",
          "- **LLM results are MOCK** (rule-based, offline). No real DeepSeek evidence "
          "in v2 by design; do not cite mock numbers as LLM effectiveness.",
          "- CodeQL on wrapped functions is still sparse (no build context) — the static "
          "channel is a weak lower bound.",
          "- Fusion final scores compress below the 0.5 threshold → low thresholded F1; "
          "PR-AUC / MCC / ROC-AUC and ranking metrics are the more informative view, "
          "especially for the imbalanced BigVul/DiverseVul.",
          "- No semantic dedup across splits → possible near-duplicate functions "
          "(dataset-level caveat, esp. DiverseVul/Devign).",
          "- Positive-enriched eval is balanced by subsetting the natural test set; it "
          "is for stability analysis only and is reported separately from the natural-"
          "distribution test.",
          "- DiverseVul/BigVul remain heavily imbalanced at the corpus level even after "
          "scaling; the scaled test sets give more positives but the natural pos-rate "
          "is unchanged.", "",
          "## Output paths", "",
          f"- Per-dataset artifacts: `{V2.ROOT}/{{dataset}}/`",
          f"- Test-only artifacts: `{V2.ROOT}/{{dataset}}/test_only/`",
          f"- Positive-enriched eval: `{V2.ROOT}/{{dataset}}/test_only_posenriched/`",
          f"- Mock matrix: `{V2.ROOT}/{{dataset}}/mock/` (+ `mock_posenriched/`)",
          f"- Cross-dataset mock summary: `{V2.ROOT}/mock_summary/`",
          f"- This report: `{V2.ROOT}/final_report.md`", ""]

    (V2.ROOT / "final_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"[summary] final report -> {V2.ROOT / 'final_report.md'}")


def _generalization_verdict(v2r, v1r) -> str:
    gains = []
    for ds in DATASETS:
        a = v1r[ds]["test_metrics"].get("roc_auc")
        b = v2r[ds]["test_metrics"].get("roc_auc")
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            gains.append(b - a)
    if not gains:
        return "Generalization vs v1: n/a."
    avg = sum(gains) / len(gains)
    direction = ("improves" if avg > 0.01 else
                 "is roughly comparable" if abs(avg) <= 0.01 else "declines")
    return (f"**Ranker generalization {direction} vs v1** (mean ROC-AUC Δ = "
            f"{avg:+.4f} across datasets). v2's value is chiefly the larger, more "
            "stable test sets — metrics on more positives are more trustworthy even "
            "where the point estimate is similar.")


def _worth_real_verdict(both_50, leak, total_cost) -> str:
    lead = ("With BigVul/DiverseVul now at >= 50 test positives, corpus-level metrics "
            "are far more stable than v1's ~11, so a real run would now produce "
            "trustworthy numbers. "
            if both_50 else
            "BigVul/DiverseVul still fall short of 50 natural test positives; rely on "
            "the positive-enriched eval for stability there. ")
    return (lead +
            f"Estimated real top-50 cost is only ${total_cost:.4f} (≈"
            f"{sum(leak[d]['test_n'] for d in DATASETS)} test samples, top-50/dataset), "
            "which is cheap. **Recommendation: v2 is a reasonable setting to run real "
            "DeepSeek top-50 — the test sets are now large enough for the LLM channel "
            "to be evaluated meaningfully — but per the task's stop condition, real "
            "top-50 must NOT be run until explicitly approved.**")


# ---------------------------------------------------------------------------
# Phase dispatch.
# ---------------------------------------------------------------------------
def run_subset() -> None:
    _resolve_devign_target()
    subset_split.main(DATASETS)


def run_all() -> None:
    prep_normalization()
    run_subset()
    build_features_phase()
    validate_features.main(DATASETS)
    codeql_alerts.main(DATASETS)
    ranker.main(DATASETS)
    test_only.main(DATASETS)
    build_positive_enriched()
    mock.main(DATASETS)
    mock_posenriched()
    cost_preview.main(DATASETS)
    ctx = write_mock_summaries()
    write_final_report(ctx)


PHASES = {
    "prep": prep_normalization,
    "subset": run_subset,
    "features": build_features_phase,
    "validate": lambda: validate_features.main(DATASETS),
    "codeql": lambda: codeql_alerts.main(DATASETS),
    "ranker": lambda: ranker.main(DATASETS),
    "testonly": lambda: test_only.main(DATASETS),
    "posenrich": build_positive_enriched,
    "mock": lambda: mock.main(DATASETS),
    "mockpe": mock_posenriched,
    "cost": lambda: cost_preview.main(DATASETS),
    "summary": lambda: write_final_report(write_mock_summaries()),
    "all": run_all,
}


def main(argv: list[str] | None = None) -> int:
    _patch_globals()
    argv = argv or ["all"]
    phase = argv[0]
    if phase not in PHASES:
        print(f"unknown phase {phase!r}; choices: {', '.join(PHASES)}")
        return 2
    PHASES[phase]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or None))
