"""JSON / JSONL report writers for fused findings.

``write_findings_jsonl`` emits one :class:`FinalFinding` per line (the canonical
stream consumed downstream), while ``write_findings_json`` wraps the findings in
a report envelope carrying reproducibility metadata and summary counts.

Output is deterministic: findings keep their input order and JSON keys are
written in a stable order.
"""

from __future__ import annotations

import json
from pathlib import Path

from semvulguard.schemas.records import FinalFinding
from semvulguard.utils.jsonl import write_jsonl

REPORT_TOOL_NAME = "SemVulGuard"
REPORT_SCHEMA_VERSION = "1.0"


def build_report(findings: list[FinalFinding], metadata: dict | None = None) -> dict:
    """Assemble the report envelope: metadata, counts, and the findings list."""
    vulnerable = [f for f in findings if f.final_label == 1]
    report_metadata = {
        "tool": REPORT_TOOL_NAME,
        "schema_version": REPORT_SCHEMA_VERSION,
    }
    if metadata:
        report_metadata.update(metadata)
    return {
        "metadata": report_metadata,
        "total_findings": len(findings),
        "vulnerable_count": len(vulnerable),
        "findings": [f.model_dump() for f in findings],
    }


def write_findings_json(
    findings: list[FinalFinding],
    output_path: Path,
    metadata: dict | None = None,
) -> None:
    """Write the wrapped JSON report (metadata + counts + findings)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(findings, metadata=metadata)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_findings_jsonl(findings: list[FinalFinding], output_path: Path) -> None:
    """Write one FinalFinding per line as JSONL."""
    write_jsonl(output_path, findings)


__all__ = [
    "build_report",
    "write_findings_json",
    "write_findings_jsonl",
    "REPORT_TOOL_NAME",
]
