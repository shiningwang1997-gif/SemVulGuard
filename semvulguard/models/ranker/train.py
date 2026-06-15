"""Train the candidate ranker on FeatureRecord JSONL.

A minimal, CPU-friendly, deterministic training loop suitable for tiny fixture
data. It saves a checkpoint (weights + the config needed to rebuild the model)
and a ``train_metrics.json`` summary.

Example::

    python -m semvulguard.models.ranker.train \
        --features tests/fixtures/model/features.jsonl \
        --output-dir artifacts/ranker --epochs 2 --batch-size 2 --fallback
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader

from semvulguard.models.encoder.hybrid import HybridCodeEncoder
from semvulguard.models.ranker.dataset import (
    NODE_FEATURE_SIZE,
    STATIC_VECTOR_SIZE,
    FeatureDataset,
    collate_fn,
)
from semvulguard.models.ranker.model import CandidateRanker
from semvulguard.utils.logging import get_logger

LOGGER = get_logger("semvulguard.models.ranker.train")


def set_seed(seed: int) -> None:
    """Seed Python and torch RNGs for reproducible runs."""
    random.seed(seed)
    torch.manual_seed(seed)


def build_model(
    hidden_size: int = 256,
    model_name: str | None = None,
    fallback: bool = True,
    use_gatv2: bool = True,
) -> CandidateRanker:
    """Construct a ranker with a hybrid encoder under a fixed feature layout."""
    encoder = HybridCodeEncoder(
        hidden_size=hidden_size,
        node_feature_size=NODE_FEATURE_SIZE,
        static_vector_size=STATIC_VECTOR_SIZE,
        model_name=model_name,
        fallback=fallback,
        use_gatv2=use_gatv2,
    )
    return CandidateRanker(encoder, hidden_size=hidden_size)


def train(
    features_path: Path,
    output_dir: Path,
    epochs: int = 2,
    batch_size: int = 2,
    lr: float = 1e-3,
    hidden_size: int = 256,
    model_name: str | None = None,
    fallback: bool = True,
    use_gatv2: bool = True,
    seed: int = 42,
) -> dict:
    """Run training and persist a checkpoint + metrics. Returns the metrics."""
    set_seed(seed)
    device = torch.device("cpu")

    dataset = FeatureDataset(features_path)
    if len(dataset) == 0:
        raise ValueError(f"no feature records found in {features_path}")
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        collate_fn=collate_fn,
    )

    model = build_model(
        hidden_size=hidden_size,
        model_name=model_name,
        fallback=fallback,
        use_gatv2=use_gatv2,
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    criterion = nn.BCEWithLogitsLoss()

    model.train()
    epoch_losses: list[float] = []
    for epoch in range(epochs):
        total = 0.0
        n_batches = 0
        for batch in loader:
            optimizer.zero_grad()
            logits = model.forward_batch(batch)
            loss = criterion(logits, batch["labels"].to(device))
            loss.backward()
            optimizer.step()
            total += float(loss.item())
            n_batches += 1
        mean_loss = total / max(n_batches, 1)
        epoch_losses.append(mean_loss)
        LOGGER.info("epoch %d/%d loss=%.4f", epoch + 1, epochs, mean_loss)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "model.pt"
    config = {
        "hidden_size": hidden_size,
        "model_name": model_name,
        "fallback": fallback,
        "use_gatv2": use_gatv2,
        "node_feature_size": NODE_FEATURE_SIZE,
        "static_vector_size": STATIC_VECTOR_SIZE,
    }
    torch.save(
        {"state_dict": model.state_dict(), "config": config}, checkpoint_path
    )

    metrics = {
        "epochs": epochs,
        "batch_size": batch_size,
        "num_samples": len(dataset),
        "final_loss": epoch_losses[-1] if epoch_losses else None,
        "epoch_losses": epoch_losses,
        "uses_huggingface": model.encoder.sequence_encoder.uses_huggingface,
        "uses_gatv2": model.encoder.graph_encoder.uses_gatv2,
    }
    with (output_dir / "train_metrics.json").open("w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)

    LOGGER.info("saved checkpoint -> %s", checkpoint_path)
    return metrics


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="semvulguard.models.ranker.train",
        description="Train the candidate ranker on FeatureRecord JSONL.",
    )
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--hidden-size", type=int, default=256)
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--fallback",
        action="store_true",
        help="force the sequence-encoder fallback (no HuggingFace download)",
    )
    parser.add_argument(
        "--no-gatv2",
        action="store_true",
        help="force the graph-encoder fallback (no torch_geometric)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    metrics = train(
        features_path=args.features,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        hidden_size=args.hidden_size,
        model_name=args.model_name,
        fallback=args.fallback or args.model_name is None,
        use_gatv2=not args.no_gatv2,
        seed=args.seed,
    )
    print(
        f"trained {metrics['epochs']} epochs on {metrics['num_samples']} "
        f"samples; final_loss={metrics['final_loss']:.4f}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["train", "build_model", "set_seed"]
