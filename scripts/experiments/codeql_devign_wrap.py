"""Task B1: wrap Devign function-level samples into batched C files for CodeQL.

Devign samples are individual C functions with no buildable repository and a
``file == "unknown"`` manifest. We emit each function into a batch ``.c`` file
(with common headers), recording the exact line span each function occupies so
SARIF alerts can be mapped back to the originating ``sample_id`` by line
containment. Functions that are empty / unusable are skipped and recorded.

This does NOT alter vulnerability logic: each function body is written verbatim.
"""

from __future__ import annotations

import json
from pathlib import Path

FEATURES = Path("artifacts/experiments/devign/features.jsonl")
OUT_ROOT = Path("artifacts/codeql_devign_wrapped")
SRC_DIR = OUT_ROOT / "src"
MAP_DIR = OUT_ROOT / "mapping"
MAPPING_PATH = MAP_DIR / "sample_line_mapping.jsonl"
SKIPPED_PATH = OUT_ROOT / "skipped_samples.jsonl"

BATCH_SIZE = 50  # functions per batch file

HEADER = (
    "#include <stdio.h>\n"
    "#include <stdlib.h>\n"
    "#include <string.h>\n"
    "#include <stdint.h>\n"
    "#include <unistd.h>\n"
    "\n"
)
HEADER_LINES = HEADER.count("\n")  # number of lines consumed by the header block


def _load_features(limit: int | None) -> list[dict]:
    rows = []
    with FEATURES.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def main(limit: int | None = None) -> int:
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    MAP_DIR.mkdir(parents=True, exist_ok=True)
    # Clear any stale batch files from a previous run in this NEW directory.
    for old in SRC_DIR.glob("batch_*.c"):
        old.unlink()

    features = _load_features(limit)

    mapping: list[dict] = []
    skipped: list[dict] = []

    # Partition into batches of usable functions.
    usable = []
    for rec in features:
        sid = rec["sample_id"]
        code = rec.get("function_code") or ""
        if not code.strip():
            skipped.append({"sample_id": sid, "reason": "empty function_code"})
            continue
        nlines = len(code.splitlines())
        if nlines < 2:
            skipped.append({"sample_id": sid, "reason": f"too short ({nlines} lines)"})
            continue
        usable.append(rec)

    batch_idx = 0
    pos_in_batch = 0
    fh = None
    cur_line = 0  # 1-indexed line counter within the current batch file

    def open_batch(idx: int):
        path = SRC_DIR / f"batch_{idx:03d}.c"
        f = path.open("w", encoding="utf-8")
        f.write(HEADER)
        return f, path, HEADER_LINES  # next content starts at HEADER_LINES + 1

    for rec in usable:
        if fh is None or pos_in_batch == BATCH_SIZE:
            if fh is not None:
                fh.close()
                batch_idx += 1
            fh, batch_path, cur_line = open_batch(batch_idx)
            pos_in_batch = 0

        sid = rec["sample_id"]
        code = rec["function_code"]
        if not code.endswith("\n"):
            code += "\n"

        start_line = cur_line + 1
        # Marker comment so the function is greppable; counts as one line.
        marker = f"/* === sample_id={sid} === */\n"
        fh.write(marker)
        fh.write(code)
        body_lines = code.count("\n")
        # function span inside the batch file (excluding the marker line)
        func_start = start_line + 1
        func_end = func_start + body_lines - 1
        fh.write("\n")  # blank separator
        cur_line = func_end + 1  # account for the separator line
        pos_in_batch += 1

        mapping.append(
            {
                "sample_id": sid,
                "batch_file": f"batch_{batch_idx:03d}.c",
                "start_line": func_start,
                "end_line": func_end,
                "orig_file": rec.get("file", "unknown"),
                "orig_span": rec.get("span"),
                "label": rec.get("label"),
            }
        )

    if fh is not None:
        fh.close()

    MAPPING_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MAPPING_PATH.open("w", encoding="utf-8") as f:
        for m in mapping:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    with SKIPPED_PATH.open("w", encoding="utf-8") as f:
        for s in skipped:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    # Makefile: best-effort syntax-only compile of every batch (errors ignored
    # via the leading '-', so CodeQL still extracts every translation unit).
    n_batches = batch_idx + 1 if mapping else 0
    mk = ["CC = gcc", "BATCHES = $(wildcard batch_*.c)", "", "all:"]
    mk.append("\t-@for f in $(BATCHES); do echo \"syntax-check $$f\"; "
              "$(CC) -fsyntax-only $$f 2>/dev/null || true; done")
    mk.append("")
    (SRC_DIR / "Makefile").write_text("\n".join(mk), encoding="utf-8")

    print(f"usable functions : {len(usable)}")
    print(f"skipped          : {len(skipped)}")
    print(f"batch files      : {n_batches}")
    print(f"mapping records  : {len(mapping)} -> {MAPPING_PATH}")
    print(f"skipped records  : {len(skipped)} -> {SKIPPED_PATH}")
    return 0


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    raise SystemExit(main(lim))
