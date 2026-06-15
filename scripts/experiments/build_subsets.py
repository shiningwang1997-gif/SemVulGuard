"""Phase 3: build deterministic, label-stratified subsets from full manifests.

For each ready dataset we draw up to ``target`` samples while preserving the
vulnerable/benign ratio of the full manifest as closely as possible. Selection
is deterministic (``random.Random(seed)`` over ids sorted within each class), so
re-runs are byte-identical. Subset code files are symlinked/copied so the Feature
Builder can still resolve ``<sample_id>.c``.

Also emits ``artifacts/experiments/dataset_summary.csv``.
"""

from __future__ import annotations

import csv
import random
import shutil
from collections import Counter
from pathlib import Path

from semvulguard.schemas.records import SampleRecord
from semvulguard.utils.jsonl import read_models, write_jsonl

EXP = Path("artifacts/experiments")
SEED = 42

# dataset -> target subset size. Only datasets with a full manifest are built.
TARGETS = {"devign": 1000, "bigvul": 1000, "diversevul": 500}


def stratified_subset(
    records: list[SampleRecord], target: int, seed: int
) -> list[SampleRecord]:
    """Pick ``target`` records preserving the label ratio, deterministically."""
    if target >= len(records):
        # keep all, in original order
        return list(records)

    by_label: dict[int, list[SampleRecord]] = {0: [], 1: []}
    for r in records:
        by_label[r.label].append(r)

    n_total = len(records)
    # proportional allocation, then fix rounding so the sum == target
    alloc = {
        lab: round(target * len(recs) / n_total) for lab, recs in by_label.items()
    }
    # adjust to hit exactly `target`
    diff = target - sum(alloc.values())
    # bump the larger class first for stability
    order = sorted(by_label, key=lambda lab: -len(by_label[lab]))
    i = 0
    while diff != 0 and order:
        lab = order[i % len(order)]
        if diff > 0 and alloc[lab] < len(by_label[lab]):
            alloc[lab] += 1
            diff -= 1
        elif diff < 0 and alloc[lab] > 0:
            alloc[lab] -= 1
            diff += 1
        i += 1

    rng = random.Random(seed)
    picked: list[SampleRecord] = []
    for lab in (0, 1):
        pool = sorted(by_label[lab], key=lambda r: r.sample_id)
        k = min(alloc[lab], len(pool))
        picked.extend(rng.sample(pool, k))

    # stable output order: by sample_id
    picked.sort(key=lambda r: r.sample_id)
    return picked


def build_one(dataset: str, target: int, summary_rows: list[dict]) -> None:
    ddir = EXP / dataset
    full = ddir / "manifest_full.jsonl"
    if not full.exists():
        # excluded dataset (normalization_error.md present)
        note = "excluded: no manifest_full.jsonl (see normalization_error.md)"
        summary_rows.append(
            {
                "dataset": dataset,
                "full_valid_count": 0,
                "subset_count": 0,
                "vulnerable_count": 0,
                "benign_count": 0,
                "cwe_count": 0,
                "selected_manifest_path": "",
                "skipped_count": 0,
                "notes": note,
            }
        )
        print(f"{dataset}: SKIPPED ({note})")
        return

    records = read_models(full, SampleRecord)
    subset = stratified_subset(records, target, SEED)

    manifest = ddir / "manifest.jsonl"
    write_jsonl(manifest, subset)

    # copy subset code files into code/ for the Feature Builder
    code_full = ddir / "code_full"
    code_sub = ddir / "code"
    if code_sub.exists():
        shutil.rmtree(code_sub)
    code_sub.mkdir(parents=True, exist_ok=True)
    for r in subset:
        src = code_full / f"{r.sample_id}.c"
        if src.exists():
            shutil.copy2(src, code_sub / f"{r.sample_id}.c")

    pos = sum(1 for r in subset if r.label == 1)
    cwe_counter: Counter[str] = Counter()
    for r in subset:
        cwe_counter.update(r.cwe)

    # skipped count from full normalization
    skipped_path = ddir / "skipped_samples.jsonl"
    skipped_count = (
        sum(1 for _ in open(skipped_path)) if skipped_path.exists() else 0
    )

    note = "all valid samples used" if len(subset) == len(records) else (
        f"stratified subset of {len(records)} (seed={SEED})"
    )
    summary_rows.append(
        {
            "dataset": dataset,
            "full_valid_count": len(records),
            "subset_count": len(subset),
            "vulnerable_count": pos,
            "benign_count": len(subset) - pos,
            "cwe_count": len(cwe_counter),
            "selected_manifest_path": str(manifest),
            "skipped_count": skipped_count,
            "notes": note,
        }
    )
    print(f"{dataset}: full={len(records)} subset={len(subset)} "
          f"(vuln={pos}, benign={len(subset)-pos}, cwe_types={len(cwe_counter)})")


def main() -> int:
    summary_rows: list[dict] = []
    for dataset, target in TARGETS.items():
        build_one(dataset, target, summary_rows)

    summary_path = EXP / "dataset_summary.csv"
    cols = [
        "dataset", "full_valid_count", "subset_count", "vulnerable_count",
        "benign_count", "cwe_count", "selected_manifest_path",
        "skipped_count", "notes",
    ]
    with summary_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(summary_rows)
    print(f"wrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
