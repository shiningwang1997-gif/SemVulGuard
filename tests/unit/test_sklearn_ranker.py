"""Tests for the sklearn_tfidf ranker (model, training, inference, determinism)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from semvulguard.models.ranker.infer_sklearn import infer, score_samples
from semvulguard.models.ranker.sklearn_ranker import (
    NUMERIC_FEATURE_NAMES,
    SklearnRanker,
    build_samples,
    compute_code_metrics,
    compute_static_alert_features,
)
from semvulguard.models.ranker.train_sklearn import (
    stratified_split,
    train,
)
from semvulguard.schemas.records import StaticAlertRecord

# -- synthetic data ----------------------------------------------------------

_VULN_CODE = (
    "int copy(char *dst, char *src) {{\n"
    "    char buf[64];\n"
    "    strcpy(buf, src);\n"
    "    memcpy(dst, buf, strlen(src));\n"
    "    for (int i = 0; i < 10; i++) {{ dst[i] = buf[i]; }}\n"
    "    return 0;\n"
    "}}\n"
)
_SAFE_CODE = (
    "int add(int a, int b) {{\n"
    "    int total = a + b;\n"
    "    return total;\n"
    "}}\n"
)


def _make_features(path: Path, n_per_class: int = 12) -> Path:
    """Write a small synthetic FeatureRecord JSONL with two separable classes."""
    rows = []
    for i in range(n_per_class):
        rows.append({
            "sample_id": f"vuln_{i}",
            "label": 1,
            "cwe": ["CWE-120"],
            "file": "x.c",
            "function": "copy",
            "span": {"file": "x.c", "start_line": 1, "end_line": 7},
            "function_code": _VULN_CODE.replace("buf", f"buf{i}"),
            "static_features": {
                "alert_count": 1, "dangerous_api_count": 2,
                "function_line_count": 7, "has_codeql_alert": 1,
            },
            "metadata": {"dataset": "synthetic", "split": "unknown"},
        })
        rows.append({
            "sample_id": f"safe_{i}",
            "label": 0,
            "cwe": [],
            "file": "y.c",
            "function": "add",
            "span": {"file": "y.c", "start_line": 1, "end_line": 4},
            "function_code": _SAFE_CODE.replace("total", f"total{i}"),
            "static_features": {
                "alert_count": 0, "dangerous_api_count": 0,
                "function_line_count": 4, "has_codeql_alert": 0,
            },
            "metadata": {"dataset": "synthetic", "split": "unknown"},
        })
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return path


def _make_alerts(path: Path, n_per_class: int = 12) -> Path:
    rows = []
    for i in range(n_per_class):
        rows.append({
            "sample_id": f"vuln_{i}",
            "tool": "codeql",
            "query_id": "cpp/unsafe-strcpy",
            "message": "unsafe copy",
            "severity": "error",
            "file": "x.c",
            "start_line": 3,
            "end_line": 3,
            "cwe": ["CWE-120"],
            "trace_lines": [3, 4],
            "raw": {},
        })
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return path


# -- feature extraction ------------------------------------------------------

def test_compute_code_metrics_counts():
    m = compute_code_metrics("int f() {\n    strcpy(a, b);\n    if (x) return 1;\n}")
    assert m["dangerous_api_count"] >= 1.0  # strcpy
    assert m["if_count"] == 1.0
    assert m["return_count"] == 1.0
    assert m["line_count"] == 4.0
    assert m["char_count"] > 0


def test_compute_static_alert_features_aggregates():
    alerts = [
        StaticAlertRecord(
            sample_id="s", tool="codeql", query_id="q1", message="m",
            severity="error", file="f.c", start_line=1, end_line=1,
            cwe=["CWE-1"], trace_lines=[1, 2], raw={},
        ),
        StaticAlertRecord(
            sample_id="s", tool="codeql", query_id="q2", message="m",
            severity="warning", file="f.c", start_line=5, end_line=5,
            cwe=["CWE-2"], trace_lines=[5], raw={},
        ),
    ]
    feats = compute_static_alert_features(alerts)
    assert feats["alert_count"] == 2.0
    assert feats["has_codeql_alert"] == 1.0
    assert feats["high_severity_count"] == 1.0  # only the error
    assert feats["unique_query_count"] == 2.0
    assert feats["cwe_count"] == 2.0
    assert feats["trace_line_count"] == 3.0


def test_static_alert_features_empty():
    feats = compute_static_alert_features([])
    assert all(v == 0.0 for v in feats.values())
    assert feats["has_codeql_alert"] == 0.0


def test_build_samples_vector_width(tmp_path: Path):
    feats = _make_features(tmp_path / "features.jsonl", n_per_class=2)
    alerts = _make_alerts(tmp_path / "alerts.jsonl", n_per_class=2)
    samples = build_samples(feats, alerts)
    assert len(samples) == 4
    for s in samples:
        assert len(s.numeric_vector()) == len(NUMERIC_FEATURE_NAMES)


# -- split -------------------------------------------------------------------

def test_stratified_split_is_deterministic_and_stratified(tmp_path: Path):
    feats = _make_features(tmp_path / "features.jsonl", n_per_class=10)
    samples = build_samples(feats, None)
    a = stratified_split(samples, seed=42)
    b = stratified_split(samples, seed=42)
    assert a == b  # deterministic
    # every sample assigned to a valid split
    assert set(a.values()) <= {"train", "valid", "test"}
    assert len(a) == len(samples)
    # both classes present in train
    train_labels = {s.label for s in samples if a[s.sample_id] == "train"}
    assert train_labels == {0, 1}


# -- model fit / predict -----------------------------------------------------

def test_ranker_fit_predict_scores_in_range(tmp_path: Path):
    feats = _make_features(tmp_path / "features.jsonl")
    alerts = _make_alerts(tmp_path / "alerts.jsonl")
    samples = build_samples(feats, alerts)
    ranker = SklearnRanker(model="logistic_regression", seed=42).fit(samples)
    scores = ranker.predict_scores(samples)
    assert len(scores) == len(samples)
    assert all(0.0 <= s <= 1.0 for s in scores)
    # separable data: positives should outscore negatives on average
    pos = [sc for s, sc in zip(samples, scores, strict=True) if s.label == 1]
    neg = [sc for s, sc in zip(samples, scores, strict=True) if s.label == 0]
    assert sum(pos) / len(pos) > sum(neg) / len(neg)


def test_ranker_deterministic(tmp_path: Path):
    feats = _make_features(tmp_path / "features.jsonl")
    samples = build_samples(feats, None)
    s1 = SklearnRanker(seed=42).fit(samples).predict_scores(samples)
    s2 = SklearnRanker(seed=42).fit(samples).predict_scores(samples)
    assert list(s1) == list(s2)


def test_feature_importance_numeric_only(tmp_path: Path):
    feats = _make_features(tmp_path / "features.jsonl")
    samples = build_samples(feats, None)
    ranker = SklearnRanker(seed=42).fit(samples)
    imp = ranker.feature_importance()
    names = {n for n, _ in imp}
    assert names == set(NUMERIC_FEATURE_NAMES)


def test_random_forest_backend(tmp_path: Path):
    feats = _make_features(tmp_path / "features.jsonl")
    samples = build_samples(feats, None)
    ranker = SklearnRanker(model="random_forest", seed=42).fit(samples)
    scores = ranker.predict_scores(samples)
    assert all(0.0 <= s <= 1.0 for s in scores)


def test_unknown_model_raises():
    with pytest.raises(ValueError):
        SklearnRanker(model="svm")


# -- save / load -------------------------------------------------------------

def test_save_and_load_roundtrip(tmp_path: Path):
    feats = _make_features(tmp_path / "features.jsonl")
    samples = build_samples(feats, None)
    ranker = SklearnRanker(seed=42).fit(samples)
    before = list(ranker.predict_scores(samples))
    model_dir = tmp_path / "model"
    ranker.save(model_dir)
    assert (model_dir / "model.joblib").exists()
    assert (model_dir / "vectorizer.joblib").exists()
    loaded = SklearnRanker.load(model_dir)
    after = list(loaded.predict_scores(samples))
    assert before == after


# -- training CLI / outputs --------------------------------------------------

def test_train_writes_all_outputs(tmp_path: Path):
    feats = _make_features(tmp_path / "features.jsonl")
    alerts = _make_alerts(tmp_path / "alerts.jsonl")
    out = tmp_path / "ranker_out"
    summary = train(
        features_path=feats,
        output_dir=out,
        static_alerts_path=alerts,
        manifest_path=None,
        seed=42,
        model="logistic_regression",
    )
    for name in [
        "model.joblib", "vectorizer.joblib", "split.jsonl",
        "train_metrics.json", "valid_metrics.json", "test_metrics.json",
        "feature_importance.csv", "training_report.md",
    ]:
        assert (out / name).exists(), f"missing {name}"
    assert summary["split_created"] is True
    assert summary["counts"]["train"] > 0


def test_train_split_persisted_assignment(tmp_path: Path):
    feats = _make_features(tmp_path / "features.jsonl")
    out = tmp_path / "ranker_out"
    train(features_path=feats, output_dir=out, seed=42)
    rows = [json.loads(line) for line in (out / "split.jsonl").open()]
    assert len(rows) == 24
    assert {r["split"] for r in rows} <= {"train", "valid", "test"}


# -- inference + validation --------------------------------------------------

def test_infer_writes_scores_and_validation(tmp_path: Path):
    feats = _make_features(tmp_path / "features.jsonl")
    alerts = _make_alerts(tmp_path / "alerts.jsonl")
    out = tmp_path / "ranker_out"
    train(features_path=feats, output_dir=out, static_alerts_path=alerts, seed=42)

    scores_path = out / "rank_scores_sklearn.jsonl"
    rows = infer(
        features_path=feats,
        model_dir=out,
        output_path=scores_path,
        static_alerts_path=alerts,
        manifest_path=None,
    )
    assert scores_path.exists()
    assert (out / "rank_score_validation.md").exists()
    assert len(rows) == 24
    # required fields + range + contiguous ranks
    for r in rows:
        assert set(r) >= {"sample_id", "rank_score", "rank", "label", "metadata"}
        assert 0.0 <= r["rank_score"] <= 1.0
    assert sorted(r["rank"] for r in rows) == list(range(1, 25))


def test_score_samples_sorted_descending(tmp_path: Path):
    feats = _make_features(tmp_path / "features.jsonl")
    samples = build_samples(feats, None)
    ranker = SklearnRanker(seed=42).fit(samples)
    rows = score_samples(ranker, samples)
    scores = [r["rank_score"] for r in rows]
    assert scores == sorted(scores, reverse=True)
