"""Phase 3: deterministic stratified subset + train/valid/test split.

For each usable dataset we:
  1. draw up to SUBSET_TARGETS[ds] records preserving the vuln/benign ratio
     (deterministic: seeded RNG over ids sorted within each label);
  2. assign a stratified 70/10/20 train/valid/test split per label (seed=42),
     so each split preserves the class balance and re-runs are byte-identical;
  3. write manifest.jsonl (split field populated) and split.jsonl;
  4. materialize the subset's <sample_id>.c code files from code_full.jsonl;
  5. emit dataset_summary.csv and dataset_readiness_report.md.

No native split exists in any of the three datasets (Devign/BigVul/DiverseVul),
so a fresh deterministic split is always created and documented.

CRITICAL: the test split produced here is the ONLY data used for final metrics.
"""

from __future__ import annotations

import csv
import json
import random
from collections import Counter
from pathlib import Path

from semvulguard.schemas.records import SampleRecord
from semvulguard.utils.jsonl import read_models, write_jsonl

from scripts.experiments.formal.config import (
    ROOT,
    SEED,
    SPLIT_RATIOS,
    SUBSET_TARGETS,
)


def stratified_subset(records: list[SampleRecord], target: int, seed: int) -> list[SampleRecord]:
    """Pick ``target`` records preserving label ratio, deterministically."""
    if target >= len(records):
        return list(records)
    by_label: dict[int, list[SampleRecord]] = {0: [], 1: []}
    for r in records:
        by_label[r.label].append(r)
    n_total = len(records)
    alloc = {lab: round(target * len(recs) / n_total) for lab, recs in by_label.items()}
    diff = target - sum(alloc.values())
    order = sorted(by_label, key=lambda lab: -len(by_label[lab]))
    i = 0
    while diff != 0 and order:
        lab = order[i % len(order)]
        if diff > 0 and alloc[lab] < len(by_label[lab]):
            alloc[lab] += 1; diff -= 1
        elif diff < 0 and alloc[lab] > 0:
            alloc[lab] -= 1; diff += 1
        i += 1
    rng = random.Random(seed)
    picked: list[SampleRecord] = []
    for lab in (0, 1):
        pool = sorted(by_label[lab], key=lambda r: r.sample_id)
        picked.extend(rng.sample(pool, min(alloc[lab], len(pool))))
    picked.sort(key=lambda r: r.sample_id)
    return picked


def stratified_split(records: list[SampleRecord], seed: int,
                     ratios: tuple[float, float, float]) -> dict[str, str]:
    """Per-label stratified train/valid/test assignment. Returns id -> split."""
    train_r, valid_r, _ = ratios
    by_label: dict[int, list[str]] = {}
    for r in records:
        by_label.setdefault(r.label, []).append(r.sample_id)
    assignment: dict[str, str] = {}
    for lab in sorted(by_label):
        ids = sorted(by_label[lab])
        rng = random.Random(seed + lab)  # distinct stream per label, still fixed
        rng.shuffle(ids)
        n = len(ids)
        n_train = int(round(n * train_r))
        n_valid = int(round(n * valid_r))
        n_train = min(n_train, n)
        n_valid = min(n_valid, n - n_train)
        for i, sid in enumerate(ids):
            if i < n_train:
                assignment[sid] = "train"
            elif i < n_train + n_valid:
                assignment[sid] = "valid"
            else:
                assignment[sid] = "test"
    return assignment


def _load_code_map(ddir: Path) -> dict[str, str]:
    path = ddir / "code_full.jsonl"
    out: dict[str, str] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            out[o["sample_id"]] = o.get("code", "")
    return out


def build_one(ds: str, summary_rows: list[dict]) -> dict:
    ddir = ROOT / ds
    full = ddir / "manifest_full.jsonl"
    target = SUBSET_TARGETS[ds]

    records = read_models(full, SampleRecord)
    full_count = len(records)
    subset = stratified_subset(records, target, SEED)

    assignment = stratified_split(subset, SEED, SPLIT_RATIOS)
    subset = [s.model_copy(update={"split": assignment[s.sample_id]}) for s in subset]

    manifest = ddir / "manifest.jsonl"
    write_jsonl(manifest, subset)
    split_rows = [{"sample_id": s.sample_id, "split": s.split, "label": s.label}
                  for s in subset]
    write_jsonl(ddir / "split.jsonl", split_rows)

    # materialize subset code files
    code_map = _load_code_map(ddir)
    code_dir = ddir / "code"
    if code_dir.exists():
        for old in code_dir.glob("*.c"):
            old.unlink()
    code_dir.mkdir(parents=True, exist_ok=True)
    missing_code = 0
    for s in subset:
        code = code_map.get(s.sample_id, "")
        if not code:
            missing_code += 1
        (code_dir / f"{s.sample_id}.c").write_text(code, encoding="utf-8")

    pos = sum(1 for s in subset if s.label == 1)
    split_counts = Counter(s.split for s in subset)
    split_pos = {sp: sum(1 for s in subset if s.split == sp and s.label == 1)
                 for sp in ("train", "valid", "test")}
    cwe_counter: Counter[str] = Counter()
    for s in subset:
        cwe_counter.update(s.cwe)
    skipped_path = ddir / "skipped_samples.jsonl"
    skipped_count = sum(1 for _ in skipped_path.open()) if skipped_path.exists() else 0

    note = ("all valid samples used" if len(subset) == full_count
            else f"stratified subset of {full_count} (seed={SEED})")
    note += "; fresh deterministic stratified 70/10/20 split (no native split)"

    summary_rows.append({
        "dataset": ds, "usable": True, "full_valid_count": full_count,
        "subset_count": len(subset), "train_count": split_counts["train"],
        "valid_count": split_counts["valid"], "test_count": split_counts["test"],
        "vulnerable_count": pos, "benign_count": len(subset) - pos,
        "cwe_count": len(cwe_counter), "manifest_path": str(manifest),
        "skipped_count": skipped_count, "notes": note,
    })

    info = {
        "dataset": ds, "full_count": full_count, "subset_count": len(subset),
        "split_counts": dict(split_counts), "split_pos": split_pos,
        "pos": pos, "neg": len(subset) - pos, "cwe_types": len(cwe_counter),
        "missing_code": missing_code,
    }
    print(f"{ds}: full={full_count} subset={len(subset)} "
          f"(vuln={pos}/benign={len(subset)-pos}) "
          f"train={split_counts['train']} valid={split_counts['valid']} "
          f"test={split_counts['test']} cwe_types={len(cwe_counter)} "
          f"missing_code={missing_code}")
    return info


def write_summary_csv(rows: list[dict]) -> None:
    cols = ["dataset", "usable", "full_valid_count", "subset_count",
            "train_count", "valid_count", "test_count", "vulnerable_count",
            "benign_count", "cwe_count", "manifest_path", "skipped_count", "notes"]
    path = ROOT / "dataset_summary.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {path}")


def write_readiness_report(infos: list[dict]) -> None:
    L = ["# Dataset Readiness Report — formal_multidataset_v1 (Phase 3)", "",
         f"- Seed: {SEED} | Split: 70/10/20 stratified per label (fresh, no native split)",
         f"- **Usable datasets: {', '.join(i['dataset'] for i in infos)}**", ""]
    for i in infos:
        sc, sp = i["split_counts"], i["split_pos"]
        L += [f"## {i['dataset']}", "",
              "- Status: **READY ✅**",
              f"- Full valid records: {i['full_count']}",
              f"- Subset: {i['subset_count']} (vuln={i['pos']}, benign={i['neg']}, "
              f"pos_rate={i['pos']/max(1,i['subset_count']):.3f})",
              f"- Split: train={sc.get('train',0)} (pos={sp['train']}), "
              f"valid={sc.get('valid',0)} (pos={sp['valid']}), "
              f"test={sc.get('test',0)} (pos={sp['test']})",
              f"- Distinct CWE types in subset: {i['cwe_types']}",
              f"- Samples missing function code: {i['missing_code']}",
              "- Both classes present in every split: "
              f"{'yes' if all(sp[s] > 0 and sc.get(s,0)-sp[s] > 0 for s in ('train','valid','test')) else 'CHECK'}",
              ""]
    L += ["## Critical rule", "",
          "Final paper-facing metrics are computed on `split == \"test\"` ONLY. "
          "The ranker is fit on the train split alone; valid is used for "
          "threshold/diagnostic only; test is held out until final evaluation.", ""]
    path = ROOT / "dataset_readiness_report.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {path}")


def main(argv: list[str] | None = None) -> int:
    targets = argv if argv else list(SUBSET_TARGETS)
    summary_rows: list[dict] = []
    infos = [build_one(ds, summary_rows) for ds in targets]
    write_summary_csv(summary_rows)
    write_readiness_report(infos)
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:] or None))
