"""Tests for LLM verdict parsing, repair, and schema validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from semvulguard.llm.client import parse_llm_verdict
from semvulguard.schemas.records import LLMVerdict


def _valid(**overrides) -> dict:
    base = {
        "sample_id": "s1",
        "verdict": "vulnerable",
        "confidence": 0.9,
        "predicted_cwe": "CWE-119",
        "vulnerable_lines": [12],
        "evidence": [],
        "need_more_context": False,
        "missing_context": [],
        "patch_hint": "bound the copy",
    }
    base.update(overrides)
    return base


def test_parses_fixture_responses(fixtures_dir: Path):
    llm_dir = fixtures_dir / "llm"
    vuln = json.loads(
        (llm_dir / "mock_response_vulnerable.json").read_text()
    )
    benign = json.loads((llm_dir / "mock_response_benign.json").read_text())
    assert parse_llm_verdict(vuln, "vuln_001").verdict == "vulnerable"
    assert parse_llm_verdict(benign, "benign_002").verdict == "benign"


def test_accepts_json_string_input():
    verdict = parse_llm_verdict(json.dumps(_valid()), "s1")
    assert isinstance(verdict, LLMVerdict)
    assert verdict.sample_id == "s1"


def test_fills_missing_sample_id():
    raw = _valid()
    del raw["sample_id"]
    assert parse_llm_verdict(raw, "expected_id").sample_id == "expected_id"


def test_fills_empty_sample_id():
    assert parse_llm_verdict(_valid(sample_id=""), "expected_id").sample_id == (
        "expected_id"
    )


def test_clamps_slightly_high_confidence():
    assert parse_llm_verdict(_valid(confidence=1.0001), "s1").confidence == 1.0


def test_clamps_slightly_low_confidence():
    assert parse_llm_verdict(_valid(confidence=-0.01), "s1").confidence == 0.0


def test_rejects_wildly_out_of_range_confidence():
    with pytest.raises(ValueError):
        parse_llm_verdict(_valid(confidence=1.8), "s1")
    with pytest.raises(ValueError):
        parse_llm_verdict(_valid(confidence=-0.5), "s1")


def test_rejects_invalid_verdict_label():
    with pytest.raises(ValidationError):
        parse_llm_verdict(_valid(verdict="maybe"), "s1")


def test_rejects_non_positive_vulnerable_lines():
    with pytest.raises(ValidationError):
        parse_llm_verdict(_valid(vulnerable_lines=[0, 5]), "s1")
    with pytest.raises(ValidationError):
        parse_llm_verdict(_valid(vulnerable_lines=[-3]), "s1")


def test_rejects_invalid_json_string():
    with pytest.raises(json.JSONDecodeError):
        parse_llm_verdict("{not valid json", "s1")
