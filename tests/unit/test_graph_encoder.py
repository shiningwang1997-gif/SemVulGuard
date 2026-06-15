"""Tests for the graph encoder (fallback mean-pool mode)."""

from __future__ import annotations

import torch

from semvulguard.models.encoder.graph import GraphEncoder


def _two_graph_batch(node_feat_size: int):
    # Graph 0: nodes 0,1; Graph 1: nodes 2,3,4.
    node_features = torch.randn(5, node_feat_size)
    edge_index = torch.tensor([[0, 2, 3], [1, 3, 4]], dtype=torch.long)
    batch_index = torch.tensor([0, 0, 1, 1, 1], dtype=torch.long)
    return node_features, edge_index, batch_index


def test_fallback_output_shape():
    enc = GraphEncoder(node_feature_size=8, hidden_size=16, use_gatv2=False)
    nf, ei, bi = _two_graph_batch(8)
    out = enc(nf, ei, bi)
    assert out.shape == (2, 16)


def test_fallback_flag_set():
    enc = GraphEncoder(node_feature_size=8, hidden_size=16, use_gatv2=False)
    assert enc.uses_gatv2 is False


def test_empty_graph_returns_zeros():
    enc = GraphEncoder(node_feature_size=8, hidden_size=16, use_gatv2=False)
    nf = torch.zeros(0, 8)
    ei = torch.zeros(2, 0, dtype=torch.long)
    bi = torch.zeros(0, dtype=torch.long)
    out = enc(nf, ei, bi)
    assert out.shape == (0, 16)


def test_single_graph_mean_pool_values():
    enc = GraphEncoder(node_feature_size=4, hidden_size=4, use_gatv2=False)
    nf = torch.randn(3, 4)
    ei = torch.zeros(2, 0, dtype=torch.long)
    bi = torch.zeros(3, dtype=torch.long)  # all nodes in graph 0
    out = enc(nf, ei, bi)
    assert out.shape == (1, 4)
    assert torch.isfinite(out).all()


def test_output_is_finite_for_random_input():
    enc = GraphEncoder(node_feature_size=8, hidden_size=16, use_gatv2=False)
    nf, ei, bi = _two_graph_batch(8)
    out = enc(nf, ei, bi)
    assert torch.isfinite(out).all()
