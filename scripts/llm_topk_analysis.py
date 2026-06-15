#!/usr/bin/env python3
"""Top-k candidate verification analysis for real DeepSeek top-50 verdicts.

Evaluates the LLM ONLY within the candidates it actually verified (rank top-50),
for k in {10, 30, 50}. No API calls, no fusion, no modification of old results.
"""
import json
import math
import os
import csv

BASE = "artifacts/experiments/formal_multidataset_v2_scaled"
DATASETS = ["devign", "bigvul", "diversevul"]
KS = [10, 30, 50]
SETTINGS = ["uncertain_as_negative", "uncertain_excluded"]

CASE_FIELDS = [
    "sample_id", "rank", "rank_score", "true_label", "llm_verdict",
    "confidence", "predicted_cwe", "vulnerable_lines", "evidence", "patch_hint",
]

METRIC_COLUMNS = [
    "dataset", "k", "uncertain_setting",
    "candidate_count", "positives_in_topk",
    "vulnerable_verdict_count", "benign_verdict_count", "uncertain_count",
    "uncertain_rate",
    "precision", "recall", "f1", "accuracy", "mcc",
    "tp", "fp", "tn", "fn",
    "vulnerable_verdict_precision", "benign_verdict_precision",
    "ranker_topk_precision", "llm_filtered_precision",
    "precision_gain_over_ranker_topk",
]


def read_jsonl(path):
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def safe_div(n, d):
    return n / d if d else 0.0


def mcc(tp, fp, tn, fn):
    denom = (tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)
    if denom == 0:
        return None
    return (tp * tn - fp * fn) / math.sqrt(denom)


def load_dataset(ds):
    base = os.path.join(BASE, ds, "test_only")
    manifest = {o["sample_id"]: o for o in read_jsonl(os.path.join(base, "manifest_test.jsonl"))}
    ranks = {o["sample_id"]: o for o in read_jsonl(os.path.join(base, "rank_scores_test.jsonl"))}
    verdicts = read_jsonl(os.path.join(base, "llm_verdicts_real_top50.jsonl"))

    rows = []
    for v in verdicts:
        sid = v["sample_id"]
        m = manifest[sid]
        r = ranks[sid]
        rows.append({
            "sample_id": sid,
            "rank": r["rank"],
            "rank_score": r["rank_score"],
            "true_label": int(m["label"]),
            "llm_verdict": v.get("verdict", ""),
            "confidence": v.get("confidence", None),
            "predicted_cwe": v.get("predicted_cwe", ""),
            "vulnerable_lines": v.get("vulnerable_lines", []),
            "evidence": v.get("evidence", []),
            "patch_hint": v.get("patch_hint", ""),
        })
    rows.sort(key=lambda x: x["rank"])
    return rows


def compute_metrics(rows, k, setting):
    """rows: full verified list sorted by rank. Compute metrics for top-k."""
    topk = [r for r in rows if r["rank"] <= k]

    vulnerable = [r for r in topk if r["llm_verdict"] == "vulnerable"]
    benign = [r for r in topk if r["llm_verdict"] == "benign"]
    uncertain = [r for r in topk if r["llm_verdict"] == "uncertain"]

    vulnerable_verdict_count = len(vulnerable)
    benign_verdict_count = len(benign)
    uncertain_count = len(uncertain)

    positives_in_topk = sum(1 for r in topk if r["true_label"] == 1)
    uncertain_rate = safe_div(uncertain_count, len(topk))

    # Build the evaluation candidate set + predictions
    if setting == "uncertain_as_negative":
        candidates = topk
        def pred(r):
            return 1 if r["llm_verdict"] == "vulnerable" else 0
    else:  # uncertain_excluded
        candidates = [r for r in topk if r["llm_verdict"] != "uncertain"]
        def pred(r):
            return 1 if r["llm_verdict"] == "vulnerable" else 0

    tp = fp = tn = fn = 0
    for r in candidates:
        p = pred(r)
        t = r["true_label"]
        if p == 1 and t == 1:
            tp += 1
        elif p == 1 and t == 0:
            fp += 1
        elif p == 0 and t == 0:
            tn += 1
        else:
            fn += 1

    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    accuracy = safe_div(tp + tn, tp + fp + tn + fn)
    m = mcc(tp, fp, tn, fn)

    # Verdict-level precisions (within top-k, independent of exclusion setting)
    vuln_true = sum(1 for r in vulnerable if r["true_label"] == 1)
    benign_true = sum(1 for r in benign if r["true_label"] == 0)
    vulnerable_verdict_precision = safe_div(vuln_true, vulnerable_verdict_count)
    benign_verdict_precision = safe_div(benign_true, benign_verdict_count)

    # Ranker baseline vs LLM filtering (over full top-k)
    ranker_topk_precision = safe_div(positives_in_topk, len(topk))
    llm_filtered_precision = vulnerable_verdict_precision
    precision_gain = llm_filtered_precision - ranker_topk_precision

    return {
        "k": k,
        "uncertain_setting": setting,
        "candidate_count": len(candidates),
        "positives_in_topk": positives_in_topk,
        "vulnerable_verdict_count": vulnerable_verdict_count,
        "benign_verdict_count": benign_verdict_count,
        "uncertain_count": uncertain_count,
        "uncertain_rate": round(uncertain_rate, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "mcc": round(m, 4) if m is not None else "",
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "vulnerable_verdict_precision": round(vulnerable_verdict_precision, 4),
        "benign_verdict_precision": round(benign_verdict_precision, 4),
        "ranker_topk_precision": round(ranker_topk_precision, 4),
        "llm_filtered_precision": round(llm_filtered_precision, 4),
        "precision_gain_over_ranker_topk": round(precision_gain, 4),
    }


def write_case_file(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps({k: r[k] for k in CASE_FIELDS}, ensure_ascii=False) + "\n")


def write_metrics_csv(path, metric_rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=METRIC_COLUMNS)
        w.writeheader()
        for row in metric_rows:
            w.writerow(row)


def fmt_pct(x):
    try:
        return f"{float(x)*100:.1f}%"
    except (ValueError, TypeError):
        return str(x)


def write_dataset_md(path, ds, metric_rows, rows):
    lines = []
    lines.append(f"# LLM Top-k Verification Analysis — {ds}\n")
    lines.append("Real DeepSeek top-50 verdicts evaluated **only within the candidates the LLM actually verified** "
                 "(the ranker's top-50). This is a candidate-verification analysis, not whole-corpus classification.\n")
    n = len(rows)
    pos = sum(1 for r in rows if r["true_label"] == 1)
    lines.append(f"- Verified candidates: **{n}** (ranker top-50)")
    lines.append(f"- Ground-truth positives among the 50: **{pos}** ({fmt_pct(pos/n)})\n")

    for setting in SETTINGS:
        lines.append(f"## Setting: `{setting}`\n")
        lines.append("| k | cand | pos@k | vuln | benign | unc | unc_rate | P | R | F1 | Acc | MCC | TP | FP | TN | FN |")
        lines.append("|---|------|-------|------|--------|-----|----------|---|---|----|----|----|----|----|----|----|")
        for row in metric_rows:
            if row["uncertain_setting"] != setting:
                continue
            lines.append("| {k} | {candidate_count} | {positives_in_topk} | {vulnerable_verdict_count} | "
                         "{benign_verdict_count} | {uncertain_count} | {ur} | {p} | {r} | {f1} | {acc} | {mcc} | "
                         "{tp} | {fp} | {tn} | {fn} |".format(
                             k=row["k"], candidate_count=row["candidate_count"],
                             positives_in_topk=row["positives_in_topk"],
                             vulnerable_verdict_count=row["vulnerable_verdict_count"],
                             benign_verdict_count=row["benign_verdict_count"],
                             uncertain_count=row["uncertain_count"],
                             ur=fmt_pct(row["uncertain_rate"]),
                             p=fmt_pct(row["precision"]), r=fmt_pct(row["recall"]),
                             f1=fmt_pct(row["f1"]), acc=fmt_pct(row["accuracy"]),
                             mcc=row["mcc"], tp=row["tp"], fp=row["fp"], tn=row["tn"], fn=row["fn"]))
        lines.append("")

    lines.append("## Ranker vs LLM filtering (false-positive filtering view)\n")
    lines.append("`ranker_topk_precision` = true-positive rate in the ranker's top-k *before* the LLM. "
                 "`llm_filtered_precision` = true-positive rate among the candidates the LLM keeps as `vulnerable`. "
                 "(Independent of uncertain handling — uses `uncertain_as_negative` row.)\n")
    lines.append("| k | ranker_topk_precision | llm_filtered_precision | gain | vuln_verdict_prec | benign_verdict_prec |")
    lines.append("|---|-----------------------|------------------------|------|-------------------|---------------------|")
    for row in metric_rows:
        if row["uncertain_setting"] != "uncertain_as_negative":
            continue
        lines.append("| {k} | {rp} | {lp} | {g} | {vp} | {bp} |".format(
            k=row["k"], rp=fmt_pct(row["ranker_topk_precision"]),
            lp=fmt_pct(row["llm_filtered_precision"]),
            g=("+" if row["precision_gain_over_ranker_topk"] >= 0 else "") + fmt_pct(row["precision_gain_over_ranker_topk"]),
            vp=fmt_pct(row["vulnerable_verdict_precision"]),
            bp=fmt_pct(row["benign_verdict_precision"])))
    lines.append("")

    with open(path, "w") as f:
        f.write("\n".join(lines))


def main():
    all_metric_rows = []
    per_ds = {}

    for ds in DATASETS:
        rows = load_dataset(ds)
        out_dir = os.path.join(BASE, ds, "llm_topk_analysis")
        os.makedirs(out_dir, exist_ok=True)

        metric_rows = []
        for k in KS:
            for setting in SETTINGS:
                m = compute_metrics(rows, k, setting)
                m_full = {"dataset": ds, **m}
                metric_rows.append(m_full)
                all_metric_rows.append(m_full)

        write_metrics_csv(os.path.join(out_dir, "llm_topk_metrics.csv"), metric_rows)
        write_case_file(os.path.join(out_dir, "llm_top50_cases.jsonl"), rows)
        write_dataset_md(os.path.join(out_dir, "llm_topk_analysis.md"), ds, metric_rows, rows)
        per_ds[ds] = (rows, metric_rows)
        print(f"[{ds}] wrote {out_dir}")

    # Cross-dataset summary
    sum_dir = os.path.join(BASE, "llm_topk_summary")
    os.makedirs(sum_dir, exist_ok=True)
    write_metrics_csv(os.path.join(sum_dir, "llm_topk_metrics_all.csv"), all_metric_rows)
    write_summary_md(os.path.join(sum_dir, "llm_topk_summary.md"), per_ds, all_metric_rows)
    print(f"[summary] wrote {sum_dir}")


def write_summary_md(path, per_ds, all_metric_rows):
    def row_for(ds, k, setting):
        for r in all_metric_rows:
            if r["dataset"] == ds and r["k"] == k and r["uncertain_setting"] == setting:
                return r
        return None

    lines = []
    lines.append("# Cross-Dataset LLM Top-k Verification Summary\n")
    lines.append("**Scope.** Real DeepSeek (deepseek) was run only on each ranker's **top-50** test candidates "
                 "(50 of 1000 test samples per dataset). All metrics below are computed *inside that verified "
                 "candidate set*. This is deliberately **not** a whole-corpus classifier evaluation — the LLM never "
                 "saw the other 950 samples, so corpus-level F1 cannot credit it for them.\n")

    # Headline table: k=50, uncertain_as_negative
    lines.append("## Headline (k=50, uncertain treated as negative)\n")
    lines.append("| dataset | pos@50 | ranker_topk_prec | llm_filtered_prec | gain | vuln_verdict_prec | benign_verdict_prec | uncertain_rate | F1 | MCC |")
    lines.append("|---------|--------|------------------|-------------------|------|-------------------|---------------------|----------------|----|----|")
    for ds in DATASETS:
        r = row_for(ds, 50, "uncertain_as_negative")
        lines.append("| {ds} | {pos}/50 | {rp} | {lp} | {g} | {vp} | {bp} | {ur} | {f1} | {mcc} |".format(
            ds=ds, pos=r["positives_in_topk"],
            rp=fmt_pct(r["ranker_topk_precision"]), lp=fmt_pct(r["llm_filtered_precision"]),
            g=("+" if r["precision_gain_over_ranker_topk"] >= 0 else "") + fmt_pct(r["precision_gain_over_ranker_topk"]),
            vp=fmt_pct(r["vulnerable_verdict_precision"]), bp=fmt_pct(r["benign_verdict_precision"]),
            ur=fmt_pct(r["uncertain_rate"]), f1=fmt_pct(r["f1"]), mcc=r["mcc"]))
    lines.append("")

    # Q1
    lines.append("## 1. Within top-50, does DeepSeek improve precision over the ranker candidate set?\n")
    improved, regressed = [], []
    for ds in DATASETS:
        r = row_for(ds, 50, "uncertain_as_negative")
        g = r["precision_gain_over_ranker_topk"]
        msg = (f"- **{ds}**: ranker top-50 precision {fmt_pct(r['ranker_topk_precision'])} → "
               f"LLM-`vulnerable` precision {fmt_pct(r['llm_filtered_precision'])} "
               f"(**{'+' if g>=0 else ''}{fmt_pct(g)}**), "
               f"keeping {r['vulnerable_verdict_count']} of 50 candidates.")
        lines.append(msg)
        (improved if g > 0 else regressed).append(ds)
    lines.append("")
    if improved:
        lines.append(f"On **{', '.join(improved)}**, filtering to `vulnerable` raises the true-positive rate among "
                     "kept candidates above the ranker's raw top-50 rate — i.e. the LLM acts as a precision filter.")
    if regressed:
        lines.append(f"On **{', '.join(regressed)}**, the `vulnerable` subset is *not* purer than the ranker top-50; "
                     "the LLM does not add precision there (it mostly contributes by rejecting candidates as benign).")
    lines.append("")

    # Q2
    lines.append("## 2. Is DeepSeek better at confirming vulnerabilities or rejecting benign candidates?\n")
    lines.append("| dataset | vulnerable_verdict_precision (confirm) | benign_verdict_precision (reject) |")
    lines.append("|---------|----------------------------------------|-----------------------------------|")
    confirm_wins, reject_wins = 0, 0
    reject_ds, confirm_ds = [], []
    for ds in DATASETS:
        r = row_for(ds, 50, "uncertain_as_negative")
        vp, bp = r["vulnerable_verdict_precision"], r["benign_verdict_precision"]
        if bp > vp:
            reject_wins += 1
            reject_ds.append(ds)
        elif vp > bp:
            confirm_wins += 1
            confirm_ds.append(ds)
        lines.append(f"| {ds} | {fmt_pct(vp)} | {fmt_pct(bp)} |")
    lines.append("")
    if reject_wins > confirm_wins:
        majority = (f"On **{reject_wins} of {len(DATASETS)}** datasets ({', '.join(reject_ds)}), DeepSeek is stronger "
                    "at **rejecting benign candidates** — its `benign` calls are more often correct than its "
                    "`vulnerable` calls. It behaves as a reliable *negative screener* but a noisier *positive confirmer*.")
        if confirm_ds:
            majority += (f" The exception is **{', '.join(confirm_ds)}**, where the base positive rate in the top-50 "
                         "is already high, so 'benign' calls there are frequently wrong (many true positives the "
                         "ranker surfaced get dismissed).")
    elif confirm_wins > reject_wins:
        majority = (f"On **{confirm_wins} of {len(DATASETS)}** datasets ({', '.join(confirm_ds)}), DeepSeek is stronger "
                    "at **confirming vulnerabilities** than at rejecting benign candidates.")
        if reject_ds:
            majority += f" The exception is **{', '.join(reject_ds)}**."
    else:
        majority = "The two skills are evenly split across datasets; there is no consistent direction."
    lines.append(majority + "\n")

    # Q3
    lines.append("## 3. What is the uncertain rate?\n")
    lines.append("| dataset | uncertain@10 | uncertain@30 | uncertain@50 |")
    lines.append("|---------|--------------|--------------|--------------|")
    for ds in DATASETS:
        r10 = row_for(ds, 10, "uncertain_as_negative")
        r30 = row_for(ds, 30, "uncertain_as_negative")
        r50 = row_for(ds, 50, "uncertain_as_negative")
        lines.append(f"| {ds} | {r10['uncertain_count']} ({fmt_pct(r10['uncertain_rate'])}) | "
                     f"{r30['uncertain_count']} ({fmt_pct(r30['uncertain_rate'])}) | "
                     f"{r50['uncertain_count']} ({fmt_pct(r50['uncertain_rate'])}) |")
    lines.append("")
    avg_unc = sum(row_for(ds, 50, "uncertain_as_negative")["uncertain_rate"] for ds in DATASETS) / len(DATASETS)
    lines.append(f"Mean uncertain rate at k=50 is **{fmt_pct(avg_unc)}**. A non-trivial share of candidates "
                 "receive abstentions, which is why we report both `uncertain_as_negative` and `uncertain_excluded`.\n")

    # Q4
    lines.append("## 4. Which dataset benefits most from LLM verification?\n")
    best = max(DATASETS, key=lambda d: row_for(d, 50, "uncertain_as_negative")["precision_gain_over_ranker_topk"])
    ranked = sorted(DATASETS, key=lambda d: row_for(d, 50, "uncertain_as_negative")["precision_gain_over_ranker_topk"], reverse=True)
    for ds in ranked:
        r = row_for(ds, 50, "uncertain_as_negative")
        lines.append(f"- **{ds}**: precision gain {('+' if r['precision_gain_over_ranker_topk']>=0 else '')}"
                     f"{fmt_pct(r['precision_gain_over_ranker_topk'])} at k=50.")
    lines.append("")
    lines.append(f"**{best}** benefits most from LLM verification by precision-gain over the ranker top-50.\n")

    # Q5
    lines.append("## 5. Does the LLM top-k analysis provide stronger evidence than corpus-level full F1?\n")
    lines.append("Yes — but only for the claim it actually supports. Corpus-level full-method F1 dilutes the LLM "
                 "across 950 unseen samples and therefore cannot beat `ranker_only`; that comparison is structurally "
                 "unfair to a top-50-only verifier and should **not** be presented as the LLM's contribution. The "
                 "top-k analysis isolates the regime the LLM operated in (the ranker's top candidates) and measures "
                 "the operationally meaningful quantity: how clean the reviewed candidate list is, and how well the "
                 "LLM screens false positives. It is the correct evidence base for the LLM component — and it is "
                 "honest about the fact that the LLM does not change whole-corpus classification.\n")

    # Q6
    lines.append("## 6. How should this be reported in the paper?\n")
    lines.append("- **Do not** report full-corpus F1 as evidence the LLM helps classification; state plainly that "
                 "full-method corpus F1 does not beat `ranker_only` because LLM verification covers only the top-50 "
                 "of 1000 test samples.")
    lines.append("- Frame the LLM as a **candidate-verification / false-positive-filtering stage** on top of the "
                 "ranker, and report top-k metrics (k=10/30/50) inside the verified set.")
    lines.append("- Report both `uncertain_as_negative` and `uncertain_excluded` so abstentions are transparent.")
    lines.append("- Lead with `ranker_topk_precision` vs `llm_filtered_precision` (precision gain), plus "
                 "`benign_verdict_precision` to evidence the LLM's strength as a negative screener.")
    lines.append("- Report the uncertain rate as a limitation / calibration signal.")
    lines.append("- Keep the corpus-level numbers in the paper as context, clearly labeled as a different question "
                 "(detection over the whole corpus) than what the LLM stage was evaluated for (verification within "
                 "retrieved candidates).\n")

    with open(path, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
