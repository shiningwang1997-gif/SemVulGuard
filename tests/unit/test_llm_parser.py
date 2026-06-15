"""Tests for the LLMResponseParser."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from semvulguard.llm.parser import LLMResponseParser, parse_llm_verdict
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


def test_parses_dict_response():
    verdict = LLMResponseParser().parse_raw_response(_valid(), "s1")
    assert isinstance(verdict, LLMVerdict)
    assert verdict.verdict == "vulnerable"


def test_parses_json_string():
    verdict = LLMResponseParser().parse_raw_response(json.dumps(_valid()), "s1")
    assert verdict.sample_id == "s1"


def test_parses_markdown_fenced_json():
    raw = "```json\n" + json.dumps(_valid()) + "\n```"
    verdict = LLMResponseParser().parse_raw_response(raw, "s1")
    assert verdict.verdict == "vulnerable"


def test_parses_bare_fenced_json():
    raw = "```\n" + json.dumps(_valid()) + "\n```"
    verdict = LLMResponseParser().parse_raw_response(raw, "s1")
    assert verdict.verdict == "vulnerable"


def test_strip_markdown_code_fence_noop_on_plain():
    parser = LLMResponseParser()
    assert parser.strip_markdown_code_fence('{"a": 1}') == '{"a": 1}'


def test_fills_missing_sample_id():
    raw = _valid()
    del raw["sample_id"]
    assert LLMResponseParser().parse_raw_response(raw, "expected").sample_id == (
        "expected"
    )


def test_fills_empty_sample_id():
    verdict = LLMResponseParser().parse_raw_response(_valid(sample_id=""), "exp")
    assert verdict.sample_id == "exp"


def test_clamps_slightly_out_of_range_confidence():
    assert LLMResponseParser().parse_raw_response(
        _valid(confidence=1.0001), "s1"
    ).confidence == 1.0
    assert LLMResponseParser().parse_raw_response(
        _valid(confidence=-0.01), "s1"
    ).confidence == 0.0


def test_rejects_wildly_out_of_range_confidence():
    with pytest.raises(ValueError):
        LLMResponseParser().parse_raw_response(_valid(confidence=1.8), "s1")


def test_rejects_invalid_verdict_label():
    with pytest.raises(ValidationError):
        LLMResponseParser().parse_raw_response(_valid(verdict="maybe"), "s1")


def test_rejects_non_positive_vulnerable_lines():
    with pytest.raises(ValidationError):
        LLMResponseParser().parse_raw_response(_valid(vulnerable_lines=[0]), "s1")
    with pytest.raises(ValidationError):
        LLMResponseParser().parse_raw_response(_valid(vulnerable_lines=[-3]), "s1")


def test_rejects_invalid_json_string():
    with pytest.raises(json.JSONDecodeError):
        LLMResponseParser().parse_raw_response("{not valid json", "s1")


def test_functional_wrapper_matches_class():
    assert parse_llm_verdict(_valid(), "s1").verdict == "vulnerable"
