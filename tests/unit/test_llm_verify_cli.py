"""Tests for the verify CLI in mock mode (no network, no API key)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from semvulguard.llm.mock import MockLLMClient
from semvulguard.llm.verify import main as verify_main
from semvulguard.llm.verify import verify
from semvulguard.schemas.records import LLMVerdict
from semvulguard.utils.jsonl import read_models


def _llm_dir(fixtures_dir: Path) -> Path:
    return fixtures_dir / "llm"


def _common_args(fixtures_dir: Path, out: Path) -> list[str]:
    d = _llm_dir(fixtures_dir)
    return [
        "--features",
        str(d / "features.jsonl"),
        "--rank-scores",
        str(d / "rank_scores.jsonl"),
        "--alerts",
        str(d / "alerts.jsonl"),
        "--output",
        str(out),
    ]


def test_cli_mock_writes_valid_verdict_jsonl(
    fixtures_dir: Path, tmp_path: Path, capsys
):
    out = tmp_path / "verdicts.jsonl"
    rc = verify_main(_common_args(fixtures_dir, out) + ["--top-k", "20", "--mock"])
    assert rc == 0
    assert out.exists()

    verdicts = read_models(out, LLMVerdict)
    assert len(verdicts) == 5
    assert all(isinstance(v, LLMVerdict) for v in verdicts)
    assert "verified 5 candidates" in capsys.readouterr().out


def test_cli_default_top_k_is_50(fixtures_dir: Path, tmp_path: Path):
    # With only 5 candidates, the default top-k=50 still returns all 5.
    out = tmp_path / "verdicts.jsonl"
    rc = verify_main(_common_args(fixtures_dir, out) + ["--mock"])
    assert rc == 0
    assert len(read_models(out, LLMVerdict)) == 5


def test_cli_top_k_limits_verdicts(fixtures_dir: Path, tmp_path: Path):
    out = tmp_path / "verdicts.jsonl"
    rc = verify_main(_common_args(fixtures_dir, out) + ["--top-k", "2", "--mock"])
    assert rc == 0
    verdicts = read_models(out, LLMVerdict)
    assert [v.sample_id for v in verdicts] == ["vuln_001", "tie_alpha"]


def test_cli_mock_mode_vulnerable_forces_verdict(fixtures_dir: Path, tmp_path: Path):
    out = tmp_path / "verdicts.jsonl"
    verify_main(
        _common_args(fixtures_dir, out)
        + ["--top-k", "5", "--mock", "--mock-mode", "vulnerable"]
    )
    verdicts = read_models(out, LLMVerdict)
    assert {v.verdict for v in verdicts} == {"vulnerable"}


def test_cli_cost_log_written(fixtures_dir: Path, tmp_path: Path):
    out = tmp_path / "verdicts.jsonl"
    cost = tmp_path / "cost.jsonl"
    verify_main(
        _common_args(fixtures_dir, out)
        + ["--top-k", "3", "--mock", "--cost-log", str(cost)]
    )
    assert cost.exists()
    lines = cost.read_text().strip().splitlines()
    assert len(lines) == 3
    rec = json.loads(lines[0])
    assert rec["success"] is True
    assert "Bearer" not in cost.read_text()


def test_cli_dry_run_prompts_makes_no_llm_calls(
    fixtures_dir: Path, tmp_path: Path, capsys
):
    out = tmp_path / "prompts.jsonl"
    rc = verify_main(
        _common_args(fixtures_dir, out) + ["--top-k", "3", "--dry-run-prompts"]
    )
    assert rc == 0
    assert "no LLM calls" in capsys.readouterr().out

    rows = list(out.read_text().strip().splitlines())
    assert len(rows) == 3
    rec = json.loads(rows[0])
    assert rec["sample_id"] == "vuln_001"
    # Rendered messages are present and well-formed.
    assert [m["role"] for m in rec["messages"]] == ["system", "user"]


def test_verify_function_with_injected_mock_client(fixtures_dir: Path, tmp_path: Path):
    out = tmp_path / "verdicts.jsonl"
    d = _llm_dir(fixtures_dir)
    verdicts = verify(
        features_path=d / "features.jsonl",
        rank_scores_path=d / "rank_scores.jsonl",
        alerts_path=d / "alerts.jsonl",
        output_path=out,
        top_k=3,
        client=MockLLMClient("rule"),
        graph_evidence_path=d / "graph_evidence.json",
    )
    assert [v.sample_id for v in verdicts] == ["vuln_001", "tie_alpha", "tie_beta"]
    by_id = {v.sample_id: v for v in verdicts}
    assert by_id["vuln_001"].verdict == "vulnerable"


def test_verify_requires_a_client(fixtures_dir: Path, tmp_path: Path):
    d = _llm_dir(fixtures_dir)
    with pytest.raises(ValueError):
        verify(
            features_path=d / "features.jsonl",
            rank_scores_path=d / "rank_scores.jsonl",
            alerts_path=d / "alerts.jsonl",
            output_path=tmp_path / "out.jsonl",
            top_k=2,
            client=None,
        )
