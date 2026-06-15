"""Dataset & labeling pipeline.

Loads raw Devign/BigVul/DiverseVul-style inputs and normalizes them into the
canonical :class:`SampleRecord` manifest, with optional deduplication and
train/valid/test split assignment.
"""

from semvulguard.dataset.base import DatasetLoader
from semvulguard.dataset.bigvul import BigVulLoader
from semvulguard.dataset.dedup import (
    deduplicate_samples,
    exact_hash,
    normalized_code_hash,
)
from semvulguard.dataset.devign import DevignLoader
from semvulguard.dataset.diversevul import DiverseVulLoader
from semvulguard.dataset.split import assign_random_split, assign_time_split

__all__ = [
    "DatasetLoader",
    "DevignLoader",
    "BigVulLoader",
    "DiverseVulLoader",
    "exact_hash",
    "normalized_code_hash",
    "deduplicate_samples",
    "assign_random_split",
    "assign_time_split",
]
