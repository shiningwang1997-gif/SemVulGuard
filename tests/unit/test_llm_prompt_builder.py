"""Tests for the PromptBuilder (verification + JSON-repair messages)."""

from __future__ import annotations

import json

from semvulguard.llm.packet import build_verification_packet
from semvulguard.llm.prompt_builder import PromptBuilder
from semvulguard.llm.prompts import build_verification_prompt
from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import (
    CodeSpan,
    StaticAlertRecord,
    VerificationPacket,
)


def _feature() -> FeatureRecord:
    return FeatureRecord(
        sample_id="vuln_001",
        label=1,
        cwe=["CWE-119"],
        file="net/pkt.c",
        function="f",
        span=CodeSpan(file="net/pkt.c", start_line=10, end_line=16),
        function_code=(
            "void f(char *d, const char *s, int n) {\n    memcpy(d, s, n);\n}"
        ),
        code_lines=[
            "void f(char *d, const char *s, int n) {",
            "    memcpy(d, s, n);",
            "}",
        ],
        alert_lines=[11],
        trace_lines=[11],
        static_features={"language": "c"},
    )


def _alert() -> StaticAlertRecord:
    return StaticAlertRecord(
        sample_id="vuln_001",
        tool="codeql",
        query_id="cpp/unbounded-write",
        message="Unbounded copy into fixed-size buffer",
        severity="high",
        file="net/pkt.c",
        start_line=11,
        end_line=11,
        cwe=["CWE-119"],
        trace_lines=[11],
    )


def _packet() -> VerificationPacket:
    return build_verification_packet(
        feature_record=_feature(),
        alerts=[_alert()],
        rank_score=0.91,
        joern_evidence={"sinks": ["memcpy"]},
    )


def test_returns_system_then_user_messages():
    messages = PromptBuilder().build_verification_messages(_packet())
    assert [m["role"] for m in messages] == ["system", "user"]


def test_system_prompt_is_conservative_and_json_only():
    messages = PromptBuilder().build_verification_messages(_packet())
    system = messages[0]["content"]
    assert "secure-code semantic verifier" in system
    assert "JSON only" in system
    assert "conservative" in system.lower()
    assert "uncertain" in system
    assert "need_more_context" in system


def test_user_prompt_contains_code_evidence_rank_and_schema():
    user = PromptBuilder().build_verification_messages(_packet())[1]["content"]
    # Function code is embedded.
    assert "memcpy(d, s, n)" in user
    # Span information.
    assert "net/pkt.c" in user
    assert "10-16" in user
    # Static alerts.
    assert "cpp/unbounded-write" in user
    # Structured evidence summary, including the rank score.
    assert "Structured static evidence" in user
    assert "rank_score" in user
    assert "0.91" in user
    assert "dangerous_api_lines" in user
    # Required schema fields all appear.
    for field in [
        "sample_id",
        "verdict",
        "confidence",
        "predicted_cwe",
        "vulnerable_lines",
        "evidence",
        "need_more_context",
        "missing_context",
        "patch_hint",
    ]:
        assert field in user


def test_prompt_is_deterministic():
    a = PromptBuilder().build_verification_messages(_packet())
    b = PromptBuilder().build_verification_messages(_packet())
    assert a == b


def test_backward_compatible_wrapper_matches_builder():
    packet = _packet()
    assert build_verification_prompt(packet) == (
        PromptBuilder().build_verification_messages(packet)
    )


def test_evidence_summary_embedded_as_valid_json():
    user = PromptBuilder().build_verification_messages(_packet())[1]["content"]
    start = user.index("{", user.index("Structured static evidence"))
    parsed, _ = json.JSONDecoder().raw_decode(user[start:])
    assert parsed["sample_id"] == "vuln_001"
    assert parsed["rank_score"] == 0.91


def test_json_repair_messages():
    builder = PromptBuilder()
    messages = builder.build_json_repair_messages(
        raw_response="not json",
        error_message="JSONDecodeError: boom",
        expected_sample_id="vuln_001",
    )
    assert [m["role"] for m in messages] == ["system", "user"]
    assert "JSON repair" in messages[0]["content"]
    user = messages[1]["content"]
    assert "vuln_001" in user
    assert "JSONDecodeError: boom" in user
    assert "not json" in user


def test_optional_context_included_when_present():
    packet = build_verification_packet(
        feature_record=_feature(),
        alerts=[_alert()],
        rank_score=0.5,
        context={"caller": "handle_packet"},
    )
    user = PromptBuilder().build_verification_messages(packet)[1]["content"]
    assert "Additional context" in user
    assert "handle_packet" in user
