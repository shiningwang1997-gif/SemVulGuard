"""Feature vectorization and batching for the ranker.

:class:`FeatureDataset` reads a ``FeatureRecord`` JSONL file and turns each
record into model-ready tensors:

* ``sequence_text`` — the function source (encoded later by the sequence model);
* ``node_features`` — a fixed-width numeric matrix ``[num_nodes, NODE_FEATURE_SIZE]``;
* ``edge_index`` — a ``[2, num_edges]`` long tensor (PyG convention);
* ``static_vector`` — a fixed-width numeric vector of summary features.

Node and static dimensions are fixed constants so a checkpoint trained on one
shard stays compatible at inference. ``collate_fn`` packs variable-size graphs
into one disjoint batch with a ``batch_index`` mapping nodes to graphs.
"""

from __future__ import annotations

import re
import zlib
from pathlib import Path

import torch
from torch.utils.data import Dataset

from semvulguard.schemas.features import FeatureNode, FeatureRecord
from semvulguard.utils.jsonl import read_models

# -- fixed feature layout ---------------------------------------------------

NODE_TYPE_BUCKETS = 16
CODE_HASH_DIM = 16
STATIC_FLAG_KEYS = (
    "is_alert_line",
    "is_trace_line",
    "is_source_like",
    "is_sink_like",
)
# node feature = type one-hot | line_index norm | static flags | code hash bag
NODE_FEATURE_SIZE = (
    NODE_TYPE_BUCKETS + 1 + len(STATIC_FLAG_KEYS) + CODE_HASH_DIM
)

STATIC_FEATURE_KEYS = (
    "alert_count",
    "trace_line_count",
    "unique_query_count",
    "has_codeql_alert",
    "max_severity_score",
    "function_line_count",
    "graph_node_count",
    "graph_edge_count",
    "dangerous_api_count",
)
STATIC_VECTOR_SIZE = len(STATIC_FEATURE_KEYS)

_TOKEN_SPLIT = re.compile(r"[A-Za-z_]\w*|\d+|[^\s\w]")


def _stable_hash(text: str) -> int:
    return zlib.crc32(text.encode("utf-8"))


def _node_feature_vector(node: FeatureNode) -> list[float]:
    """Build the fixed-width numeric vector for one graph node."""
    vec = [0.0] * NODE_FEATURE_SIZE

    # node_type as a hashed one-hot bucket.
    bucket = _stable_hash(node.node_type) % NODE_TYPE_BUCKETS
    vec[bucket] = 1.0

    offset = NODE_TYPE_BUCKETS
    # line_index normalized (cap at 1.0 over a typical function length).
    if node.line_index is not None:
        vec[offset] = min(node.line_index / 100.0, 1.0)
    offset += 1

    # static flags in a stable order.
    for i, key in enumerate(STATIC_FLAG_KEYS):
        vec[offset + i] = float(node.static_flags.get(key, 0))
    offset += len(STATIC_FLAG_KEYS)

    # bag of hashed code tokens (normalized counts).
    tokens = _TOKEN_SPLIT.findall(node.code or "")
    if tokens:
        for tok in tokens:
            vec[offset + _stable_hash(tok) % CODE_HASH_DIM] += 1.0
        total = float(len(tokens))
        for j in range(CODE_HASH_DIM):
            vec[offset + j] /= total
    return vec


def _static_vector(static_features: dict) -> list[float]:
    """Extract the fixed-order numeric static-feature vector."""
    vec = [0.0] * STATIC_VECTOR_SIZE
    for i, key in enumerate(STATIC_FEATURE_KEYS):
        value = static_features.get(key, 0)
        if isinstance(value, bool):
            vec[i] = float(value)
        elif isinstance(value, (int, float)):
            vec[i] = float(value)
    return vec


def vectorize_record(record: FeatureRecord) -> dict:
    """Turn a :class:`FeatureRecord` into tensors and plain fields."""
    if record.nodes:
        node_features = torch.tensor(
            [_node_feature_vector(n) for n in record.nodes],
            dtype=torch.float32,
        )
    else:
        node_features = torch.zeros((0, NODE_FEATURE_SIZE), dtype=torch.float32)

    if record.edges:
        edge_index = torch.tensor(
            [[e.source for e in record.edges], [e.target for e in record.edges]],
            dtype=torch.long,
        )
    else:
        edge_index = torch.zeros((2, 0), dtype=torch.long)

    return {
        "sample_id": record.sample_id,
        "label": int(record.label),
        "sequence_text": record.function_code,
        "node_features": node_features,
        "edge_index": edge_index,
        "static_vector": torch.tensor(
            _static_vector(record.static_features), dtype=torch.float32
        ),
        "metadata": record.metadata,
    }


class FeatureDataset(Dataset):
    """A torch ``Dataset`` over a ``FeatureRecord`` JSONL file."""

    def __init__(self, features_path: str | Path) -> None:
        self.records = read_models(Path(features_path), FeatureRecord)
        self.items = [vectorize_record(r) for r in self.records]

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, idx: int) -> dict:
        return self.items[idx]


def collate_fn(batch: list[dict]) -> dict:
    """Collate variable-size graphs into one disjoint batch.

    Node features are concatenated; edge indices are offset per graph; a
    ``batch_index`` maps each node to its graph position in the batch.
    """
    sequence_texts = [item["sequence_text"] for item in batch]
    sample_ids = [item["sample_id"] for item in batch]
    labels = torch.tensor([item["label"] for item in batch], dtype=torch.float32)
    static_vectors = torch.stack([item["static_vector"] for item in batch])
    metadata = [item["metadata"] for item in batch]

    node_chunks: list[torch.Tensor] = []
    edge_chunks: list[torch.Tensor] = []
    batch_index_chunks: list[torch.Tensor] = []
    node_offset = 0
    for graph_id, item in enumerate(batch):
        nf = item["node_features"]
        n = nf.size(0)
        node_chunks.append(nf)
        if item["edge_index"].numel() > 0:
            edge_chunks.append(item["edge_index"] + node_offset)
        batch_index_chunks.append(
            torch.full((n,), graph_id, dtype=torch.long)
        )
        node_offset += n

    node_features = (
        torch.cat(node_chunks, dim=0)
        if node_chunks
        else torch.zeros((0, NODE_FEATURE_SIZE), dtype=torch.float32)
    )
    edge_index = (
        torch.cat(edge_chunks, dim=1)
        if edge_chunks
        else torch.zeros((2, 0), dtype=torch.long)
    )
    batch_index = (
        torch.cat(batch_index_chunks, dim=0)
        if batch_index_chunks
        else torch.zeros((0,), dtype=torch.long)
    )

    return {
        "sample_ids": sample_ids,
        "labels": labels,
        "sequence_texts": sequence_texts,
        "node_features": node_features,
        "edge_index": edge_index,
        "batch_index": batch_index,
        "static_vectors": static_vectors,
        "metadata": metadata,
        "num_graphs": len(batch),
    }


__all__ = [
    "FeatureDataset",
    "collate_fn",
    "vectorize_record",
    "NODE_FEATURE_SIZE",
    "STATIC_VECTOR_SIZE",
    "STATIC_FEATURE_KEYS",
]
