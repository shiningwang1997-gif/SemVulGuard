"""Hybrid (sequence + graph + static) code encoder.

Fuses three channels into one embedding per sample:

* a :class:`SequenceEncoder` over the function source,
* a :class:`GraphEncoder` over the program-graph slice, and
* a linear projection of the static-feature vector.

The three are concatenated and projected back to ``hidden_size``. The graph
channel is robust to empty graphs (it emits zero vectors), so samples without a
slice still produce a valid embedding.
"""

from __future__ import annotations

import torch
from torch import nn

from semvulguard.models.encoder.graph import GraphEncoder
from semvulguard.models.encoder.sequence import SequenceEncoder


class HybridCodeEncoder(nn.Module):
    """Combine sequence, graph, and static channels into one embedding."""

    def __init__(
        self,
        hidden_size: int = 256,
        node_feature_size: int | None = None,
        static_vector_size: int | None = None,
        model_name: str | None = None,
        fallback: bool = True,
        use_gatv2: bool = True,
    ) -> None:
        super().__init__()
        self.hidden_size = hidden_size

        # Resolve the dataset feature layout lazily to avoid an import cycle
        # (ranker.dataset pulls in the ranker package, which imports this class).
        if node_feature_size is None or static_vector_size is None:
            from semvulguard.models.ranker.dataset import (
                NODE_FEATURE_SIZE,
                STATIC_VECTOR_SIZE,
            )

            node_feature_size = node_feature_size or NODE_FEATURE_SIZE
            static_vector_size = static_vector_size or STATIC_VECTOR_SIZE
        self.sequence_encoder = SequenceEncoder(
            model_name=model_name, hidden_size=hidden_size, fallback=fallback
        )
        self.graph_encoder = GraphEncoder(
            node_feature_size=node_feature_size,
            hidden_size=hidden_size,
            use_gatv2=use_gatv2,
        )
        self.static_proj = nn.Linear(static_vector_size, hidden_size)

        # Fuse the three hidden_size channels back down to hidden_size.
        self.fusion = nn.Sequential(
            nn.Linear(hidden_size * 3, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
        )

    def forward(
        self,
        sequence_texts: list[str],
        graph_batch: dict,
        static_vectors: torch.Tensor,
    ) -> torch.Tensor:
        """Return a ``[batch_size, hidden_size]`` hybrid embedding.

        ``graph_batch`` provides ``node_features``, ``edge_index``,
        ``batch_index``, and ``num_graphs`` (as produced by ``collate_fn``).
        """
        seq_emb = self.sequence_encoder(sequence_texts)

        num_graphs = graph_batch.get("num_graphs", len(sequence_texts))
        graph_emb = self.graph_encoder(
            graph_batch["node_features"],
            graph_batch["edge_index"],
            graph_batch["batch_index"],
        )
        # Pad graph embeddings if some trailing graphs had no nodes.
        if graph_emb.size(0) < num_graphs:
            pad = torch.zeros(
                num_graphs - graph_emb.size(0),
                self.hidden_size,
                device=graph_emb.device,
            )
            graph_emb = torch.cat([graph_emb, pad], dim=0)

        static_emb = self.static_proj(static_vectors)

        fused = torch.cat([seq_emb, graph_emb, static_emb], dim=-1)
        return self.fusion(fused)


__all__ = ["HybridCodeEncoder"]
