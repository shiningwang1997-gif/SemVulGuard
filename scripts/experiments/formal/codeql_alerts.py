"""Phase 5: CodeQL static alerts for each usable dataset (function-wrapped).

Devign / BigVul / DiverseVul are function-level corpora with no buildable repo
context, so we use the function-wrapping strategy (same approach as the prior
Devign run, generalized):

  1. wrap each subset function into batched .c files (50 funcs/file) with common
     headers, recording the exact line span each function occupies;
  2. build a CodeQL C/C++ database over the batch dir (gcc autobuild,
     -fsyntax-only so partial functions still extract);
  3. analyze with codeql/cpp-queries cpp-security-extended.qls -> SARIF;
  4. parse SARIF and map each alert back to its originating sample_id by line
     containment, re-basing alert lines onto the function body.

Outputs per dataset (under .../formal_multidataset_v1/{ds}/):
  codeql_wrapped/src/batch_*.c, codeql_wrapped/mapping/sample_line_mapping.jsonl,
  codeql_wrapped/results.sarif, static_alerts_codeql.jsonl, codeql_report.md

Robust: if CodeQL fails for a dataset, an EMPTY but valid static_alerts JSONL is
written and the failure is documented; other datasets still proceed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

from semvulguard.schemas.records import StaticAlertRecord
from semvulguard.static.codeql.runner import DEFAULT_QUERY_SUITE, CodeQLRunner
from semvulguard.static.codeql.sarif import sarif_to_static_alerts
from semvulguard.utils.jsonl import read_models, write_jsonl

from scripts.experiments.formal.config import ROOT, SUBSET_TARGETS

try:
    from semvulguard.schemas.features import FeatureRecord
except Exception:  # pragma: no cover
    FeatureRecord = None

BATCH_SIZE = 50
HEADER = (
    "#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n"
    "#include <stdint.h>\n#include <unistd.h>\n\n"
)
HEADER_LINES = HEADER.count("\n")
QUERY_SUITE = DEFAULT_QUERY_SUITE


def _wrap(ds: str) -> tuple[int, int, int, Path]:
    """Wrap subset functions into batched .c files. Returns (usable, skipped, batches, src_dir)."""
    ddir = ROOT / ds
    features = read_models(ddir / "features.jsonl", FeatureRecord)
    wrap_root = ddir / "codeql_wrapped"
    src_dir = wrap_root / "src"
    map_dir = wrap_root / "mapping"
    src_dir.mkdir(parents=True, exist_ok=True)
    map_dir.mkdir(parents=True, exist_ok=True)
    for old in src_dir.glob("batch_*.c"):
        old.unlink()

    usable, skipped = [], []
    for rec in features:
        code = rec.function_code or ""
        if not code.strip():
            skipped.append({"sample_id": rec.sample_id, "reason": "empty function_code"})
            continue
        if len(code.splitlines()) < 2:
            skipped.append({"sample_id": rec.sample_id, "reason": "too short (<2 lines)"})
            continue
        usable.append(rec)

    mapping = []
    batch_idx, pos_in_batch, fh, cur_line = 0, 0, None, 0

    def open_batch(idx):
        f = (src_dir / f"batch_{idx:03d}.c").open("w", encoding="utf-8")
        f.write(HEADER)
        return f, HEADER_LINES

    for rec in usable:
        if fh is None or pos_in_batch == BATCH_SIZE:
            if fh is not None:
                fh.close(); batch_idx += 1
            fh, cur_line = open_batch(batch_idx)
            pos_in_batch = 0
        sid, code = rec.sample_id, rec.function_code
        if not code.endswith("\n"):
            code += "\n"
        start_line = cur_line + 1
        fh.write(f"/* === sample_id={sid} === */\n")
        fh.write(code)
        body_lines = code.count("\n")
        func_start = start_line + 1
        func_end = func_start + body_lines - 1
        fh.write("\n")
        cur_line = func_end + 1
        pos_in_batch += 1
        mapping.append({"sample_id": sid, "batch_file": f"batch_{batch_idx:03d}.c",
                        "start_line": func_start, "end_line": func_end,
                        "label": rec.label})
    if fh is not None:
        fh.close()

    n_batches = batch_idx + 1 if mapping else 0
    with (map_dir / "sample_line_mapping.jsonl").open("w", encoding="utf-8") as f:
        for m in mapping:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    with (wrap_root / "skipped_samples.jsonl").open("w", encoding="utf-8") as f:
        for s in skipped:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    # Makefile (best-effort syntax-only compile)
    mk = ("CC = gcc\nBATCHES = $(wildcard batch_*.c)\n\nall:\n"
          "\t-@for f in $(BATCHES); do $(CC) -fsyntax-only $$f 2>/dev/null || true; done\n")
    (src_dir / "Makefile").write_text(mk, encoding="utf-8")
    return len(usable), len(skipped), n_batches, src_dir


def _build_and_analyze(ds: str, src_dir: Path) -> tuple[bool, str, Path | None]:
    """Create CodeQL DB and analyze. Returns (ok, message, sarif_path)."""
    wrap_root = ROOT / ds / "codeql_wrapped"
    db_dir = wrap_root / "db"
    sarif = wrap_root / "results.sarif"
    if db_dir.exists():
        shutil.rmtree(db_dir)
    runner = CodeQLRunner(threads=8)
    if not runner.is_available():
        return False, "codeql binary not on PATH", None
    try:
        runner.build_database(
            source_root=src_dir, database_dir=db_dir, language="cpp",
            command="make",
        )
    except subprocess.CalledProcessError as exc:
        return False, f"database create failed: {exc}", None
    try:
        runner.analyze_database(db_dir, sarif, query_suite=QUERY_SUITE)
    except subprocess.CalledProcessError as exc:
        return False, f"database analyze failed: {exc}", None
    return True, "ok", sarif


def _basename(uri: str) -> str:
    return uri.replace("\\", "/").rsplit("/", 1)[-1]


def _find_sample(spans, line):
    best = None
    for m in spans:
        if m["start_line"] <= line <= m["end_line"]:
            if best is None or (m["end_line"] - m["start_line"]) < (best["end_line"] - best["start_line"]):
                best = m
    return best


def _map_sarif(ds: str, sarif: Path) -> dict:
    wrap_root = ROOT / ds / "codeql_wrapped"
    by_file = defaultdict(list)
    with (wrap_root / "mapping" / "sample_line_mapping.jsonl").open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                m = json.loads(line)
                by_file[m["batch_file"]].append(m)

    raw_alerts = sarif_to_static_alerts(sarif, default_sample_id="unknown")
    mapped, unmapped = [], 0
    for alert in raw_alerts:
        spans = by_file.get(_basename(alert.file), [])
        hit = _find_sample(spans, alert.start_line)
        if hit is None:
            unmapped += 1
            continue
        rel_start = max(1, alert.start_line - hit["start_line"] + 1)
        rel_end = max(rel_start, alert.end_line - hit["start_line"] + 1)
        rel_trace = [t - hit["start_line"] + 1 for t in alert.trace_lines
                     if hit["start_line"] <= t <= hit["end_line"]]
        rel_trace = [t for t in rel_trace if t >= 1]
        raw = dict(alert.raw) if isinstance(alert.raw, dict) else {"sarif": alert.raw}
        mapped.append(StaticAlertRecord(
            sample_id=hit["sample_id"], tool="codeql", query_id=alert.query_id,
            message=alert.message, severity=alert.severity,
            file=_basename(alert.file), start_line=rel_start, end_line=rel_end,
            cwe=alert.cwe, trace_lines=rel_trace, raw=raw))
    for a in mapped:
        StaticAlertRecord.model_validate(a.model_dump())
    n = write_jsonl(ROOT / ds / "static_alerts_codeql.jsonl", mapped)
    return {
        "parsed": len(raw_alerts), "mapped": n, "unmapped": unmapped,
        "samples_covered": len({a.sample_id for a in mapped}),
        "qids": Counter(a.query_id for a in mapped),
        "cwes": Counter(c for a in mapped for c in a.cwe),
    }


def _write_report(ds: str, wrap_stats, build_ok, build_msg, map_stats, subset_n):
    ddir = ROOT / ds
    L = [f"# CodeQL Report — {ds}", "",
         f"- Strategy: function-wrapping (batched .c, {BATCH_SIZE} funcs/file)",
         f"- Query suite: `{QUERY_SUITE}`",
         f"- Usable functions wrapped: {wrap_stats[0]} / subset {subset_n}",
         f"- Skipped (empty/too short): {wrap_stats[1]}",
         f"- Batch files: {wrap_stats[2]}",
         f"- DB create+analyze: **{'SUCCESS' if build_ok else 'FAILED'}** ({build_msg})",
         ""]
    if map_stats:
        L += [f"- SARIF path: `{ddir / 'codeql_wrapped' / 'results.sarif'}`",
              f"- SARIF findings parsed: **{map_stats['parsed']}**",
              f"- Alerts mapped to sample_id: **{map_stats['mapped']}**",
              f"- Unmapped findings: {map_stats['unmapped']}",
              f"- Samples with >=1 alert: **{map_stats['samples_covered']}** / {subset_n}",
              f"- Output: `{ddir / 'static_alerts_codeql.jsonl'}`", "",
              "## query_id counts", "", "| query_id | count |", "|---|---|"]
        for q, c in map_stats["qids"].most_common():
            L.append(f"| `{q}` | {c} |")
        L += ["", "## CWE counts", "", "| CWE | count |", "|---|---|"]
        for c, n_ in map_stats["cwes"].most_common():
            L.append(f"| {c} | {n_} |")
    else:
        L += ["", "## Limitation", "",
              "CodeQL did not complete for this dataset; an EMPTY but valid "
              "`static_alerts_codeql.jsonl` was written so the pipeline continues. "
              "The static channel contributes nothing (static_score=0) for this dataset."]
    L.append("")
    (ddir / "codeql_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def run_one(ds: str) -> dict:
    ddir = ROOT / ds
    subset_n = SUBSET_TARGETS[ds]
    print(f"[{ds}] wrapping functions...")
    wrap_stats = _wrap(ds)
    print(f"[{ds}] wrapped={wrap_stats[0]} skipped={wrap_stats[1]} batches={wrap_stats[2]}")
    print(f"[{ds}] building + analyzing CodeQL DB...")
    build_ok, build_msg, sarif = _build_and_analyze(ds, wrap_stats[3])
    map_stats = None
    if build_ok and sarif is not None:
        map_stats = _map_sarif(ds, sarif)
        print(f"[{ds}] parsed={map_stats['parsed']} mapped={map_stats['mapped']} "
              f"covered={map_stats['samples_covered']}")
    else:
        # write empty valid alerts file
        write_jsonl(ddir / "static_alerts_codeql.jsonl", [])
        print(f"[{ds}] CodeQL FAILED: {build_msg} -> empty alerts written")
    _write_report(ds, wrap_stats, build_ok, build_msg, map_stats, subset_n)
    return {"dataset": ds, "build_ok": build_ok, "msg": build_msg,
            "map": ({k: (dict(v) if isinstance(v, Counter) else v)
                     for k, v in map_stats.items()} if map_stats else None)}


def main(argv: list[str] | None = None) -> int:
    targets = argv if argv else list(SUBSET_TARGETS)
    results = [run_one(ds) for ds in targets]
    # merge with any existing summary so partial re-runs don't clobber others
    summary_path = ROOT / "codeql_summary.json"
    existing = {}
    if summary_path.exists():
        try:
            for r in json.loads(summary_path.read_text()):
                existing[r["dataset"]] = r
        except Exception:
            pass
    for r in results:
        existing[r["dataset"]] = r
    merged = [existing[ds] for ds in SUBSET_TARGETS if ds in existing]
    summary_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or None))
