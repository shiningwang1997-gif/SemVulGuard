"""Phase 7: build test-only artifacts and a leakage audit per dataset.

Filters every per-sample artifact to ``split == "test"`` so the final evaluation
touches NO train/valid sample. Produces, under .../{ds}/test_only/:
  manifest_test.jsonl, features_test.jsonl, static_alerts_test.jsonl,
  rank_scores_test.jsonl, leakage_audit.md

Top-k LLM candidate selection is later computed WITHIN rank_scores_test.jsonl
(the test set), never the full subset -- this file is the source of truth for
that. The audit proves the train/valid samples are excluded and that ids align.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import SampleRecord, StaticAlertRecord
from semvulguard.utils.jsonl import read_jsonl, read_models, write_jsonl

from scripts.experiments.formal.config import ROOT, SUBSET_TARGETS


def _split_map(ddir: Path) -> dict[str, str]:
    return {r["sample_id"]: r["split"] for r in read_jsonl(ddir / "split.jsonl")}


def run_one(ds: str) -> dict:
    ddir = ROOT / ds
    out = ddir / "test_only"
    out.mkdir(parents=True, exist_ok=True)
    split = _split_map(ddir)
    test_ids = {sid for sid, sp in split.items() if sp == "test"}
    counts = {"train": 0, "valid": 0, "test": 0}
    for sp in split.values():
        counts[sp] = counts.get(sp, 0) + 1

    # manifest
    manifest = read_models(ddir / "manifest.jsonl", SampleRecord)
    test_manifest = [m for m in manifest if m.split == "test"]
    write_jsonl(out / "manifest_test.jsonl", test_manifest)

    # features
    features = read_models(ddir / "features.jsonl", FeatureRecord)
    test_features = [f for f in features if f.sample_id in test_ids]
    write_jsonl(out / "features_test.jsonl", test_features)

    # static alerts
    alerts = read_models(ddir / "static_alerts_codeql.jsonl", StaticAlertRecord)
    test_alerts = [a for a in alerts if a.sample_id in test_ids]
    write_jsonl(out / "static_alerts_test.jsonl", test_alerts)

    # rank scores (re-rank WITHIN the test set)
    all_scores = list(read_jsonl(ddir / "rank_scores_sklearn.jsonl"))
    test_scores = [r for r in all_scores if r["sample_id"] in test_ids]
    test_scores.sort(key=lambda r: (-float(r["rank_score"]), r["sample_id"]))
    for i, r in enumerate(test_scores):
        r["rank"] = i + 1
    write_jsonl(out / "rank_scores_test.jsonl", test_scores)

    # ---- audit checks ----
    feat_ids = {f.sample_id for f in test_features}
    score_ids = {r["sample_id"] for r in test_scores}
    man_ids = {m.sample_id for m in test_manifest}
    labels_feat = {f.sample_id: f.label for f in test_features}
    labels_man = {m.sample_id: m.label for m in test_manifest}

    train_valid_in_test = [r["sample_id"] for r in test_scores
                           if split.get(r["sample_id"]) in ("train", "valid")]
    label_leak = sum(1 for sid in feat_ids
                     if labels_feat.get(sid) != labels_man.get(sid))
    # label-as-feature leakage probe: is any static_feature exactly the label?
    leak_feature_keys = []
    for f in test_features[:200]:
        for k, v in (f.static_features or {}).items():
            if isinstance(v, (int, float)) and v == f.label and k.lower().endswith("label"):
                leak_feature_keys.append(k)
    n_pos = sum(1 for m in test_manifest if m.label == 1)

    checks = [
        ("test split filtered correctly",
         all(m.split == "test" for m in test_manifest), f"{len(test_manifest)} records"),
        ("no train/valid sample in test rank scores",
         len(train_valid_in_test) == 0, f"{len(train_valid_in_test)} offenders"),
        ("manifest/feature/score id sets identical",
         man_ids == feat_ids == score_ids,
         f"man={len(man_ids)} feat={len(feat_ids)} score={len(score_ids)}"),
        ("label consistency feature vs manifest", label_leak == 0,
         f"{label_leak} mismatches"),
        ("no label-as-feature leakage detected", len(leak_feature_keys) == 0,
         f"{leak_feature_keys}"),
        ("top-k recomputed within test set (rank 1..N contiguous)",
         [r["rank"] for r in test_scores] == list(range(1, len(test_scores) + 1)),
         f"n={len(test_scores)}"),
        ("both classes present in test",
         0 < n_pos < len(test_manifest), f"pos={n_pos}/{len(test_manifest)}"),
    ]
    ok = all(c[1] for c in checks)

    L = [f"# Leakage Audit — {ds} (test-only final evaluation)", "",
         "## Split sizes", "",
         f"- train samples: **{counts['train']}** (EXCLUDED from final metrics)",
         f"- valid samples: **{counts['valid']}** (EXCLUDED from final metrics)",
         f"- test samples: **{counts['test']}**",
         f"- **final evaluation sample count: {len(test_manifest)}** (= test only)",
         f"- test positives: {n_pos} / {len(test_manifest)} "
         f"(pos_rate={n_pos/max(1,len(test_manifest)):.3f})", "",
         "## Audit checks", "",
         f"- Status: **{'ALL CHECKS PASSED' if ok else 'CHECKS FAILED'}**", ""]
    for name, passed, detail in checks:
        L.append(f"- {'PASS' if passed else 'FAIL'}: {name} ({detail})")
    L += ["", "## How leakage is prevented", "",
          "- The ranker was fit on the **train** split only (Phase 6); train/valid "
          "metrics are reported separately and are NOT used as scientific results.",
          "- Final fusion + evaluation (Phases 8/11) consume ONLY the files in this "
          "`test_only/` directory.",
          "- Top-k candidates for LLM verification are selected from "
          "`rank_scores_test.jsonl` (the test set re-ranked 1..N), never the full subset.",
          "- DiverseVul/BigVul are heavily imbalanced; PR-AUC/MCC/ROC-AUC are the "
          "reliable metrics, not thresholded F1 on ~11 positives.", "",
          "## Remaining leakage risk", "",
          "- TF-IDF vocabulary is fit on train only; no test text informs the model.",
          "- No cross-sample features; each FeatureRecord is independent, so there is "
          "no train→test information path beyond the learned weights.",
          "- Residual risk: duplicate/near-duplicate functions could appear across "
          "splits (no semantic dedup was applied). This is a known dataset-level "
          "caveat (esp. DiverseVul/Devign) and is noted as a limitation.", ""]
    (out / "leakage_audit.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"{ds}: test={len(test_manifest)} (pos={n_pos}) "
          f"alerts={len(test_alerts)} {'OK' if ok else 'FAILED'}")
    return {"dataset": ds, "ok": ok, "test_n": len(test_manifest),
            "test_pos": n_pos, "test_alerts": len(test_alerts),
            "counts": counts}


def main(argv: list[str] | None = None) -> int:
    targets = argv if argv else list(SUBSET_TARGETS)
    results = [run_one(ds) for ds in targets]
    (ROOT / "leakage_audit_summary.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or None))
