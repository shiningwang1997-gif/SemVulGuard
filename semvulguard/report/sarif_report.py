"""SARIF 2.1.0 report generation for fused findings.

Renders the vulnerable :class:`FinalFinding` records into a SARIF log so the
results can be ingested by IDEs and code-scanning dashboards. Benign findings
are omitted from ``results`` (they are not reportable defects).

Each result's ``ruleId`` is the predicted CWE (or the tool name as a fallback),
its message summarizes the verdict and confidence, its location points at the
sample's file and first vulnerable line, and the fused evidence is carried in
``properties`` for downstream consumers.
"""

from __future__ import annotations

import json
from pathlib import Path

from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import FinalFinding

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/"
    "Schemas/sarif-schema-2.1.0.json"
)
TOOL_NAME = "SemVulGuard"
TOOL_VERSION = "0.1.0"
FALLBACK_RULE_ID = "SemVulGuard"


def _rule_id(finding: FinalFinding) -> str:
    """Use the predicted CWE as the rule id, falling back to the tool name."""
    cwe = (finding.predicted_cwe or "").strip()
    if not cwe or cwe.lower() in {"unknown", "cwe-unknown"}:
        return FALLBACK_RULE_ID
    return cwe


def _result_message(finding: FinalFinding) -> str:
    """Human-readable summary of the finding for the SARIF message text."""
    cwe = finding.predicted_cwe or "unknown CWE"
    lines = (
        ", ".join(str(line) for line in finding.vulnerable_lines)
        if finding.vulnerable_lines
        else "n/a"
    )
    return (
        f"Potential vulnerability ({cwe}) with confidence "
        f"{finding.final_confidence:.2f}. Suspect lines: {lines}."
    )


def _location(finding: FinalFinding, file: str) -> dict:
    """Build a SARIF location anchored at the first vulnerable line."""
    start_line = finding.vulnerable_lines[0] if finding.vulnerable_lines else 1
    return {
        "physicalLocation": {
            "artifactLocation": {"uri": file},
            "region": {"startLine": start_line},
        }
    }


def _collect_rules(findings: list[FinalFinding]) -> list[dict]:
    """Build the driver's rule table from the distinct rule ids in use."""
    rules: list[dict] = []
    seen: set[str] = set()
    for finding in findings:
        rule_id = _rule_id(finding)
        if rule_id in seen:
            continue
        seen.add(rule_id)
        rules.append(
            {
                "id": rule_id,
                "name": rule_id,
                "shortDescription": {"text": f"{rule_id} detected by {TOOL_NAME}"},
            }
        )
    return rules


def final_findings_to_sarif(
    findings: list[FinalFinding],
    feature_records_by_id: dict[str, FeatureRecord],
) -> dict:
    """Convert vulnerable findings into a SARIF 2.1.0 log dict.

    ``feature_records_by_id`` supplies the source file for each finding's
    location; a sample with no matching feature record falls back to its
    ``sample_id`` as the artifact URI.
    """
    vulnerable = [f for f in findings if f.final_label == 1]

    results: list[dict] = []
    for finding in vulnerable:
        feature = feature_records_by_id.get(finding.sample_id)
        file = feature.file if feature is not None else finding.sample_id
        results.append(
            {
                "ruleId": _rule_id(finding),
                "level": "warning",
                "message": {"text": _result_message(finding)},
                "locations": [_location(finding, file)],
                "properties": {
                    "sample_id": finding.sample_id,
                    "final_confidence": finding.final_confidence,
                    "predicted_cwe": finding.predicted_cwe,
                    "vulnerable_lines": finding.vulnerable_lines,
                    "patch_hint": finding.patch_hint,
                    "evidence": finding.evidence,
                },
            }
        )

    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": TOOL_NAME,
                        "version": TOOL_VERSION,
                        "rules": _collect_rules(vulnerable),
                    }
                },
                "results": results,
            }
        ],
    }


def write_sarif(
    findings: list[FinalFinding],
    feature_records_by_id: dict[str, FeatureRecord],
    output_path: Path,
) -> None:
    """Write the SARIF log for ``findings`` to ``output_path``."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sarif = final_findings_to_sarif(findings, feature_records_by_id)
    output_path.write_text(
        json.dumps(sarif, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


__all__ = ["final_findings_to_sarif", "write_sarif", "SARIF_VERSION", "TOOL_NAME"]
