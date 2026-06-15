"""Shared config for the formal multi-dataset experiment (formal_multidataset_v1).

Single source of truth for paths, dataset registry, subset targets, split
ratios, and the seed. Everything downstream imports from here so the pipeline
stays consistent and reproducible.

CRITICAL RULE enforced project-wide: all final scientific metrics are computed
on ``split == "test"`` only. The ranker is fit on the train split alone.
"""

from __future__ import annotations

from pathlib import Path

SEED = 42
ROOT = Path("artifacts/experiments/formal_multidataset_v1")
DATA = Path("../experiment")

SPLIT_RATIOS = (0.7, 0.1, 0.2)  # train / valid / test

# Subset targets (Phase 3). If a dataset has fewer valid samples, use all.
SUBSET_TARGETS = {
    "devign": 3000,
    "bigvul": 1000,
    "diversevul": 1000,
}

# Raw source files (relative to SemVulGuard/ working dir).
RAW_PATHS = {
    "devign": DATA / "devign-master" / "data" / "raw" / "dataset.json",
    "bigvul": DATA / "bigvul_test.csv",
    "diversevul": DATA / "diversevul_20230702.json",
}

DATASETS = ("devign", "bigvul", "diversevul")

# LLM / cost settings.
MODEL = "deepseek-v4-flash"
PRICE_IN_PER_1M = 0.14   # cache-miss input
PRICE_OUT_PER_1M = 0.28  # output
OUT_TOKENS_PER_SAMPLE = 500

# Method matrix.
KS_MOCK = [0, 10, 30, 50]
KS_REAL = [0, 10]
REAL_TOPK = 10


def dataset_dir(ds: str) -> Path:
    return ROOT / ds


__all__ = [
    "SEED", "ROOT", "DATA", "SPLIT_RATIOS", "SUBSET_TARGETS", "RAW_PATHS",
    "DATASETS", "MODEL", "PRICE_IN_PER_1M", "PRICE_OUT_PER_1M",
    "OUT_TOKENS_PER_SAMPLE", "KS_MOCK", "KS_REAL", "REAL_TOPK", "dataset_dir",
]
