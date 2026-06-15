"""Phase 2: normalize Devign / BigVul / DiverseVul into SampleRecord manifests.

Reuses the existing dataset loaders' ``_normalize`` (DevignLoader, BigVulLoader,
DiverseVulLoader) so the canonical SampleRecord semantics are unchanged. Streams
the large files line-by-line (DiverseVul JSONL, BigVul CSV) to stay memory-bound;
Devign's 61 MB JSON array is loaded whole.

Per dataset we write, under artifacts/experiments/formal_multidataset_v1/{ds}/:
  * manifest_full.jsonl       -- every valid SampleRecord
  * code_full.jsonl           -- {sample_id, code} mapping (one file, not 330k)
  * skipped_samples.jsonl     -- rows dropped, with reasons

The subset step (Phase 3) materializes only the selected subset's <sample_id>.c
files into code/ for the FeatureBuilder, so we never write a code file per row
for the 330k-record DiverseVul corpus.

Deterministic: ids are minted from a stable per-row index.
Labels are never fabricated; benign samples are never fabricated. Rows lacking
usable function code are skipped (recorded), never guessed.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from semvulguard.dataset.bigvul import BigVulLoader
from semvulguard.dataset.devign import DevignLoader
from semvulguard.dataset.diversevul import DiverseVulLoader
from semvulguard.schemas.records import SampleRecord
from semvulguard.utils.jsonl import write_jsonl

from scripts.experiments.formal.config import RAW_PATHS, ROOT

csv.field_size_limit(sys.maxsize)


def _prep_out(ds: str) -> tuple[Path, Path, Path, Path]:
    ddir = ROOT / ds
    ddir.mkdir(parents=True, exist_ok=True)
    return ddir, ddir / "manifest_full.jsonl", ddir / "code_full.jsonl", ddir / "skipped_samples.jsonl"


def _normalize_stream(ds: str, loader, rows_iter):
    """Drive a loader._normalize over an iterator of (index, raw_row) dicts.

    ``rows_iter`` yields already-prepared raw dicts (with id/cwe keys injected as
    needed). Returns (records, skipped, code_lookup).
    """
    records: list[SampleRecord] = []
    skipped: list[dict] = []
    seen: set[str] = set()
    code_lookup: dict[str, str] = {}

    for idx, row in rows_iter:
        code = row.get("__code__")
        if not code or not str(code).strip():
            skipped.append({"index": idx, "reason": "empty/missing function code"})
            continue
        row.pop("__code__", None)
        try:
            rec = loader._normalize(row)
            rec = SampleRecord.model_validate(rec.model_dump())
        except Exception as exc:  # schema/normalization failure
            skipped.append({"index": idx, "reason": f"{type(exc).__name__}: {exc}"})
            continue
        if rec.sample_id in seen:
            skipped.append({"index": idx, "sample_id": rec.sample_id,
                            "reason": "duplicate sample_id"})
            continue
        seen.add(rec.sample_id)
        records.append(rec)
        code_lookup[rec.sample_id] = loader.code_lookup.get(rec.sample_id, code)

    return records, skipped, code_lookup


# -- per-dataset row preparation ---------------------------------------------

def _devign_rows():
    data = json.load(RAW_PATHS["devign"].open(encoding="utf-8"))
    assert isinstance(data, list)
    for idx, row in enumerate(data):
        if not isinstance(row, dict):
            continue
        r = dict(row)
        r.setdefault("idx", idx)
        r["__code__"] = r.get("func") or r.get("function") or r.get("function_code")
        yield idx, r


def _bigvul_rows():
    with RAW_PATHS["bigvul"].open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for idx, row in enumerate(reader):
            r = dict(row)
            # stable id from the BigVul `index` column (fallback to row idx)
            r["id"] = r.get("index") or idx
            # map BigVul's `CWE ID` column into the loader's `cwe` alias
            cwe = (r.get("CWE ID") or "").strip()
            r["cwe"] = cwe if cwe and cwe.lower() != "none" else None
            r["__code__"] = r.get("func_before") or r.get("processed_func")
            yield idx, r


def _diversevul_rows():
    with RAW_PATHS["diversevul"].open(encoding="utf-8") as fh:
        for idx, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                yield idx, {"__code__": None}  # recorded as skipped
                continue
            r = dict(row)
            r.setdefault("idx", idx)  # DiverseVul has no native row id
            r["__code__"] = r.get("func") or r.get("function") or r.get("function_code")
            yield idx, r


LOADERS = {
    "devign": (DevignLoader, _devign_rows),
    "bigvul": (BigVulLoader, _bigvul_rows),
    "diversevul": (DiverseVulLoader, _diversevul_rows),
}


def normalize_one(ds: str) -> dict:
    loader_cls, rows_fn = LOADERS[ds]
    loader = loader_cls()
    ddir, manifest, code_path, skipped_path = _prep_out(ds)

    records, skipped, code_lookup = _normalize_stream(ds, loader, rows_fn())

    # write code mapping as a single JSONL (sample_id -> code)
    with code_path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(
                {"sample_id": rec.sample_id, "code": code_lookup.get(rec.sample_id, "")},
                ensure_ascii=False) + "\n")

    n = write_jsonl(manifest, records)
    write_jsonl(skipped_path, skipped)

    pos = sum(1 for r in records if r.label == 1)
    summary = {
        "dataset": ds, "valid": n, "vulnerable": pos, "benign": n - pos,
        "skipped": len(skipped), "manifest": str(manifest),
        "code_map": str(code_path),
    }
    print(f"{ds}: {n} valid ({pos} vuln / {n - pos} benign), "
          f"{len(skipped)} skipped -> {manifest}")
    return summary


def main(argv: list[str] | None = None) -> int:
    targets = argv if argv else list(LOADERS)
    out = [normalize_one(ds) for ds in targets]
    (ROOT / "normalization_summary.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or None))
