"""Run the trained ranker over FeatureRecord JSONL and emit ranked scores.

Loads a checkpoint (weights + config), scores every sample with a sigmoid over
the ranker logit, sorts by descending risk, and writes a JSONL of
``sample_id`` / ``rank_score`` / ``rank`` / ``label`` / ``metadata``. ``--top-k``
limits how many rows are written (ranks are still global).

Example::

    python -m semvulguard.models.ranker.infer \
        --features tests/fixtures/model/features.jsonl \
        --checkpoint artifacts/ranker/model.pt \
        --output artifacts/rank_scores.jsonl --top-k 20
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from semvulguard.models.ranker.dataset import FeatureDataset, collate_fn
from semvulguard.models.ranker.train import build_model
from semvulguard.utils.jsonl import write_jsonl
from semvulguard.utils.logging import get_logger

LOGGER = get_logger("semvulguard.models.ranker.infer")


def load_model(checkpoint_path: Path):
    """Rebuild the ranker from a checkpoint's saved config and load weights."""
    checkpoint = torch.load(
        Path(checkpoint_path), map_location="cpu", weights_only=False
    )
    config = checkpoint["config"]
    model = build_model(
        hidden_size=config["hidden_size"],
        model_name=config.get("model_name"),
        fallback=config.get("fallback", True),
        use_gatv2=config.get("use_gatv2", True),
    )
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model


def score_dataset(
    model, dataset: FeatureDataset, batch_size: int = 8
) -> list[dict]:
    """Score every sample; return unsorted ``{sample_id, rank_score, ...}`` rows."""
    loader = DataLoader(
        dataset, batch_size=batch_size, shuffle=False, collate_fn=collate_fn
    )
    rows: list[dict] = []
    with torch.no_grad():
        for batch in loader:
            logits = model.forward_batch(batch)
            scores = torch.sigmoid(logits)
            for i, sample_id in enumerate(batch["sample_ids"]):
                rows.append(
                    {
                        "sample_id": sample_id,
                        "rank_score": float(scores[i].item()),
                        "label": int(batch["labels"][i].item()),
                        "metadata": batch["metadata"][i],
                    }
                )
    return rows


def rank_rows(rows: list[dict], top_k: int | None = None) -> list[dict]:
    """Sort rows by descending score (ties broken by sample_id) and rank them."""
    ordered = sorted(rows, key=lambda r: (-r["rank_score"], r["sample_id"]))
    for i, row in enumerate(ordered):
        row["rank"] = i + 1
    if top_k is not None:
        ordered = ordered[:top_k]
    return ordered


def infer(
    features_path: Path,
    checkpoint_path: Path,
    output_path: Path,
    top_k: int | None = None,
    batch_size: int = 8,
) -> list[dict]:
    """End-to-end: load model, score, rank, write JSONL. Returns the rows."""
    dataset = FeatureDataset(features_path)
    model = load_model(checkpoint_path)
    rows = score_dataset(model, dataset, batch_size=batch_size)
    ranked = rank_rows(rows, top_k=top_k)
    n = write_jsonl(output_path, ranked)
    LOGGER.info("wrote %d ranked scores -> %s", n, output_path)
    return ranked


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="semvulguard.models.ranker.infer",
        description="Rank samples by vulnerability risk using a checkpoint.",
    )
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=8)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    ranked = infer(
        features_path=args.features,
        checkpoint_path=args.checkpoint,
        output_path=args.output,
        top_k=args.top_k,
        batch_size=args.batch_size,
    )
    print(f"ranked {len(ranked)} samples -> {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["infer", "load_model", "score_dataset", "rank_rows"]
