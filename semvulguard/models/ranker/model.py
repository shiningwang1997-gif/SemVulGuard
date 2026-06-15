"""Candidate ranker: a thin classification head over the hybrid encoder."""

from __future__ import annotations

import torch
from torch import nn

from semvulguard.models.encoder.hybrid import HybridCodeEncoder


class CandidateRanker(nn.Module):
    """Score samples by vulnerability risk.

    Wraps a :class:`HybridCodeEncoder` with a small MLP head that emits one
    logit per sample. Train with :class:`torch.nn.BCEWithLogitsLoss`; apply a
    sigmoid at inference to obtain a risk probability.
    """

    def __init__(
        self, encoder: HybridCodeEncoder, hidden_size: int = 256
    ) -> None:
        super().__init__()
        self.encoder = encoder
        self.head = nn.Sequential(
            nn.Linear(encoder.hidden_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_size, 1),
        )

    def forward(
        self,
        sequence_texts: list[str],
        graph_batch: dict,
        static_vectors: torch.Tensor,
    ) -> torch.Tensor:
        """Return a ``[batch_size]`` logit tensor."""
        embedding = self.encoder(sequence_texts, graph_batch, static_vectors)
        return self.head(embedding).squeeze(-1)

    def forward_batch(self, batch: dict) -> torch.Tensor:
        """Convenience: run ``forward`` on a ``collate_fn`` batch dict."""
        return self.forward(
            batch["sequence_texts"], batch, batch["static_vectors"]
        )


__all__ = ["CandidateRanker"]
