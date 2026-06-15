"""Graph encoder over program-graph slices.

Two modes, selected at construction and degrading gracefully:

* **GATv2 mode** — when ``torch_geometric`` is installed and ``use_gatv2`` is
  set, a 2-layer ``GATv2Conv`` stack with attentive node updates.
* **Fallback mode** — a 2-layer node MLP followed by mean pooling per graph.

Both consume ``(node_features, edge_index, batch_index)`` and return a
``[num_graphs, hidden_size]`` tensor. ``batch_index[i]`` gives the graph id of
node ``i`` (the standard PyG mini-batch convention).
"""

from __future__ import annotations

import torch
from torch import nn


def _try_import_gatv2():
    """Return ``GATv2Conv`` if torch_geometric is installed, else None."""
    try:
        from torch_geometric.nn import GATv2Conv  # noqa: PLC0415

        return GATv2Conv
    except Exception:  # pragma: no cover - environment dependent
        return None


def _mean_pool(
    node_emb: torch.Tensor, batch_index: torch.Tensor, num_graphs: int
) -> torch.Tensor:
    """Mean-pool node embeddings into one vector per graph."""
    hidden = node_emb.size(-1)
    out = torch.zeros(num_graphs, hidden, device=node_emb.device)
    counts = torch.zeros(num_graphs, 1, device=node_emb.device)
    out.index_add_(0, batch_index, node_emb)
    ones = torch.ones(node_emb.size(0), 1, device=node_emb.device)
    counts.index_add_(0, batch_index, ones)
    return out / counts.clamp(min=1.0)


class GraphEncoder(nn.Module):
    """Encode batched program graphs into per-graph vectors."""

    def __init__(
        self,
        node_feature_size: int,
        hidden_size: int = 256,
        use_gatv2: bool = True,
        heads: int = 4,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.node_feature_size = node_feature_size
        self.hidden_size = hidden_size

        gatv2 = _try_import_gatv2() if use_gatv2 else None
        self.uses_gatv2 = gatv2 is not None

        if self.uses_gatv2:
            # Two GATv2 layers; first is multi-head (concat), second averages.
            self.conv1 = gatv2(
                node_feature_size, hidden_size, heads=heads, dropout=dropout
            )
            self.conv2 = gatv2(
                hidden_size * heads,
                hidden_size,
                heads=1,
                concat=False,
                dropout=dropout,
            )
            self.act = nn.ELU()
        else:
            # Fallback node MLP + mean pooling.
            self.mlp = nn.Sequential(
                nn.Linear(node_feature_size, hidden_size),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_size, hidden_size),
            )

    def forward(
        self,
        node_features: torch.Tensor,
        edge_index: torch.Tensor,
        batch_index: torch.Tensor,
    ) -> torch.Tensor:
        # Determine graph count even when some graphs have no nodes.
        if batch_index.numel() > 0:
            num_graphs = int(batch_index.max().item()) + 1
        else:
            num_graphs = 0

        if node_features.numel() == 0 or num_graphs == 0:
            # No nodes anywhere: return zeros for each requested graph.
            return torch.zeros(max(num_graphs, 0), self.hidden_size)

        if self.uses_gatv2:
            x = self.act(self.conv1(node_features, edge_index))
            x = self.conv2(x, edge_index)
        else:
            x = self.mlp(node_features)

        return _mean_pool(x, batch_index, num_graphs)


__all__ = ["GraphEncoder"]
