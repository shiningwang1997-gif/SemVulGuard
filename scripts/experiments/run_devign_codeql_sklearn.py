"""Rerun the Devign experiment matrix with the sklearn_tfidf ranker + CodeQL.

Same orchestration as scripts/experiments/run_devign_codeql.py, but the ranker
channel is fed by the new sklearn_tfidf rank scores
(artifacts/experiments/devign_sklearn_ranker/rank_scores_sklearn.jsonl) instead
of the fallback hashing ranker. Reuses the existing REAL DeepSeek verdicts from
the max_k=50 run (NO new API call) and the real CodeQL static alerts.

Writes the M1-M5 x top-k{0,10,30,50} matrix and the five summary CSVs / markdown
summaries / run_status.json under artifacts/experiments/devign_codeql_sklearn/,
plus a THREE-WAY comparison vs:
  (1) original (static_score=0, fallback ranker)  -> real_summary/
  (2) CodeQL + fallback ranker                     -> devign_codeql/
  (3) CodeQL + sklearn_tfidf ranker  (this run)

Nothing here calls DeepSeek; everything is deterministic.
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
SK = EXP / "devign_sklearn_ranker"
OUT = EXP / "devign_codeql_sklearn"
PREV_ORIG = EXP / "real_summary"        # original: static=0, fallback ranker
PREV_CODEQL = EXP / "devign_codeql"     # CodeQL + fallback ranker

KS = [0, 10, 30, 50]
MAX_K = 50
MODEL = "deepseek-v4-flash"

FEATURES = DEVIGN / "features.jsonl"
ALERTS = DEVIGN / "static_alerts_codeql.jsonl"
RANK = SK / "rank_scores_sklearn.jsonl"
VERDICTS = DEVIGN / "real" / f"llm_verdicts_real_maxk{MAX_K}.jsonl"
COST_LOG = DEVIGN / "real" / f"real_llm_cost_log_maxk{MAX_K}.jsonl"


def _cost_total(path: Path) -> tuple[float, int]:
    if not path.exists():
        return 0.0, 0
    rows = [json.loads(line) for line in path.open()]
    return sum(float(r.get("api_cost_usd", 0.0)) for r in rows), len(rows)


def _alert_stats() -> dict:
    if not ALERTS.exists():
        return {"n_alerts": 0, "n_samples": 0, "qids": {}, "cwes": {}}
    rows = [json.loads(line) for line in ALERTS.open()]
    from collections import Counter
    qids = Counter(r["query_id"] for r in rows)
    cwes = Counter(c for r in rows for c in r.get("cwe", []))
    return {
        "n_alerts": len(rows),
        "n_samples": len({r["sample_id"] for r in rows}),
        "qids": dict(qids),
        "cwes": dict(cwes),
    }


def _load_overall(summary_dir: Path) -> dict[tuple[str, int], dict]:
    p = summary_dir / "overall_performance.csv"
    out: dict[tuple[str, int], dict] = {}
    if not p.exists():
        return out
    with p.open() as fh:
        for r in csv.DictReader(fh):
            out[(r["method"], int(r["top_k"]))] = r
    return out


def _load_ranking_quality(summary_dir: Path) -> dict[str, dict]:
    p = summary_dir / "ranking_quality.csv"
    out: dict[str, dict] = {}
    if not p.exists():
        return out
    with p.open() as fh:
        for r in csv.DictReader(fh):
            out[r["score_type"]] = r
    return out


def _load_split_metrics() -> dict[str, dict]:
    """Load the ranker's held-out train/valid/test metric JSONs."""
    out: dict[str, dict] = {}
    for name in ("train", "valid", "test"):
        p = SK / f"{name}_metrics.json"
        if p.exists():
            out[name] = json.loads(p.read_text())
    return out


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


def main() -> int:
    start = datetime.now(timezone.utc).isoformat()
    OUT.mkdir(parents=True, exist_ok=True)
    base = OUT / "cells"

    if not RANK.exists():
        raise SystemExit(
            f"missing sklearn rank scores: {RANK}\n"
            "run train_sklearn + infer_sklearn first."
        )

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
            except Exception as exc:  # noqa: BLE001
                failed.append({"cell": tag, "error": f"{type(exc).__name__}: {exc}"})
                print(f"FAILED {tag}: {exc}")

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
    prev_orig = _load_overall(PREV_ORIG)
    prev_codeql = _load_overall(PREV_CODEQL)
    rq_orig = _load_ranking_quality(PREV_ORIG)
    rq_codeql = _load_ranking_quality(PREV_CODEQL)
    rq_now = _load_ranking_quality(OUT)
    split_metrics = _load_split_metrics()

    _write_summary(rows, prev_orig, prev_codeql, stats, completed, failed,
                   start, end, total_calls, total_cost,
                   rq_orig, rq_codeql, rq_now, split_metrics)
    _write_paper_ready(rows, prev_orig, prev_codeql, stats, rq_codeql, rq_now,
                       split_metrics)
    _write_run_status(rows, stats, completed, failed, start, end,
                      total_calls, total_cost)

    print(f"\nDEVIGN+CodeQL+sklearn pipeline done: {len(completed)} cells ok, {len(failed)} failed")
    print(f"ranker channel: sklearn_tfidf ({RANK})")
    print(f"reused REAL verdicts: {total_calls} calls, ${total_cost:.6f} (NO new API)")
    print(f"summaries -> {OUT}")
    return 0


def _cmp(a, b, name_a, name_b, k):
    if not a or not b:
        return f"- {name_a} vs {name_b}: n/a"
    better = (a["f1"], a["mcc"]) > (b["f1"], b["mcc"])
    return (f"- {name_a} vs {name_b} (k={k}): F1 {_f(a['f1'])} vs {_f(b['f1'])}, "
            f"MCC {_f(a['mcc'])} vs {_f(b['mcc'])} -> "
            f"{'IMPROVES' if better else 'no improvement'}")


def _three_way_row(method, k, now, orig, codeql):
    o = orig.get((method, k))
    c = codeql.get((method, k))
    return (
        f"| {method} | {k} "
        f"| {_f(o['f1']) if o else 'n/a'} | {_f(c['f1']) if c else 'n/a'} | {_f(now['f1'])} "
        f"| {_f(o['mcc']) if o else 'n/a'} | {_f(c['mcc']) if c else 'n/a'} | {_f(now['mcc'])} "
        f"| {_f(o['pr_auc']) if o else 'n/a'} | {_f(c['pr_auc']) if c else 'n/a'} | {_f(now['pr_auc'])} |"
    )


def _write_summary(rows, orig, codeql, stats, completed, failed, start, end,
                   calls, cost, rq_orig, rq_codeql, rq_now, split_metrics):
    maxk = max(KS)
    so, ro, sr, fu, sl = (_get(rows, m, maxk) for m in
                          ("static_only", "ranker_only", "static_ranker", "full", "static_llm"))
    bf, bm = _best(rows, "f1"), _best(rows, "mcc")

    # fallback-ranker reference (CodeQL + fallback) for ranker_only
    ro_fb = codeql.get(("ranker_only", maxk))
    ro_fb_f1 = float(ro_fb["f1"]) if ro_fb else None
    ro_fb_mcc = float(ro_fb["mcc"]) if ro_fb else None
    ro_fb_pr = float(ro_fb["pr_auc"]) if ro_fb else None

    test_m = split_metrics.get("test", {})
    valid_m = split_metrics.get("valid", {})
    train_m = split_metrics.get("train", {})

    L = [
        "# Experiment Summary — Devign + CodeQL + sklearn_tfidf ranker", "",
        "## ⚠ Read first: corpus metrics include training samples", "",
        "Inference scores **all 1000 samples**, of which **700 were the ranker's training "
        "split**. The corpus-level `overall_performance.csv` numbers below are therefore "
        "**in-sample (optimistic)** for the ranker channel and must NOT be read as "
        "generalization. The honest, leak-free signal is the held-out **test** split:", "",
        f"- ranker held-out **test**: F1={_f(test_m.get('f1'))} MCC={_f(test_m.get('mcc'))} "
        f"PR-AUC={_f(test_m.get('pr_auc'))} ROC-AUC={_f(test_m.get('roc_auc'))} "
        f"(n={test_m.get('num_samples')})",
        f"- ranker held-out **valid**: F1={_f(valid_m.get('f1'))} MCC={_f(valid_m.get('mcc'))} "
        f"PR-AUC={_f(valid_m.get('pr_auc'))} (n={valid_m.get('num_samples')})",
        f"- ranker **train** (in-sample, for ref): F1={_f(train_m.get('f1'))} "
        f"PR-AUC={_f(train_m.get('pr_auc'))} (n={train_m.get('num_samples')})",
        "",
        "**Interpretation:** on this 1000-sample subset the TF-IDF+features ranker "
        "memorizes the training split (train PR-AUC≈0.96) but does **not** generalize "
        "(test PR-AUC≈0.50, ≈random). The corpus-wide F1/PR-AUC gains shown later are an "
        "artifact of that contamination, not evidence of a better ranker on unseen code.", "",
        "## Run configuration", "",
        "- Dataset: devign (1000-sample subset)",
        "- **Ranker backend: sklearn_tfidf** (TF-IDF + code metrics + CodeQL alert features"
        " + LogisticRegression, class_weight=balanced, seed=42)",
        "- Static analyzer: CodeQL 2.25.6 (cpp-security-extended.qls), function-wrapped",
        f"- CodeQL alerts: **{stats['n_alerts']}** over **{stats['n_samples']}** samples",
        f"- Verdict source: **REAL DeepSeek** (`{MODEL}`) — REUSED from max_k=50 run, **no new API call**",
        f"- Methods: {', '.join(METHODS)}",
        f"- Top-k: {KS}",
        f"- Reused API calls: {calls} | reused cost: ${cost:.6f}",
        f"- Run start: {start} | end: {end}",
        f"- Cells completed: {len(completed)} | failed: {len(failed)}", "",
        "## Headline results (corpus, in-sample — see warning)", "",
        f"- Best F1: **{bf['method']}** @k={bf['top_k']} (F1={_f(bf['f1'])}, MCC={_f(bf['mcc'])})",
        f"- Best MCC: **{bm['method']}** @k={bm['top_k']} (MCC={_f(bm['mcc'])})", "",
        "## Does sklearn_tfidf improve over the fallback ranker? (ranker_only, k=50)", "",
        "_Corpus-wide (in-sample, optimistic — see warning at top):_",
        f"- fallback ranker: F1={_f(ro_fb_f1)} MCC={_f(ro_fb_mcc)} PR-AUC={_f(ro_fb_pr)}",
        f"- sklearn_tfidf : F1={_f(ro['f1'])} MCC={_f(ro['mcc'])} PR-AUC={_f(ro['pr_auc'])}",
    ]
    if ro_fb_pr is not None:
        dpr = ro["pr_auc"] - ro_fb_pr
        df1 = ro["f1"] - ro_fb_f1
        dmcc = ro["mcc"] - ro_fb_mcc
        L.append(
            f"- corpus ΔPR-AUC={dpr:+.4f}, ΔF1={df1:+.4f}, ΔMCC={dmcc:+.4f} "
            f"(inflated by train-set memorization; not a generalization claim)."
        )
    tpr = test_m.get("pr_auc")
    if tpr is not None and ro_fb_pr is not None:
        gen = "IMPROVES" if tpr > ro_fb_pr else ("MATCHES" if abs(tpr - ro_fb_pr) < 1e-9 else "DOES NOT IMPROVE")
        L.append(
            f"- **Held-out test PR-AUC={_f(tpr)} vs fallback corpus PR-AUC={_f(ro_fb_pr)} "
            f"-> sklearn_tfidf {gen} on unseen data.** On this subset the learned ranker "
            f"does not beat the fallback out-of-sample."
        )
    L.append("")

    # ranking quality (recall@k) comparison
    L += ["## Ranking quality: Recall@k / MRR / nDCG (rank_score)", "",
          "| version | R@10 | R@30 | R@50 | MRR | nDCG@50 |",
          "|---|---|---|---|---|---|"]
    for label, rq in (("orig fallback", rq_orig), ("CodeQL fallback", rq_codeql),
                      ("CodeQL+sklearn", rq_now)):
        r = rq.get("rank_score")
        if r:
            L.append(f"| {label} | {_f(r['recall_at_10'])} | {_f(r['recall_at_30'])} "
                     f"| {_f(r['recall_at_50'])} | {_f(r['mrr'])} | {_f(r['ndcg_at_50'])} |")
    L.append("")

    L += ["## Ablation comparisons (k=50)", "",
          _cmp(sr, ro, "static_ranker", "ranker_only", maxk),
          _cmp(fu, sr, "full", "static_ranker", maxk),
          _cmp(fu, ro, "full", "ranker_only", maxk),
          _cmp(sl, so, "static_llm", "static_only", maxk)]
    if sr and fu:
        L.append(f"- FP reduction static_ranker→full (k={maxk}): {sr['fp']} → {fu['fp']} (Δ={sr['fp']-fu['fp']})")
    if so and sl:
        L.append(f"- FP reduction static_only→static_llm (k={maxk}): {so['fp']} → {sl['fp']} (Δ={so['fp']-sl['fp']})")
    L.append("")

    L += ["## PR-AUC vs top-k (LLM methods)", ""]
    for m in ("static_llm", "full"):
        seg = [f"{k}:{_f(_get(rows, m, k)['pr_auc'])}" for k in KS if _get(rows, m, k)]
        L.append(f"- {m}: " + "  ".join(seg))
    L.append("")

    # three-way comparison table
    L += ["## Three-way comparison (orig / CodeQL-fallback / CodeQL-sklearn)", "",
          "F1, MCC, PR-AUC per method/top-k. 'orig'=static_score=0 + fallback ranker; "
          "'CodeQL'=CodeQL + fallback ranker; 'sklearn'=CodeQL + sklearn_tfidf.", "",
          "| method | k | F1 orig | F1 CodeQL | F1 sklearn | MCC orig | MCC CodeQL | MCC sklearn "
          "| PR-AUC orig | PR-AUC CodeQL | PR-AUC sklearn |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in METHODS:
        for k in KS:
            now = _get(rows, m, k)
            if now:
                L.append(_three_way_row(m, k, now, orig, codeql))
    L.append("")

    L += ["## Suitable as preliminary paper-level evidence?", "",
          "- **Pipeline / engineering: YES.** A real learned Code-Representation ranker "
          "(sklearn_tfidf) is now wired end-to-end, deterministic, tested, and fuses with "
          "CodeQL + reused LLM verdicts without any new API calls.",
          "- **Ranker effectiveness claim: NOT YET.** Held-out test PR-AUC≈"
          f"{_f(test_m.get('pr_auc'))} (≈random) shows the TF-IDF model does not generalize on "
          "this 1000-sample subset; the corpus-level gains are memorization. Do not report the "
          "in-sample F1/PR-AUC as a result.",
          "- **To make it paper-ready:** evaluate the ranker strictly on the held-out split "
          "(or report cross-validated metrics), scale beyond 1000 samples, and increase CodeQL "
          "coverage. Treat current numbers as a wiring/feasibility milestone only.", "",
          "## Limitations", "",
          "- CodeQL covers only "
          f"{stats['n_samples']}/1000 samples (function-level wrapping, no build context); "
          "static channel is a sparse lower bound.",
          "- Real LLM verification covers only the top-50 candidates (reused verdicts).",
          "- No CWE/line ground truth in Devign -> localization metrics unavailable.",
          "- 1000-sample subset; results are PRELIMINARY.", ""]
    if failed:
        L += ["## Failed cells", ""] + [f"- {fc['cell']}: {fc['error']}" for fc in failed] + [""]
    (OUT / "experiment_summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def _write_paper_ready(rows, orig, codeql, stats, rq_codeql, rq_now, split_metrics):
    maxk = max(KS)
    so, ro, sr, fu, sl = (_get(rows, m, maxk) for m in
                          ("static_only", "ranker_only", "static_ranker", "full", "static_llm"))
    ro_fb = codeql.get(("ranker_only", maxk))
    test_m = split_metrics.get("test", {})
    valid_m = split_metrics.get("valid", {})
    train_m = split_metrics.get("train", {})

    P = ["# Paper-Ready Results — Devign + CodeQL + sklearn_tfidf ranker (preliminary)", "",
         f"_TF-IDF + code/static features LogisticRegression ranker, fused with CodeQL "
         f"({stats['n_alerts']} alerts over {stats['n_samples']}/1000 samples) and REAL DeepSeek "
         f"verdicts (reused, no new API). 1000-sample Devign subset. PRELIMINARY._", "",
         "> **Caveat:** corpus-level numbers below score all 1000 samples, including the 700 "
         "training samples — they are in-sample. The honest ranker quality is the held-out split.",
         "",
         "### RQ0 Held-out ranker generalization (leak-free)", "",
         f"- test : F1={_f(test_m.get('f1'))} MCC={_f(test_m.get('mcc'))} "
         f"PR-AUC={_f(test_m.get('pr_auc'))} ROC-AUC={_f(test_m.get('roc_auc'))} "
         f"(n={test_m.get('num_samples')})",
         f"- valid: F1={_f(valid_m.get('f1'))} MCC={_f(valid_m.get('mcc'))} "
         f"PR-AUC={_f(valid_m.get('pr_auc'))} (n={valid_m.get('num_samples')})",
         f"- train: PR-AUC={_f(train_m.get('pr_auc'))} (in-sample, overfit reference)",
         "- Takeaway: test PR-AUC≈0.50 ⇒ no generalization on this subset; treat as feasibility, "
         "not an effectiveness result.", "",
         "### RQ1 Overall Performance (k=50, corpus/in-sample)", ""]
    if fu:
        P.append(f"- full: P={_f(fu['precision'])} R={_f(fu['recall'])} F1={_f(fu['f1'])} "
                 f"MCC={_f(fu['mcc'])} PR-AUC={_f(fu['pr_auc'])} ROC-AUC={_f(fu['roc_auc'])}")
    if ro:
        P.append(f"- ranker_only (sklearn_tfidf): F1={_f(ro['f1'])} MCC={_f(ro['mcc'])} "
                 f"PR-AUC={_f(ro['pr_auc'])}")
    if ro_fb:
        P.append(f"- ranker_only (fallback, for ref): F1={_f(ro_fb['f1'])} MCC={_f(ro_fb['mcc'])} "
                 f"PR-AUC={_f(ro_fb['pr_auc'])}")
    if so:
        P.append(f"- static_only: F1={_f(so['f1'])} MCC={_f(so['mcc'])} PR-AUC={_f(so['pr_auc'])}")

    P += ["", "### RQ2 Ranking Quality (rank_score Recall@k)", ""]
    rc, rn = rq_codeql.get("rank_score"), rq_now.get("rank_score")
    if rc and rn:
        P.append(f"- fallback : R@10={_f(rc['recall_at_10'])} R@30={_f(rc['recall_at_30'])} "
                 f"R@50={_f(rc['recall_at_50'])} MRR={_f(rc['mrr'])} nDCG@50={_f(rc['ndcg_at_50'])}")
        P.append(f"- sklearn  : R@10={_f(rn['recall_at_10'])} R@30={_f(rn['recall_at_30'])} "
                 f"R@50={_f(rn['recall_at_50'])} MRR={_f(rn['mrr'])} nDCG@50={_f(rn['ndcg_at_50'])}")

    P += ["", "### RQ3 False-Positive Reduction (k=50)", ""]
    if sr and fu:
        P.append(f"- static_ranker FP={sr['fp']} → full FP={fu['fp']} (Δ={sr['fp']-fu['fp']})")
    if so and sl:
        P.append(f"- static_only FP={so['fp']} → static_llm FP={sl['fp']} (Δ={so['fp']-sl['fp']})")

    P += ["", "### RQ4 Top-k Cost-Performance (full)", ""]
    for k in KS:
        r = _get(rows, "full", k)
        if r:
            P.append(f"- full @k={k}: F1={_f(r['f1'])} MCC={_f(r['mcc'])} PR-AUC={_f(r['pr_auc'])} "
                     f"LLM-verified={r['llm_verified_count']} cost=${r['total_cost_usd']:.6f}")

    P += ["", "### Takeaway", "",
          "- The sklearn_tfidf ranker is a real learned Code-Representation channel (TF-IDF + "
          "static/code features), replacing the degenerate hashing fallback — engineering milestone.",
          "- On held-out data it does **not** yet beat the fallback (test PR-AUC≈0.50); the large "
          "corpus-level gains are train-set memorization and must not be reported as effectiveness.",
          "- Next steps: held-out-only evaluation, larger corpus, denser CodeQL coverage before "
          "any effectiveness claim.", ""]
    (OUT / "paper_ready_results.md").write_text("\n".join(P) + "\n", encoding="utf-8")


def _write_run_status(rows, stats, completed, failed, start, end, calls, cost):
    status = {
        "mode": "real_codeql_sklearn",
        "run_start_time": start, "run_end_time": end,
        "dataset": "devign", "methods": list(METHODS), "top_k_values": KS,
        "ranker_backend": "sklearn_tfidf",
        "ranker_model": "logistic_regression",
        "ranker_rank_scores_path": str(RANK),
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
        "output_files": sorted(str(p) for p in OUT.glob("*")),
    }
    (OUT / "run_status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
