"""Tests for the RetryPolicy / JSON-repair behavior."""

from __future__ import annotations

import json

from semvulguard.llm.retry import RetryPolicy, conservative_uncertain_verdict
from semvulguard.schemas.records import LLMVerdict


def _valid_dict(sample_id="s1") -> dict:
    return {
        "sample_id": sample_id,
        "verdict": "vulnerable",
        "confidence": 0.9,
        "predicted_cwe": "CWE-119",
        "vulnerable_lines": [12],
        "evidence": [],
        "need_more_context": False,
        "missing_context": [],
        "patch_hint": "fix",
    }


class _ScriptedClient:
    """Returns a queued sequence of raw responses on each repair call."""

    def __init__(self, responses: list):
        self._responses = list(responses)
        self.calls = 0

    def __call__(self, messages: list[dict]):
        self.calls += 1
        return self._responses.pop(0)


def test_first_attempt_success_no_repair():
    policy = RetryPolicy(max_retries=3)
    client = _ScriptedClient([])  # should never be called
    verdict = policy.parse_with_repair(_valid_dict(), "s1", client)
    assert verdict.verdict == "vulnerable"
    assert client.calls == 0


def test_repair_recovers_after_one_failure():
    policy = RetryPolicy(max_retries=3)
    # First raw (passed in) is broken; repair returns valid JSON text.
    client = _ScriptedClient([json.dumps(_valid_dict())])
    verdict = policy.parse_with_repair("{broken", "s1", client)
    assert verdict.verdict == "vulnerable"
    assert client.calls == 1


def test_repeated_failure_yields_uncertain_verdict():
    policy = RetryPolicy(max_retries=2)
    # Every repair also fails to parse.
    client = _ScriptedClient(["still broken", "still broken again"])
    verdict = policy.parse_with_repair("{broken", "s1", client)
    assert isinstance(verdict, LLMVerdict)
    assert verdict.verdict == "uncertain"
    assert verdict.confidence == 0.0
    assert verdict.predicted_cwe == "unknown"
    assert verdict.need_more_context is True
    assert verdict.missing_context  # records the failure reason
    # max_retries=2 -> two repair calls after the initial parse.
    assert client.calls == 2


def test_invalid_schema_then_repair_to_valid():
    policy = RetryPolicy(max_retries=2)
    # Initial dict has a bad verdict label; repair fixes it.
    bad = _valid_dict()
    bad["verdict"] = "maybe"
    client = _ScriptedClient([_valid_dict()])
    verdict = policy.parse_with_repair(bad, "s1", client)
    assert verdict.verdict == "vulnerable"
    assert client.calls == 1


def test_conservative_uncertain_verdict_shape():
    verdict = conservative_uncertain_verdict("s9", "boom")
    assert verdict.sample_id == "s9"
    assert verdict.verdict == "uncertain"
    assert "boom" in verdict.missing_context[0]
