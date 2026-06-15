"""Final report generation.

Emits the fused :class:`~semvulguard.schemas.records.FinalFinding` records as a
wrapped JSON report, a JSONL stream, and a SARIF 2.1.0 log.
"""

from semvulguard.report.json_report import (
    write_findings_json,
    write_findings_jsonl,
)
from semvulguard.report.sarif_report import (
    final_findings_to_sarif,
    write_sarif,
)

__all__ = [
    "write_findings_json",
    "write_findings_jsonl",
    "final_findings_to_sarif",
    "write_sarif",
]
