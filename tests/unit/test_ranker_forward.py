"""Tests for the ranker forward pass and a single training step."""

from __future__ import annotations

from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader

from semvulguard.models.ranker.dataset import FeatureDataset, collate_fn
from semvulguard.models.ranker.train import build_model


def _loader(fixtures_dir: Path, batch_size: int = 4) -> DataLoader:
    ds = FeatureDataset(fixtures_dir / "model" / "features.jsonl")
    return DataLoader(
        ds, batch_size=batch_size, shuffle=False, collate_fn=collate_fn
    )


def test_forward_pass_logits_shape(fixtures_dir: Path):
    model = build_model(hidden_size=16, fallback=True, use_gatv2=False)
    batch = next(iter(_loader(fixtures_dir)))
    logits = model.forward_batch(batch)
    assert logits.shape == (batch["num_graphs"],)
    assert torch.isfinite(logits).all()


def test_forward_matches_explicit_call(fixtures_dir: Path):
    model = build_model(hidden_size=16, fallback=True, use_gatv2=False)
    model.eval()
    batch = next(iter(_loader(fixtures_dir)))
    with torch.no_grad():
        a = model.forward_batch(batch)
        b = model.forward(
            batch["sequence_texts"], batch, batch["static_vectors"]
        )
    assert torch.allclose(a, b)


def test_single_training_step_runs_and_updates(fixtures_dir: Path):
    torch.manual_seed(0)
    model = build_model(hidden_size=16, fallback=True, use_gatv2=False)
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-2)
    criterion = nn.BCEWithLogitsLoss()
    batch = next(iter(_loader(fixtures_dir)))

    before = next(p for p in model.parameters() if p.requires_grad).clone()
    optimizer.zero_grad()
    loss = criterion(model.forward_batch(batch), batch["labels"])
    loss.backward()
    optimizer.step()
    after = next(p for p in model.parameters() if p.requires_grad)

    assert torch.isfinite(loss)
    assert float(loss.item()) >= 0.0
    # At least one parameter changed after the optimizer step.
    assert not torch.allclose(before, after)


def test_loss_decreases_over_several_steps(fixtures_dir: Path):
    torch.manual_seed(0)
    model = build_model(hidden_size=16, fallback=True, use_gatv2=False)
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-2)
    criterion = nn.BCEWithLogitsLoss()
    batch = next(iter(_loader(fixtures_dir)))

    first = None
    last = None
    for _ in range(20):
        optimizer.zero_grad()
        loss = criterion(model.forward_batch(batch), batch["labels"])
        loss.backward()
        optimizer.step()
        if first is None:
            first = float(loss.item())
        last = float(loss.item())
    # Overfitting a tiny batch should reduce the loss.
    assert last < first
