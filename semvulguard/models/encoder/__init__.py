"""Dual-channel (sequence + graph) code representation encoder.

Exposes the sequence, graph, and hybrid encoders. Heavy optional dependencies
(transformers, torch_geometric) are imported lazily; the encoders degrade to
fallback modes when they are unavailable.
"""

from semvulguard.models.encoder.graph import GraphEncoder
from semvulguard.models.encoder.hybrid import HybridCodeEncoder
from semvulguard.models.encoder.sequence import SequenceEncoder

__all__ = ["SequenceEncoder", "GraphEncoder", "HybridCodeEncoder"]
