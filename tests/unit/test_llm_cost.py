"""Tests for the CostLogger."""

from __future__ import annotations

import json
from pathlib import Path

from semvulguard.llm.client import LLMResponse
from semvulguard.llm.cost import CostLogger


def _response() -> LLMResponse:
    return LLMResponse(
        content="{}",
        prompt_tokens=100,
        completion_tokens=20,
        total_tokens=120,
        model="mock",
    )


def test_disabled_logger_is_noop():
    logger = CostLogger(None)
    assert logger.enabled is False
    assert logger.log("s1", "m", _response(), 1.0, True) is None


def test_writes_jsonl_record(tmp_path: Path):
    path = tmp_path / "cost.jsonl"
    logger = CostLogger(path)
    logger.log("s1", "deepseek-chat", _response(), latency_seconds=1.23, success=True)

    lines = path.read_text().strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["sample_id"] == "s1"
    assert rec["model"] == "deepseek-chat"
    assert rec["total_tokens"] == 120
    assert rec["latency_seconds"] == 1.23
    assert rec["success"] is True


def test_appends_multiple_records(tmp_path: Path):
    path = tmp_path / "cost.jsonl"
    logger = CostLogger(path)
    logger.log("s1", "m", _response(), 1.0, True)
    logger.log("s2", "m", _response(), 2.0, True)
    assert len(path.read_text().strip().splitlines()) == 2


def test_failure_record_includes_error_type(tmp_path: Path):
    path = tmp_path / "cost.jsonl"
    logger = CostLogger(path)
    logger.log("s1", "m", None, latency_seconds=0.5, success=False,
               error_type="LLMClientError")
    rec = json.loads(path.read_text().strip())
    assert rec["success"] is False
    assert rec["error_type"] == "LLMClientError"
    assert rec["total_tokens"] is None


def test_does_not_log_prompt_or_key(tmp_path: Path):
    path = tmp_path / "cost.jsonl"
    logger = CostLogger(path)
    logger.log("s1", "m", _response(), 1.0, True)
    text = path.read_text()
    # No prompt content / message keys leak into the log.
    assert "messages" not in text
    assert "Authorization" not in text
    assert "Bearer" not in text
