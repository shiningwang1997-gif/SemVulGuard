"""Score all Devign samples with the trained ``sklearn_tfidf`` ranker.

Loads the saved model bundle, scores every feature record (positive-class
probability in [0,1]), sorts by descending score, assigns a global rank, and
writes a rank-scores JSONL with the same field contract as the torch ranker
(``sample_id`` / ``rank_score`` / ``rank`` / ``label`` / ``metadata``).

It also validates the produced scores against the feature set (and the manifest
when provided) and writes a markdown validation report.

Example::

    python -m semvulguard.models.ranker.infer_sklearn \
        --features artifacts/experiments/devign/features.jsonl \
        --static-alerts artifacts/experiments/devign/static_alerts_codeql.jsonl \
        --model-dir artifacts/experiments/devign_sklearn_ranker \
        --output artifacts/experiments/devign_sklearn_ranker/rank_scores_sklearn.jsonl
"""

from __future__ import annotations

import argparse
from pathlib import Path

from semvulguard.models.ranker.sklearn_ranker import (
    RankerSample,
    SklearnRanker,
    build_samples,
)
from semvulguard.utils.jsonl import read_jsonl, write_jsonl
from semvulguard.utils.logging import get_logger

LOGGER = get_logger("semvulguard.models.ranker.infer_sklearn")


def score_samples(
    ranker: SklearnRanker, samples: list[RankerSample]
) -> list[dict]:
    """Score and rank every sample; returns rows ordered by descending score."""
    scores = ranker.predict_scores(samples)
    rows = [
        {
            "sample_id": s.sample_id,
            "rank_score": float(score),
            "label": int(s.label),
            "metadata": s.metadata,
        }
        for s, score in zip(samples, scores, strict=True)
    ]
    rows.sort(key=lambda r: (-r["rank_score"], r["sample_id"]))
    for i, row in enumerate(rows):
        row["rank"] = i + 1
    return rows


def _validate(
    rows: list[dict],
    samples: list[RankerSample],
    manifest_path: Path | None,
) -> tuple[bool, list[str]]:
    """Run alignment / range / coverage checks. Returns (ok, messages)."""
    msgs: list[str] = []
    ok = True

    feature_ids = {s.sample_id for s in samples}
    score_ids = [r["sample_id"] for r in rows]
    score_id_set = set(score_ids)

    # 1. one score per sample, no duplicates
    if len(score_ids) != len(score_id_set):
        ok = False
        n_dupes = len(score_ids) - len(score_id_set)
        msgs.append(f"FAIL: duplicate sample_ids in rank scores ({n_dupes} dupes)")
    else:
        msgs.append(f"PASS: no duplicate sample_ids ({len(score_ids)} rows)")

    # 2. feature alignment (every feature has exactly one score and vice versa)
    missing = feature_ids - score_id_set
    extra = score_id_set - feature_ids
    if missing or extra:
        ok = False
        msgs.append(
            f"FAIL: feature/score mismatch — missing={len(missing)} extra={len(extra)}"
        )
    else:
        msgs.append(
            f"PASS: every feature has exactly one rank score ({len(feature_ids)})"
        )

    # 3. rank_score in [0, 1]
    out_of_range = [r["sample_id"] for r in rows if not (0.0 <= r["rank_score"] <= 1.0)]
    if out_of_range:
        ok = False
        msgs.append(f"FAIL: {len(out_of_range)} rank_scores outside [0,1]")
    else:
        msgs.append("PASS: all rank_scores in [0,1]")

    # 4. ranks are a contiguous 1..N permutation
    ranks = sorted(r["rank"] for r in rows)
    if ranks == list(range(1, len(rows) + 1)):
        msgs.append(f"PASS: ranks form contiguous 1..{len(rows)}")
    else:
        ok = False
        msgs.append("FAIL: ranks are not a contiguous 1..N sequence")

    # 5. manifest alignment (optional)
    if manifest_path and Path(manifest_path).exists():
        manifest_ids = {row["sample_id"] for row in read_jsonl(manifest_path)}
        m_missing = manifest_ids - score_id_set
        m_extra = score_id_set - manifest_ids
        if m_missing or m_extra:
            ok = False
            msgs.append(
                f"FAIL: manifest mismatch — missing={len(m_missing)} "
                f"extra={len(m_extra)}"
            )
        else:
            msgs.append(
                f"PASS: rank scores align with manifest ({len(manifest_ids)} samples)"
            )
    else:
        msgs.append("SKIP: no manifest provided for cross-check")

    return ok, msgs


def _write_validation_report(
    path: Path,
    ok: bool,
    msgs: list[str],
    rows: list[dict],
    model_dir: Path,
) -> None:
    scores = [r["rank_score"] for r in rows]
    n_pos = sum(1 for r in rows if r["label"] == 1)
    smin = min(scores) if scores else 0.0
    smax = max(scores) if scores else 0.0
    smean = sum(scores) / len(scores) if scores else 0.0
    L = [
        "# Rank-Score Validation — sklearn_tfidf ranker",
        "",
        f"- Status: **{'ALL CHECKS PASSED' if ok else 'CHECKS FAILED'}**",
        f"- Model dir: `{model_dir}`",
        f"- Samples scored: {len(rows)} (positives={n_pos})",
        f"- rank_score range: [{smin:.6f}, {smax:.6f}], mean={smean:.6f}",
        "",
        "## Checks",
        "",
    ]
    L += [f"- {m}" for m in msgs]
    L += [
        "",
        "## Top-10 by rank_score",
        "",
        "| rank | sample_id | rank_score | label |",
        "|---|---|---|---|",
    ]
    for r in rows[:10]:
        L.append(
            f"| {r['rank']} | {r['sample_id']} | {r['rank_score']:.6f} | {r['label']} |"
        )
    L.append("")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def infer(
    features_path: Path,
    model_dir: Path,
    output_path: Path,
    static_alerts_path: Path | None = None,
    manifest_path: Path | None = None,
) -> list[dict]:
    """End-to-end: load model, score+rank all samples, write JSONL + validation."""
    samples = build_samples(features_path, static_alerts_path)
    ranker = SklearnRanker.load(model_dir)
    rows = score_samples(ranker, samples)
    n = write_jsonl(output_path, rows)

    ok, msgs = _validate(rows, samples, manifest_path)
    report_path = Path(model_dir) / "rank_score_validation.md"
    _write_validation_report(report_path, ok, msgs, rows, Path(model_dir))

    LOGGER.info("wrote %d rank scores -> %s (validation=%s)", n, output_path, ok)
    if not ok:
        LOGGER.warning("rank-score validation FAILED; see %s", report_path)
    return rows


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="semvulguard.models.ranker.infer_sklearn",
        description="Score Devign samples with the sklearn_tfidf ranker.",
    )
    p.add_argument("--features", required=True, type=Path)
    p.add_argument("--static-alerts", type=Path, default=None)
    p.add_argument("--manifest", type=Path, default=None)
    p.add_argument("--model-dir", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    rows = infer(
        features_path=args.features,
        model_dir=args.model_dir,
        output_path=args.output,
        static_alerts_path=args.static_alerts,
        manifest_path=args.manifest,
    )
    print(f"scored {len(rows)} samples -> {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["infer", "score_samples", "build_arg_parser", "main"]
