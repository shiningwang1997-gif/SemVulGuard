"""Tests for FeatureDataset vectorization and the collate function."""

from __future__ import annotations

from pathlib import Path

import torch

from semvulguard.models.ranker.dataset import (
    NODE_FEATURE_SIZE,
    STATIC_VECTOR_SIZE,
    FeatureDataset,
    collate_fn,
)


def _dataset(fixtures_dir: Path) -> FeatureDataset:
    return FeatureDataset(fixtures_dir / "model" / "features.jsonl")


def test_dataset_loads_fixture(fixtures_dir: Path):
    ds = _dataset(fixtures_dir)
    assert len(ds) == 4


def test_item_fields_and_shapes(fixtures_dir: Path):
    ds = _dataset(fixtures_dir)
    item = ds[0]
    assert item["sample_id"] == "s1"
    assert item["label"] == 1
    assert isinstance(item["sequence_text"], str)
    assert item["node_features"].shape == (4, NODE_FEATURE_SIZE)
    assert item["edge_index"].shape == (2, 3)
    assert item["static_vector"].shape == (STATIC_VECTOR_SIZE,)


def test_item_without_graph_has_empty_tensors(fixtures_dir: Path):
    ds = _dataset(fixtures_dir)
    # s3 is the third record and has no nodes/edges.
    item = ds[2]
    assert item["sample_id"] == "s3"
    assert item["node_features"].shape == (0, NODE_FEATURE_SIZE)
    assert item["edge_index"].shape == (2, 0)


def test_collate_disjoint_batch(fixtures_dir: Path):
    ds = _dataset(fixtures_dir)
    batch = collate_fn([ds[0], ds[1]])
    # 4 + 2 nodes; 3 + 1 edges.
    assert batch["node_features"].shape == (6, NODE_FEATURE_SIZE)
    assert batch["edge_index"].shape == (2, 4)
    assert batch["num_graphs"] == 2
    assert batch["labels"].tolist() == [1.0, 0.0]


def test_collate_edge_offset_applied(fixtures_dir: Path):
    ds = _dataset(fixtures_dir)
    batch = collate_fn([ds[0], ds[1]])
    # Second graph's single edge (0->1) is offset by 4 nodes -> (4->5).
    assert batch["edge_index"][:, -1].tolist() == [4, 5]


def test_collate_batch_index_maps_nodes_to_graphs(fixtures_dir: Path):
    ds = _dataset(fixtures_dir)
    batch = collate_fn([ds[0], ds[1]])
    assert batch["batch_index"].tolist() == [0, 0, 0, 0, 1, 1]


def test_collate_handles_graphless_sample(fixtures_dir: Path):
    ds = _dataset(fixtures_dir)
    # s3 (index 2) has no graph; batch with s1.
    batch = collate_fn([ds[2], ds[0]])
    assert batch["num_graphs"] == 2
    # Only s1's 4 nodes appear; all map to graph 1.
    assert batch["node_features"].shape == (4, NODE_FEATURE_SIZE)
    assert batch["batch_index"].tolist() == [1, 1, 1, 1]


def test_static_vector_values(fixtures_dir: Path):
    ds = _dataset(fixtures_dir)
    item = ds[0]
    # First static key is alert_count == 1 for s1.
    assert item["static_vector"][0].item() == 1.0
    assert torch.isfinite(item["static_vector"]).all()
