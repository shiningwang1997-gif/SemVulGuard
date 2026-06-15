"""Feature builder: assemble :class:`FeatureRecord` artifacts.

``build_feature_record`` fuses one sample's source, static alerts, and (optional)
graph slice into a single model-ready record. The batch CLI walks a manifest,
loading per-sample code and graph files by ``sample_id`` convention and grouping
alerts by ``sample_id``.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from semvulguard.features.graph_features import (
    build_feature_graph,
    extract_static_features,
)
from semvulguard.features.line_map import split_code_lines
from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import SampleRecord, StaticAlertRecord
from semvulguard.static.joern.graph import ProgramGraph, load_graph_json
from semvulguard.utils.jsonl import read_models, write_jsonl
from semvulguard.utils.logging import get_logger

LOGGER = get_logger("semvulguard.features.build")


def _sorted_unique_lines(
    alerts: list[StaticAlertRecord],
) -> tuple[list[int], list[int]]:
    """Collect sorted, unique alert and trace lines from a sample's alerts."""
    alert_lines: set[int] = set()
    trace_lines: set[int] = set()
    for alert in alerts:
        alert_lines.update(range(alert.start_line, alert.end_line + 1))
        trace_lines.update(alert.trace_lines)
    return sorted(alert_lines), sorted(trace_lines)


def build_feature_record(
    sample: SampleRecord,
    function_code: str,
    alerts: list[StaticAlertRecord],
    graph_slice: ProgramGraph | None = None,
) -> FeatureRecord:
    """Build a single :class:`FeatureRecord` from a sample and its evidence.

    A missing graph yields empty node/edge lists; missing alerts yield empty
    alert/trace lines. The record is always well-formed.
    """
    alert_lines, trace_lines = _sorted_unique_lines(alerts)

    if graph_slice is not None:
        nodes, edges = build_feature_graph(graph_slice, sample, alerts)
    else:
        nodes, edges = [], []

    static_features = extract_static_features(sample, alerts, graph_slice)

    return FeatureRecord(
        sample_id=sample.sample_id,
        label=sample.label,
        cwe=sample.cwe,
        file=sample.file,
        function=sample.function,
        span=sample.span,
        function_code=function_code,
        code_lines=split_code_lines(function_code),
        alert_lines=alert_lines,
        trace_lines=trace_lines,
        nodes=nodes,
        edges=edges,
        static_features=static_features,
        metadata={
            "dataset": sample.dataset,
            "language": sample.language,
            "split": sample.split,
            "has_graph": graph_slice is not None,
        },
    )


def _group_alerts(
    alerts: list[StaticAlertRecord],
) -> dict[str, list[StaticAlertRecord]]:
    grouped: dict[str, list[StaticAlertRecord]] = defaultdict(list)
    for alert in alerts:
        grouped[alert.sample_id].append(alert)
    return grouped


def _find_code(code_dir: Path | None, sample: SampleRecord) -> str:
    """Load function source for a sample by ``<sample_id>.*`` convention."""
    if code_dir is None:
        return ""
    for candidate in sorted(code_dir.glob(f"{sample.sample_id}.*")):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return ""


def _find_graph(graphs_dir: Path | None, sample: SampleRecord) -> ProgramGraph | None:
    """Load a graph slice for a sample by ``<sample_id>.json`` convention."""
    if graphs_dir is None:
        return None
    path = graphs_dir / f"{sample.sample_id}.json"
    if path.is_file():
        return load_graph_json(path)
    return None


def build_features(
    manifest: Path,
    alerts_path: Path | None = None,
    graphs_dir: Path | None = None,
    code_dir: Path | None = None,
) -> list[FeatureRecord]:
    """Build feature records for every sample in a manifest."""
    samples = read_models(manifest, SampleRecord)
    grouped = (
        _group_alerts(read_models(alerts_path, StaticAlertRecord))
        if alerts_path is not None
        else {}
    )
    records: list[FeatureRecord] = []
    for sample in samples:
        alerts = grouped.get(sample.sample_id, [])
        code = _find_code(code_dir, sample)
        graph = _find_graph(graphs_dir, sample)
        records.append(build_feature_record(sample, code, alerts, graph))
    return records


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="semvulguard.features.build",
        description="Build model-ready FeatureRecord JSONL from a manifest.",
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--alerts", type=Path, default=None)
    parser.add_argument("--graphs-dir", type=Path, default=None)
    parser.add_argument("--code-dir", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    records = build_features(
        manifest=args.manifest,
        alerts_path=args.alerts,
        graphs_dir=args.graphs_dir,
        code_dir=args.code_dir,
    )
    n = write_jsonl(args.output, records)
    with_graph = sum(1 for r in records if r.nodes)
    LOGGER.info("built %d feature records -> %s", n, args.output)
    print(
        f"built {n} feature records ({with_graph} with graph) -> {args.output}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["build_feature_record", "build_features"]
