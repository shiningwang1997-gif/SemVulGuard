"""End-to-end report builder.

Drives the fusion stage and writes the four final artifacts to an output
directory:

* ``findings.json``      -- wrapped JSON report (metadata + counts + findings)
* ``findings.jsonl``     -- one FinalFinding per line
* ``findings.sarif``     -- SARIF 2.1.0 log of the vulnerable findings
* ``fusion_scores.jsonl``-- per-sample component scores behind each decision

Example::

    python -m semvulguard.report.build \
        --features tests/fixtures/fusion/features.jsonl \
        --rank-scores tests/fixtures/fusion/rank_scores.jsonl \
        --alerts tests/fixtures/fusion/static_alerts.jsonl \
        --llm-verdicts tests/fixtures/fusion/llm_verdicts.jsonl \
        --output-dir artifacts/final --threshold 0.5
"""

from __future__ import annotations

import argparse
from pathlib import Path

from semvulguard.models.fusion.run import fuse, write_fusion_scores
from semvulguard.report.json_report import (
    write_findings_json,
    write_findings_jsonl,
)
from semvulguard.report.sarif_report import write_sarif
from semvulguard.schemas.features import FeatureRecord
from semvulguard.utils.jsonl import read_models
from semvulguard.utils.logging import get_logger

LOGGER = get_logger("semvulguard.report.build")


def build_report_artifacts(
    features_path: Path,
    rank_scores_path: Path,
    alerts_path: Path,
    llm_verdicts_path: Path,
    output_dir: Path,
    threshold: float = 0.5,
) -> dict[str, Path]:
    """Fuse signals and write all four report artifacts. Returns their paths."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    findings, score_rows = fuse(
        features_path=features_path,
        rank_scores_path=rank_scores_path,
        alerts_path=alerts_path,
        llm_verdicts_path=llm_verdicts_path,
        threshold=threshold,
    )
    features_by_id = {
        f.sample_id: f for f in read_models(features_path, FeatureRecord)
    }

    paths = {
        "json": output_dir / "findings.json",
        "jsonl": output_dir / "findings.jsonl",
        "sarif": output_dir / "findings.sarif",
        "scores": output_dir / "fusion_scores.jsonl",
    }

    metadata = {"threshold": threshold, "source_features": str(features_path)}
    write_findings_json(findings, paths["json"], metadata=metadata)
    write_findings_jsonl(findings, paths["jsonl"])
    write_sarif(findings, features_by_id, paths["sarif"])
    write_fusion_scores(score_rows, paths["scores"])

    LOGGER.info(
        "wrote %d findings (%d vulnerable) -> %s",
        len(findings),
        sum(f.final_label for f in findings),
        output_dir,
    )
    return paths


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="semvulguard.report.build",
        description="Fuse signals and emit final findings + reports.",
    )
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument("--rank-scores", required=True, type=Path)
    parser.add_argument("--alerts", required=True, type=Path)
    parser.add_argument("--llm-verdicts", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--threshold", type=float, default=0.5)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    paths = build_report_artifacts(
        features_path=args.features,
        rank_scores_path=args.rank_scores,
        alerts_path=args.alerts,
        llm_verdicts_path=args.llm_verdicts,
        output_dir=args.output_dir,
        threshold=args.threshold,
    )
    print(
        "wrote "
        + ", ".join(str(paths[k]) for k in ("json", "jsonl", "sarif", "scores"))
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["build_report_artifacts", "main"]
