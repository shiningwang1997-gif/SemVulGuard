"""Phase 2: normalize the Devign dataset into a SampleRecord manifest.

Devign ships as a single JSON *array* (`dataset.json`) with fields
`project / commit_id / target / func`. The existing `DevignLoader` expects JSONL
and mints `devign_<idx>` ids from an `idx`/`id` field. We therefore:

  1. stream the JSON array, inject a stable 0-based `idx` per row,
  2. feed each row through the unchanged `DevignLoader._normalize`,
  3. validate every produced record against the `SampleRecord` schema,
  4. write `manifest_full.jsonl`, a per-sample code file (`<sample_id>.c`) so the
     Feature Builder can locate the function source, and `skipped_samples.jsonl`.

Deterministic: order follows the source file; ids are `devign_<idx>`.
"""

from __future__ import annotations

import json
from pathlib import Path

from semvulguard.dataset.devign import DevignLoader
from semvulguard.schemas.records import SampleRecord
from semvulguard.utils.jsonl import write_jsonl

RAW = Path("../experiment/devign-master/data/raw/dataset.json")
OUT_DIR = Path("artifacts/experiments/devign")
MANIFEST = OUT_DIR / "manifest_full.jsonl"
CODE_DIR = OUT_DIR / "code_full"
SKIPPED = OUT_DIR / "skipped_samples.jsonl"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CODE_DIR.mkdir(parents=True, exist_ok=True)

    with RAW.open(encoding="utf-8") as fh:
        rows = json.load(fh)
    assert isinstance(rows, list), "Devign dataset.json must be a JSON array"

    loader = DevignLoader()
    records: list[SampleRecord] = []
    skipped: list[dict] = []
    seen_ids: set[str] = set()

    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            skipped.append({"index": idx, "reason": "row is not an object"})
            continue
        row = dict(row)
        row.setdefault("idx", idx)  # mint a stable id when none is present
        code = row.get("func") or row.get("function") or row.get("function_code")
        if not code or not str(code).strip():
            skipped.append({"index": idx, "reason": "empty/missing function code"})
            continue
        try:
            rec = loader._normalize(row)
            # re-validate explicitly against the schema contract
            rec = SampleRecord.model_validate(rec.model_dump())
        except Exception as exc:  # schema or normalization failure
            skipped.append(
                {"index": idx, "reason": f"{type(exc).__name__}: {exc}"}
            )
            continue
        if rec.sample_id in seen_ids:
            skipped.append(
                {"index": idx, "sample_id": rec.sample_id, "reason": "duplicate sample_id"}
            )
            continue
        seen_ids.add(rec.sample_id)
        records.append(rec)
        # persist code for the Feature Builder (<sample_id>.c convention)
        (CODE_DIR / f"{rec.sample_id}.c").write_text(
            loader.code_lookup[rec.sample_id], encoding="utf-8"
        )

    n = write_jsonl(MANIFEST, records)
    write_jsonl(SKIPPED, skipped)

    pos = sum(1 for r in records if r.label == 1)
    print(f"devign: {len(rows)} raw rows -> {n} valid records "
          f"({pos} vulnerable / {len(records) - pos} benign), "
          f"{len(skipped)} skipped")
    print(f"manifest: {MANIFEST}")
    print(f"code dir: {CODE_DIR} ({len(list(CODE_DIR.glob('*.c')))} files)")
    print(f"skipped : {SKIPPED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
