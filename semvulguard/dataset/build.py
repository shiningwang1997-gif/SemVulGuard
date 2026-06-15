"""Dataset build CLI.

Normalizes a raw dataset file into a ``SampleRecord`` JSONL manifest, optionally
deduplicating and (re)assigning splits, then prints basic statistics.

Example::

    python -m semvulguard.dataset.build \
        --dataset devign \
        --input tests/fixtures/datasets/devign_sample.jsonl \
        --output artifacts/sample_manifest.jsonl \
        --split random
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from semvulguard.dataset.base import DatasetLoader
from semvulguard.dataset.bigvul import BigVulLoader
from semvulguard.dataset.dedup import deduplicate_samples
from semvulguard.dataset.devign import DevignLoader
from semvulguard.dataset.diversevul import DiverseVulLoader
from semvulguard.dataset.split import assign_random_split, assign_time_split
from semvulguard.schemas.records import SampleRecord
from semvulguard.utils.jsonl import write_jsonl
from semvulguard.utils.logging import get_logger

LOGGER = get_logger("semvulguard.dataset.build")

LOADERS: dict[str, type[DatasetLoader]] = {
    "devign": DevignLoader,
    "bigvul": BigVulLoader,
    "diversevul": DiverseVulLoader,
}


def build_manifest(
    dataset: str,
    input_path: Path,
    split: str = "keep",
    dedup: str = "none",
    seed: int = 42,
) -> tuple[list[SampleRecord], dict[str, str]]:
    """Load, optionally dedup, and (re)split a dataset into SampleRecords.

    Returns the normalized samples and the loader's ``code_lookup`` mapping.
    """
    if dataset not in LOADERS:
        raise ValueError(
            f"unknown dataset {dataset!r}; choose from {sorted(LOADERS)}"
        )
    loader = LOADERS[dataset]()
    samples = loader.load(Path(input_path))

    if dedup != "none":
        before = len(samples)
        samples = deduplicate_samples(samples, loader.code_lookup, mode=dedup)
        LOGGER.info("dedup (%s): %d -> %d samples", dedup, before, len(samples))

    if split == "random":
        samples = assign_random_split(samples, seed=seed)
    elif split == "time":
        samples = assign_time_split(samples)
    elif split != "keep":
        raise ValueError(f"unknown split mode {split!r}")

    return samples, loader.code_lookup


def compute_stats(samples: list[SampleRecord]) -> dict:
    """Compute summary statistics for a list of samples."""
    vulnerable = sum(1 for s in samples if s.label == 1)
    split_counts = Counter(s.split for s in samples)
    cwe_counts: Counter[str] = Counter()
    for sample in samples:
        cwe_counts.update(sample.cwe)
    return {
        "total": len(samples),
        "vulnerable": vulnerable,
        "benign": len(samples) - vulnerable,
        "splits": dict(split_counts),
        "cwe": dict(cwe_counts),
    }


def format_stats(stats: dict) -> str:
    """Render statistics as a human-readable block."""
    lines = [
        f"total samples : {stats['total']}",
        f"vulnerable    : {stats['vulnerable']}",
        f"benign        : {stats['benign']}",
        "split counts  :",
    ]
    for name in ("train", "valid", "test", "unknown"):
        if name in stats["splits"]:
            lines.append(f"  {name:<8}: {stats['splits'][name]}")
    lines.append("cwe counts    :")
    if stats["cwe"]:
        for cwe, count in sorted(stats["cwe"].items()):
            lines.append(f"  {cwe:<12}: {count}")
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="semvulguard.dataset.build",
        description="Normalize a raw dataset into a SampleRecord JSONL manifest.",
    )
    parser.add_argument(
        "--dataset",
        required=True,
        choices=sorted(LOADERS),
        help="source dataset format",
    )
    parser.add_argument(
        "--input", required=True, type=Path, help="path to the raw dataset file"
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="path to write the JSONL manifest"
    )
    parser.add_argument(
        "--split",
        default="keep",
        choices=["keep", "random", "time"],
        help="split assignment strategy (default: keep existing)",
    )
    parser.add_argument(
        "--dedup",
        default="none",
        choices=["none", "exact", "normalized"],
        help="deduplication strategy (default: none)",
    )
    parser.add_argument(
        "--seed", default=42, type=int, help="seed for random split"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    samples, _ = build_manifest(
        dataset=args.dataset,
        input_path=args.input,
        split=args.split,
        dedup=args.dedup,
        seed=args.seed,
    )
    n = write_jsonl(args.output, samples)
    LOGGER.info("wrote %d samples -> %s", n, args.output)
    print(format_stats(compute_stats(samples)))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
