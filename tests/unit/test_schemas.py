"""Schema validation tests for the cross-module record contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from semvulguard.schemas.records import (
    CodeSpan,
    FinalFinding,
    LLMVerdict,
    SampleRecord,
    StaticAlertRecord,
    VerificationPacket,
)


def _make_span() -> CodeSpan:
    return CodeSpan(file="a.c", start_line=10, end_line=20)


# --- valid construction -----------------------------------------------------


def test_code_span_valid():
    span = CodeSpan(file="a.c", start_line=1, end_line=1)
    assert span.start_line == 1
    assert span.end_line == 1


def test_sample_record_valid_and_language_normalized():
    rec = SampleRecord(
        sample_id="s1",
        dataset="diversevul",
        language="C",
        repo="openssl",
        commit_before="abc",
        commit_after="def",
        file="a.c",
        function="f",
        span=_make_span(),
        label=1,
        cwe=["CWE-119"],
        split="train",
    )
    assert rec.language == "c"  # normalized to lowercase
    assert rec.label == 1


def test_sample_record_optional_fields_default_none():
    rec = SampleRecord(
        sample_id="s2",
        dataset="d",
        language="cpp",
        file="a.cpp",
        span=_make_span(),
        label=0,
        split="unknown",
    )
    assert rec.repo is None
    assert rec.function is None
    assert rec.cwe == []


def test_static_alert_record_valid():
    alert = StaticAlertRecord(
        sample_id="s1",
        tool="codeql",
        query_id="cpp/uaf",
        message="use after free",
        severity="high",
        file="a.c",
        start_line=145,
        end_line=146,
        cwe=["CWE-416"],
        trace_lines=[132, 140, 145],
    )
    assert alert.trace_lines == [132, 140, 145]
    assert alert.raw is None


def test_verification_packet_valid():
    packet = VerificationPacket(
        sample_id="s1",
        language="c",
        function_code="int main() {}",
        span=_make_span(),
        static_alerts=[],
        joern_evidence={"pdg_lines": [1, 2]},
        context={"caller_summary": []},
    )
    assert packet.joern_evidence["pdg_lines"] == [1, 2]


def test_llm_verdict_valid():
    verdict = LLMVerdict(
        sample_id="s1",
        verdict="vulnerable",
        confidence=0.9,
        predicted_cwe="CWE-416",
        vulnerable_lines=[145, 146],
        evidence=[{"kind": "llm_reasoning"}],
        need_more_context=False,
        missing_context=[],
        patch_hint="reset pointer",
    )
    assert verdict.verdict == "vulnerable"


def test_final_finding_valid():
    finding = FinalFinding(
        sample_id="s1",
        final_label=1,
        final_confidence=0.91,
        predicted_cwe="CWE-416",
        vulnerable_lines=[145],
        evidence=[],
        patch_hint="",
    )
    assert finding.final_label == 1


# --- invalid line numbers ---------------------------------------------------


def test_code_span_end_before_start_rejected():
    with pytest.raises(ValidationError):
        CodeSpan(file="a.c", start_line=20, end_line=10)


def test_code_span_zero_start_rejected():
    with pytest.raises(ValidationError):
        CodeSpan(file="a.c", start_line=0, end_line=10)


def test_static_alert_end_before_start_rejected():
    with pytest.raises(ValidationError):
        StaticAlertRecord(
            sample_id="s1",
            tool="codeql",
            query_id="q",
            message="m",
            file="a.c",
            start_line=50,
            end_line=10,
        )


def test_static_alert_nonpositive_trace_line_rejected():
    with pytest.raises(ValidationError):
        StaticAlertRecord(
            sample_id="s1",
            tool="codeql",
            query_id="q",
            message="m",
            file="a.c",
            start_line=10,
            end_line=10,
            trace_lines=[0, 5],
        )


def test_llm_verdict_nonpositive_vulnerable_line_rejected():
    with pytest.raises(ValidationError):
        LLMVerdict(
            sample_id="s1",
            verdict="vulnerable",
            confidence=0.5,
            predicted_cwe="CWE-416",
            vulnerable_lines=[-1],
            need_more_context=False,
            patch_hint="",
        )


def test_final_finding_nonpositive_vulnerable_line_rejected():
    with pytest.raises(ValidationError):
        FinalFinding(
            sample_id="s1",
            final_label=1,
            final_confidence=0.5,
            predicted_cwe="CWE-416",
            vulnerable_lines=[0],
            patch_hint="",
        )


# --- invalid label values ---------------------------------------------------


@pytest.mark.parametrize("bad_label", [-1, 2, 100])
def test_sample_record_invalid_label_rejected(bad_label):
    with pytest.raises(ValidationError):
        SampleRecord(
            sample_id="s1",
            dataset="d",
            language="c",
            file="a.c",
            span=_make_span(),
            label=bad_label,
            split="train",
        )


def test_sample_record_invalid_split_rejected():
    with pytest.raises(ValidationError):
        SampleRecord(
            sample_id="s1",
            dataset="d",
            language="c",
            file="a.c",
            span=_make_span(),
            label=1,
            split="validation",  # not in allowed set
        )


@pytest.mark.parametrize("bad_label", [-1, 2])
def test_final_finding_invalid_label_rejected(bad_label):
    with pytest.raises(ValidationError):
        FinalFinding(
            sample_id="s1",
            final_label=bad_label,
            final_confidence=0.5,
            predicted_cwe="CWE-416",
            vulnerable_lines=[],
            patch_hint="",
        )


# --- invalid LLM verdict / confidence ---------------------------------------


def test_llm_verdict_invalid_verdict_value_rejected():
    with pytest.raises(ValidationError):
        LLMVerdict(
            sample_id="s1",
            verdict="maybe",  # not in Literal set
            confidence=0.5,
            predicted_cwe="CWE-416",
            need_more_context=False,
            patch_hint="",
        )


@pytest.mark.parametrize("bad_conf", [-0.1, 1.1, 2.0])
def test_llm_verdict_confidence_out_of_range_rejected(bad_conf):
    with pytest.raises(ValidationError):
        LLMVerdict(
            sample_id="s1",
            verdict="uncertain",
            confidence=bad_conf,
            predicted_cwe="",
            need_more_context=True,
            patch_hint="",
        )


@pytest.mark.parametrize("bad_conf", [-0.1, 1.5])
def test_final_finding_confidence_out_of_range_rejected(bad_conf):
    with pytest.raises(ValidationError):
        FinalFinding(
            sample_id="s1",
            final_label=1,
            final_confidence=bad_conf,
            predicted_cwe="",
            patch_hint="",
        )
