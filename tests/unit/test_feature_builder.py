"""Tests for the feature builder and its batch CLI."""

from __future__ import annotations

from pathlib import Path

from semvulguard.features.build import build_feature_record, main
from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import CodeSpan, SampleRecord, StaticAlertRecord
from semvulguard.static.joern.graph import load_graph_json
from semvulguard.utils.jsonl import read_models


def _sample(sample_id: str = "s1") -> SampleRecord:
    return SampleRecord(
        sample_id=sample_id,
        dataset="diversevul",
        language="c",
        file="a.c",
        span=CodeSpan(file="a.c", start_line=1, end_line=10),
        label=1,
        cwe=["CWE-416"],
        split="train",
    )


def _alert() -> StaticAlertRecord:
    return StaticAlertRecord(
        sample_id="s1",
        tool="codeql",
        query_id="cpp/use-after-free",
        message="Use after free",
        severity="high",
        file="a.c",
        start_line=5,
        end_line=6,
        trace_lines=[3, 5],
    )


_CODE = "int foo()\n{\n    free(p);\n    use(p);\n}"


def test_build_record_with_graph_and_alerts(fixtures_dir: Path):
    graph = load_graph_json(fixtures_dir / "features" / "sample_graph_slice.json")
    record = build_feature_record(_sample(), _CODE, [_alert()], graph)
    assert isinstance(record, FeatureRecord)
    assert record.sample_id == "s1"
    assert record.label == 1
    assert record.alert_lines == [5, 6]
    assert record.trace_lines == [3, 5]
    assert len(record.nodes) == 5
    assert record.code_lines == _CODE.splitlines()
    assert record.metadata["has_graph"] is True


def test_build_record_missing_graph():
    record = build_feature_record(_sample(), _CODE, [_alert()], graph_slice=None)
    assert record.nodes == []
    assert record.edges == []
    assert record.static_features["graph_node_count"] == 0
    assert record.metadata["has_graph"] is False
    # Alert-derived lines are still populated without a graph.
    assert record.alert_lines == [5, 6]


def test_build_record_missing_alerts(fixtures_dir: Path):
    graph = load_graph_json(fixtures_dir / "features" / "sample_graph_slice.json")
    record = build_feature_record(_sample(), _CODE, [], graph)
    assert record.alert_lines == []
    assert record.trace_lines == []
    assert record.static_features["alert_count"] == 0
    # Graph nodes are still built; alert/trace flags are all zero.
    assert len(record.nodes) == 5
    assert all(n.static_flags["is_alert_line"] == 0 for n in record.nodes)


def test_cli_builds_feature_jsonl(fixtures_dir: Path, tmp_path: Path, capsys):
    features_dir = fixtures_dir / "features"
    out = tmp_path / "features.jsonl"
    rc = main(
        [
            "--manifest",
            str(features_dir / "sample_manifest.jsonl"),
            "--alerts",
            str(features_dir / "sample_alerts.jsonl"),
            "--graphs-dir",
            str(features_dir / "graphs"),
            "--code-dir",
            str(features_dir / "code"),
            "--output",
            str(out),
        ]
    )
    assert rc == 0
    records = read_models(out, FeatureRecord)
    assert len(records) == 2
    by_id = {r.sample_id: r for r in records}
    # s1 has code, alerts, and a graph.
    assert by_id["s1"].nodes
    assert by_id["s1"].alert_lines == [5, 6]
    assert "int foo()" in by_id["s1"].function_code
    # s2 has code but no graph and no alerts.
    assert by_id["s2"].nodes == []
    assert by_id["s2"].alert_lines == []
    assert "int bar()" in by_id["s2"].function_code
    assert "built 2 feature records" in capsys.readouterr().out


def test_cli_without_alerts_or_graphs(fixtures_dir: Path, tmp_path: Path):
    features_dir = fixtures_dir / "features"
    out = tmp_path / "features.jsonl"
    main(
        [
            "--manifest",
            str(features_dir / "sample_manifest.jsonl"),
            "--code-dir",
            str(features_dir / "code"),
            "--output",
            str(out),
        ]
    )
    records = read_models(out, FeatureRecord)
    assert len(records) == 2
    assert all(r.nodes == [] for r in records)
    assert all(r.alert_lines == [] for r in records)
