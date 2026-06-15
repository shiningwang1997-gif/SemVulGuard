"""Train the ``sklearn_tfidf`` candidate ranker on Devign features + CodeQL alerts.

Deterministic, CPU-only, no network. Builds a TF-IDF + numeric-feature design
matrix (see :mod:`semvulguard.models.ranker.sklearn_ranker`), fits a
``LogisticRegression`` (default) or ``RandomForestClassifier``, and writes the
full training-output bundle.

If the manifest carries a usable train/valid/test split it is honored; otherwise
a deterministic stratified 70/10/20 split (seed-controlled) is created and saved
to ``<output-dir>/split.jsonl``.

Example::

    python -m semvulguard.models.ranker.train_sklearn \
        --features artifacts/experiments/devign/features.jsonl \
        --static-alerts artifacts/experiments/devign/static_alerts_codeql.jsonl \
        --manifest artifacts/experiments/devign/manifest.jsonl \
        --output-dir artifacts/experiments/devign_sklearn_ranker \
        --seed 42 --model logistic_regression
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from semvulguard.eval.classification import compute_binary_classification_metrics
from semvulguard.models.ranker.sklearn_ranker import (
    NUMERIC_FEATURE_NAMES,
    RankerSample,
    SklearnRanker,
    build_samples,
)
from semvulguard.utils.jsonl import read_jsonl, write_jsonl
from semvulguard.utils.logging import get_logger

LOGGER = get_logger("semvulguard.models.ranker.train_sklearn")

VALID_SPLITS = ("train", "valid", "test")
DEFAULT_RATIOS = (0.7, 0.1, 0.2)


def _load_manifest_splits(manifest_path: Path | None) -> dict[str, str]:
    """Map sample_id -> split from the manifest (only known split labels)."""
    out: dict[str, str] = {}
    if not manifest_path or not Path(manifest_path).exists():
        return out
    for row in read_jsonl(manifest_path):
        split = str(row.get("split", "unknown")).lower()
        if split in VALID_SPLITS:
            out[row["sample_id"]] = split
    return out


def stratified_split(
    samples: list[RankerSample],
    seed: int = 42,
    ratios: tuple[float, float, float] = DEFAULT_RATIOS,
) -> dict[str, str]:
    """Deterministic stratified train/valid/test assignment by label.

    Within each label, sample_ids are sorted (stable) then shuffled with a
    seeded RNG and partitioned by the ratios. Returns sample_id -> split.
    """
    rng = np.random.default_rng(seed)
    by_label: dict[int, list[str]] = {}
    for s in samples:
        by_label.setdefault(s.label, []).append(s.sample_id)

    assignment: dict[str, str] = {}
    train_r, valid_r, _ = ratios
    for label in sorted(by_label):
        ids = sorted(by_label[label])
        perm = rng.permutation(len(ids))
        ordered = [ids[i] for i in perm]
        n = len(ordered)
        n_train = int(round(n * train_r))
        n_valid = int(round(n * valid_r))
        # guard against rounding overflow
        n_train = min(n_train, n)
        n_valid = min(n_valid, n - n_train)
        for i, sid in enumerate(ordered):
            if i < n_train:
                assignment[sid] = "train"
            elif i < n_train + n_valid:
                assignment[sid] = "valid"
            else:
                assignment[sid] = "test"
    return assignment


def resolve_split(
    samples: list[RankerSample],
    manifest_path: Path | None,
    seed: int,
    ratios: tuple[float, float, float] = DEFAULT_RATIOS,
) -> tuple[dict[str, str], bool]:
    """Use the manifest split if it covers all samples; else build one.

    Returns ``(assignment, created)`` where ``created`` is True when a fresh
    stratified split was generated.
    """
    manifest = _load_manifest_splits(manifest_path)
    sample_ids = {s.sample_id for s in samples}
    covers_all = sample_ids and sample_ids.issubset(set(manifest))
    has_all_classes = (
        len({manifest[s] for s in sample_ids}) >= 2 if covers_all else False
    )
    if covers_all and has_all_classes:
        return {s: manifest[s] for s in sample_ids}, False
    return stratified_split(samples, seed=seed, ratios=ratios), True


def _metrics_for(
    ranker: SklearnRanker, samples: list[RankerSample], threshold: float = 0.5
) -> dict:
    """Classification metric suite over a sample subset."""
    if not samples:
        return {"num_samples": 0}
    scores = ranker.predict_scores(samples)
    labels = [s.label for s in samples]
    m = compute_binary_classification_metrics(labels, list(scores), threshold)
    m["num_samples"] = len(samples)
    m["num_positive"] = int(sum(labels))
    return m


def _write_feature_importance(ranker: SklearnRanker, path: Path) -> bool:
    pairs = ranker.feature_importance()
    if not pairs:
        return False
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["feature", "weight", "abs_weight"])
        for name, weight in pairs:
            w.writerow([name, f"{weight:.8f}", f"{abs(weight):.8f}"])
    return True


def _write_report(
    out_dir: Path,
    model_name: str,
    seed: int,
    counts: dict[str, int],
    split_created: bool,
    train_m: dict,
    valid_m: dict,
    test_m: dict,
    importance_written: bool,
) -> None:
    def f(d: dict, key: str) -> str:
        v = d.get(key)
        return f"{v:.4f}" if isinstance(v, (int, float)) else "n/a"

    L = [
        "# sklearn_tfidf Ranker — Training Report",
        "",
        "## Configuration",
        "",
        "- Backend: **sklearn_tfidf**",
        f"- Model: **{model_name}** (class_weight=balanced)",
        f"- Seed: {seed}",
        "- Features: TF-IDF(function_code) + code metrics + CodeQL alert features"
        " + FeatureRecord static_features",
        f"- Numeric feature columns: {len(NUMERIC_FEATURE_NAMES)}",
        f"- Split source: "
        f"{'generated stratified 70/10/20' if split_created else 'manifest'}",
        f"- Split sizes: train={counts['train']} valid={counts['valid']} "
        f"test={counts['test']}",
        "",
        "## Metrics by split",
        "",
        "| split | n | pos | precision | recall | F1 | MCC | PR-AUC | ROC-AUC |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, m in (("train", train_m), ("valid", valid_m), ("test", test_m)):
        L.append(
            f"| {name} | {m.get('num_samples', 0)} | {m.get('num_positive', 0)} "
            f"| {f(m, 'precision')} | {f(m, 'recall')} | {f(m, 'f1')} "
            f"| {f(m, 'mcc')} | {f(m, 'pr_auc')} | {f(m, 'roc_auc')} |"
        )
    L += [
        "",
        "## Notes",
        "",
        "- Deterministic: fixed seed, liblinear/forest with fixed random_state.",
        "- No DeepSeek / network calls; CPU-only scikit-learn.",
        f"- feature_importance.csv "
        f"{'written' if importance_written else 'unavailable'}.",
        "",
    ]
    (out_dir / "training_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def train(
    features_path: Path,
    output_dir: Path,
    static_alerts_path: Path | None = None,
    manifest_path: Path | None = None,
    seed: int = 42,
    model: str = "logistic_regression",
    threshold: float = 0.5,
) -> dict:
    """Fit the sklearn ranker and write all training outputs. Returns a summary."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    samples = build_samples(features_path, static_alerts_path)
    if not samples:
        raise ValueError(f"no feature records found in {features_path}")

    assignment, created = resolve_split(samples, manifest_path, seed)

    # Persist the split assignment.
    split_rows = [
        {"sample_id": s.sample_id, "split": assignment[s.sample_id], "label": s.label}
        for s in samples
    ]
    write_jsonl(output_dir / "split.jsonl", split_rows)

    by_split: dict[str, list[RankerSample]] = {k: [] for k in VALID_SPLITS}
    for s in samples:
        by_split[assignment[s.sample_id]].append(s)

    train_samples = by_split["train"]
    if len(train_samples) < 2 or len({s.label for s in train_samples}) < 2:
        raise ValueError("training split must contain both classes")

    ranker = SklearnRanker(model=model, seed=seed).fit(train_samples)
    ranker.save(output_dir)

    train_m = _metrics_for(ranker, train_samples, threshold)
    valid_m = _metrics_for(ranker, by_split["valid"], threshold)
    test_m = _metrics_for(ranker, by_split["test"], threshold)

    for name, m in (
        ("train_metrics.json", train_m),
        ("valid_metrics.json", valid_m),
        ("test_metrics.json", test_m),
    ):
        (output_dir / name).write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")

    importance_written = _write_feature_importance(
        ranker, output_dir / "feature_importance.csv"
    )

    counts = {k: len(by_split[k]) for k in VALID_SPLITS}
    _write_report(
        output_dir, model, seed, counts, created,
        train_m, valid_m, test_m, importance_written,
    )

    LOGGER.info(
        "trained sklearn_tfidf ranker (%s) on %d samples -> %s",
        model, len(train_samples), output_dir,
    )
    return {
        "model": model,
        "seed": seed,
        "split_created": created,
        "counts": counts,
        "train_metrics": train_m,
        "valid_metrics": valid_m,
        "test_metrics": test_m,
        "feature_importance_written": importance_written,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="semvulguard.models.ranker.train_sklearn",
        description="Train the sklearn_tfidf candidate ranker.",
    )
    p.add_argument("--features", required=True, type=Path)
    p.add_argument("--static-alerts", type=Path, default=None)
    p.add_argument("--manifest", type=Path, default=None)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--model",
        choices=["logistic_regression", "random_forest"],
        default="logistic_regression",
    )
    p.add_argument("--threshold", type=float, default=0.5)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = train(
        features_path=args.features,
        output_dir=args.output_dir,
        static_alerts_path=args.static_alerts,
        manifest_path=args.manifest,
        seed=args.seed,
        model=args.model,
        threshold=args.threshold,
    )
    tm = summary["test_metrics"]
    print(
        f"trained {summary['model']} | splits={summary['counts']} | "
        f"test F1={tm.get('f1')} MCC={tm.get('mcc')} PR-AUC={tm.get('pr_auc')} "
        f"-> {args.output_dir}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["train", "stratified_split", "resolve_split", "build_arg_parser", "main"]
