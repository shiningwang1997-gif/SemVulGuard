"""Tests for the hybrid encoder over a collated batch."""

from __future__ import annotations

from pathlib import Path

import torch
from torch.utils.data import DataLoader

from semvulguard.models.encoder.hybrid import HybridCodeEncoder
from semvulguard.models.ranker.dataset import (
    NODE_FEATURE_SIZE,
    STATIC_VECTOR_SIZE,
    FeatureDataset,
    collate_fn,
)


def _batch(fixtures_dir: Path) -> dict:
    dataset = FeatureDataset(fixtures_dir / "model" / "features.jsonl")
    loader = DataLoader(
        dataset, batch_size=len(dataset), shuffle=False, collate_fn=collate_fn
    )
    return next(iter(loader))


def test_hybrid_output_shape(fixtures_dir: Path):
    enc = HybridCodeEncoder(hidden_size=32, fallback=True, use_gatv2=False)
    batch = _batch(fixtures_dir)
    out = enc(batch["sequence_texts"], batch, batch["static_vectors"])
    assert out.shape == (batch["num_graphs"], 32)


def test_hybrid_handles_sample_without_graph(fixtures_dir: Path):
    # Fixture s3 has no nodes; the fused embedding must still be finite.
    enc = HybridCodeEncoder(hidden_size=16, fallback=True, use_gatv2=False)
    batch = _batch(fixtures_dir)
    out = enc(batch["sequence_texts"], batch, batch["static_vectors"])
    assert torch.isfinite(out).all()


def test_hybrid_feature_dims_default_to_dataset_layout():
    enc = HybridCodeEncoder(hidden_size=8, fallback=True, use_gatv2=False)
    assert enc.graph_encoder.node_feature_size == NODE_FEATURE_SIZE
    assert enc.static_proj.in_features == STATIC_VECTOR_SIZE
