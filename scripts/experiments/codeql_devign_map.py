"""Task B4: parse wrapped-Devign SARIF and map alerts back to Devign sample_id.

CodeQL ran on batched ``.c`` files; each alert's (batch_file, start_line) is
mapped to the ``sample_id`` whose recorded line span in that batch contains the
alert. Output is StaticAlertRecord JSONL keyed by the original Devign sample_id,
plus a mapping report.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from semvulguard.schemas.records import StaticAlertRecord
from semvulguard.static.codeql.sarif import sarif_to_static_alerts
from semvulguard.utils.jsonl import write_jsonl

WRAP = Path("artifacts/codeql_devign_wrapped")
SARIF = WRAP / "results.sarif"
MAPPING = WRAP / "mapping" / "sample_line_mapping.jsonl"
SKIPPED = WRAP / "skipped_samples.jsonl"
OUT_ALERTS = Path("artifacts/experiments/devign/static_alerts_codeql.jsonl")
REPORT = WRAP / "codeql_mapping_report.md"


def _load_mapping() -> dict[str, list[dict]]:
    """batch_file -> list of {sample_id, start_line, end_line, ...} sorted by span width."""
    by_file: dict[str, list[dict]] = defaultdict(list)
    with MAPPING.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            m = json.loads(line)
            by_file[m["batch_file"]].append(m)
    return by_file


def _basename(uri: str) -> str:
    return uri.replace("\\", "/").rsplit("/", 1)[-1]


def _find_sample(spans: list[dict], line: int) -> dict | None:
    """Return the narrowest mapping span containing ``line``."""
    best = None
    for m in spans:
        if m["start_line"] <= line <= m["end_line"]:
            if best is None or (m["end_line"] - m["start_line"]) < (
                best["end_line"] - best["start_line"]
            ):
                best = m
    return best


def main() -> int:
    by_file = _load_mapping()
    # parse SARIF (sample_id placeholder "unknown"; we rewrite below)
    raw_alerts = sarif_to_static_alerts(SARIF, default_sample_id="unknown")

    mapped: list[StaticAlertRecord] = []
    unmapped = 0
    for alert in raw_alerts:
        bfile = _basename(alert.file)
        spans = by_file.get(bfile, [])
        hit = _find_sample(spans, alert.start_line)
        if hit is None:
            unmapped += 1
            continue
        sid = hit["sample_id"]
        # Re-base the alert's lines onto the original function (1-indexed within
        # the function body), so downstream localization is relative to the
        # function rather than the batch file.
        rel_start = alert.start_line - hit["start_line"] + 1
        rel_end = alert.end_line - hit["start_line"] + 1
        if rel_start < 1:
            rel_start = 1
        if rel_end < rel_start:
            rel_end = rel_start
        rel_trace = [
            t - hit["start_line"] + 1
            for t in alert.trace_lines
            if hit["start_line"] <= t <= hit["end_line"]
        ]
        rel_trace = [t for t in rel_trace if t >= 1]

        raw = dict(alert.raw) if isinstance(alert.raw, dict) else {"sarif": alert.raw}
        raw["mapping"] = {
            "batch_file": bfile,
            "batch_start_line": alert.start_line,
            "batch_end_line": alert.end_line,
            "func_start_in_batch": hit["start_line"],
            "func_end_in_batch": hit["end_line"],
            "orig_file": hit.get("orig_file"),
            "orig_span": hit.get("orig_span"),
        }
        mapped.append(
            StaticAlertRecord(
                sample_id=sid,
                tool="codeql",
                query_id=alert.query_id,
                message=alert.message,
                severity=alert.severity,
                file=bfile,
                start_line=rel_start,
                end_line=rel_end,
                cwe=alert.cwe,
                trace_lines=rel_trace,
                raw=raw,
            )
        )

    # validate each record
    for a in mapped:
        StaticAlertRecord.model_validate(a.model_dump())

    n = write_jsonl(OUT_ALERTS, mapped)

    # report stats
    samples_covered = {a.sample_id for a in mapped}
    qid_counts = Counter(a.query_id for a in mapped)
    cwe_counts = Counter(c for a in mapped for c in a.cwe)
    n_skipped = sum(1 for _ in SKIPPED.open()) if SKIPPED.exists() else 0

    lines = [
        "# CodeQL → Devign Mapping Report (Task B4)",
        "",
        f"- SARIF findings parsed: **{len(raw_alerts)}**",
        f"- Alerts mapped to a sample_id: **{n}**",
        f"- Alerts unmapped (no containing function span): **{unmapped}**",
        f"- Devign samples with >=1 CodeQL alert: **{len(samples_covered)}** / 1000",
        f"- Skipped samples during wrapping: **{n_skipped}**",
        f"- Output: `{OUT_ALERTS}`",
        "",
        "## query_id counts",
        "",
        "| query_id | count |",
        "|---|---|",
    ]
    for q, c in qid_counts.most_common():
        lines.append(f"| `{q}` | {c} |")
    lines += ["", "## CWE counts", "", "| CWE | count |", "|---|---|"]
    for c, n_ in cwe_counts.most_common():
        lines.append(f"| {c} | {n_} |")
    lines.append("")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"parsed={len(raw_alerts)} mapped={n} unmapped={unmapped} "
          f"samples_covered={len(samples_covered)}")
    print(f"alerts -> {OUT_ALERTS}")
    print(f"report -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
