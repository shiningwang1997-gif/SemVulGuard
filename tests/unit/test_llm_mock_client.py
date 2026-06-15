"""Tests for the deterministic, offline mock LLM client."""

from __future__ import annotations

import pytest

from semvulguard.llm.client import parse_llm_verdict
from semvulguard.llm.mock import MockLLMClient


def _messages(code: str, sample_id: str = "s1") -> list[dict]:
    return [
        {"role": "system", "content": "verifier"},
        {"role": "user", "content": f"sample_id: {sample_id}\n```c\n{code}\n```"},
    ]


def test_invalid_mode_rejected():
    with pytest.raises(ValueError):
        MockLLMClient(mode="bogus")


def test_fixed_modes_return_their_verdict():
    msgs = _messages("int f(){return 0;}")
    assert MockLLMClient("vulnerable").complete_json(msgs)["verdict"] == "vulnerable"
    assert MockLLMClient("benign").complete_json(msgs)["verdict"] == "benign"
    assert MockLLMClient("uncertain").complete_json(msgs)["verdict"] == "uncertain"


def test_fixed_modes_echo_sample_id():
    msgs = _messages("int f(){return 0;}", sample_id="abc_123")
    assert MockLLMClient("vulnerable").complete_json(msgs)["sample_id"] == "abc_123"


def test_rule_mode_flags_risky_sink_without_check():
    msgs = _messages("void f(char*d,char*s,int n){memcpy(d,s,n);}")
    assert MockLLMClient("rule").complete_json(msgs)["verdict"] == "vulnerable"


def test_rule_mode_uncertain_when_guarded():
    msgs = _messages("void f(char*d,char*s,int n){if (n<64){memcpy(d,s,n);}}")
    assert MockLLMClient("rule").complete_json(msgs)["verdict"] == "uncertain"


def test_rule_mode_benign_without_sinks():
    msgs = _messages("int add(int a,int b){return a+b;}")
    assert MockLLMClient("rule").complete_json(msgs)["verdict"] == "benign"


def test_mock_output_passes_verdict_validation():
    msgs = _messages("void f(char*d,char*s,int n){strcpy(d,s);}")
    raw = MockLLMClient("rule").complete_json(msgs)
    verdict = parse_llm_verdict(raw, sample_id="s1")
    assert verdict.verdict == "vulnerable"


def test_mock_is_deterministic():
    msgs = _messages("void f(char*d,char*s,int n){memcpy(d,s,n);}")
    client = MockLLMClient("rule")
    assert client.complete_json(msgs) == client.complete_json(msgs)
