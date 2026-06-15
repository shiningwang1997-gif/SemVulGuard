"""Config overrides for formal_multidataset_v2_scaled.

This module does NOT redefine the pipeline. Every phase module
(normalize/subset_split/codeql_alerts/ranker/test_only/mock/matrix/cost_preview)
already reads ``ROOT`` / ``SUBSET_TARGETS`` as *module-level globals imported
from ``config``*. The v2 driver (run_v2.py) imports those phase modules and
rebinds their ``ROOT`` / ``SUBSET_TARGETS`` (and a couple of related globals) to
the v2 values below, so the exact same, already-validated code paths run against
the larger subsets and a separate output root.

Nothing about v1 is touched: a different ROOT means v1 artifacts are never
overwritten.

Scaled subset targets (Phase 3). If a dataset has fewer usable samples, all are
used. Devign falls back to 3000 only if 5000 are not available (it has ~27k, so
5000 is used).
"""

from __future__ import annotations

from pathlib import Path

# Same reproducibility knobs as v1.
SEED = 42
SPLIT_RATIOS = (0.7, 0.1, 0.2)  # train / valid / test, stratified per label

# v2 output root — distinct from v1 so nothing is overwritten.
ROOT = Path("artifacts/experiments/formal_multidataset_v2_scaled")

# v1 root (source of the already-normalized full manifests we reuse).
V1_ROOT = Path("artifacts/experiments/formal_multidataset_v1")

# Scaled targets. Devign: 5000 if available else 3000 (it has ~27k -> 5000).
SUBSET_TARGETS = {
    "devign": 5000,
    "bigvul": 5000,
    "diversevul": 5000,
}
DEVIGN_FALLBACK = 3000  # used only if devign has <5000 usable samples

DATASETS = ("devign", "bigvul", "diversevul")

# A separate positive-enriched (balanced) TEST split is materialized for
# analysis ONLY when the natural-distribution test set has fewer than this many
# positives. It is always kept separate from the natural-distribution test and
# clearly labeled. It never fabricates labels and never duplicates samples
# across train/valid/test (it is a strict subset of the natural test split).
MIN_TEST_POS_FOR_STABLE = 50

# Method matrix / mock top-k (real DeepSeek is NOT called in v2).
KS_MOCK = [0, 10, 30, 50]
REAL_TOPK = 50  # what a *future* real run would use; used only for cost preview

# LLM / cost settings (identical pricing to v1 for a comparable preview).
MODEL = "deepseek-v4-flash"
PRICE_IN_PER_1M = 0.14
PRICE_OUT_PER_1M = 0.28
OUT_TOKENS_PER_SAMPLE = 500


def dataset_dir(ds: str) -> Path:
    return ROOT / ds


__all__ = [
    "SEED", "ROOT", "V1_ROOT", "SPLIT_RATIOS", "SUBSET_TARGETS",
    "DEVIGN_FALLBACK", "DATASETS", "MIN_TEST_POS_FOR_STABLE", "KS_MOCK",
    "REAL_TOPK", "MODEL", "PRICE_IN_PER_1M", "PRICE_OUT_PER_1M",
    "OUT_TOKENS_PER_SAMPLE", "dataset_dir",
]
