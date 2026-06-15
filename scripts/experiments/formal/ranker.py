"""Phase 6: train + infer the sklearn_tfidf ranker per dataset (leak-free).

Reuses the existing library:
  * train_sklearn.train()  -- fits ONLY on the train split (manifest split is
    honored because Phase 3 wrote train/valid/test into manifest.jsonl), and
    writes train/valid/test_metrics.json. The held-out TEST metrics are the
    leak-free ranker generalization signal.
  * infer_sklearn.infer()  -- scores every subset sample -> rank_scores_sklearn.jsonl
    (rank_score in [0,1]); used downstream for top-k candidate selection.

Outputs per dataset under .../{ds}/sklearn_ranker/ plus
.../{ds}/rank_scores_sklearn.jsonl and rank_score_validation.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from semvulguard.models.ranker.infer_sklearn import infer
from semvulguard.models.ranker.train_sklearn import train

from scripts.experiments.formal.config import ROOT, SEED, SUBSET_TARGETS


def run_one(ds: str) -> dict:
    ddir = ROOT / ds
    features = ddir / "features.jsonl"
    alerts = ddir / "static_alerts_codeql.jsonl"
    manifest = ddir / "manifest.jsonl"
    out_dir = ddir / "sklearn_ranker"

    summary = train(
        features_path=features, output_dir=out_dir,
        static_alerts_path=alerts, manifest_path=manifest,
        seed=SEED, model="logistic_regression", threshold=0.5,
    )

    # score all subset samples
    rank_out = ddir / "rank_scores_sklearn.jsonl"
    infer(
        features_path=features, model_dir=out_dir, output_path=rank_out,
        static_alerts_path=alerts, manifest_path=manifest,
    )
    # copy validation report next to the dataset for convenience
    val_src = out_dir / "rank_score_validation.md"
    if val_src.exists():
        (ddir / "rank_score_validation.md").write_text(
            val_src.read_text(encoding="utf-8"), encoding="utf-8")

    tm = summary["test_metrics"]
    vm = summary["valid_metrics"]
    print(f"{ds}: split={summary['counts']} | "
          f"TEST F1={tm.get('f1')} MCC={tm.get('mcc')} PR-AUC={tm.get('pr_auc')} "
          f"ROC-AUC={tm.get('roc_auc')} (n={tm.get('num_samples')})")
    return {
        "dataset": ds, "counts": summary["counts"],
        "split_created": summary["split_created"],
        "train_metrics": summary["train_metrics"],
        "valid_metrics": vm, "test_metrics": tm,
        "rank_scores": str(rank_out),
    }


def main(argv: list[str] | None = None) -> int:
    targets = argv if argv else list(SUBSET_TARGETS)
    results = [run_one(ds) for ds in targets]
    (ROOT / "ranker_summary.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or None))
