"""Tests for the LLMVerifier orchestration."""

from __future__ import annotations

import json
from pathlib import Path

from semvulguard.llm.client import LLMResponse
from semvulguard.llm.cost import CostLogger
from semvulguard.llm.mock import MockLLMClient
from semvulguard.llm.packet import build_verification_packet
from semvulguard.llm.verifier import LLMVerifier
from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import CodeSpan, LLMVerdict, StaticAlertRecord


def _feature(sample_id="s1", code="void f(){ memcpy(d,s,n); }") -> FeatureRecord:
    return FeatureRecord(
        sample_id=sample_id,
        label=1,
        cwe=["CWE-119"],
        file="a.c",
        function="f",
        span=CodeSpan(file="a.c", start_line=1, end_line=3),
        function_code=code,
        code_lines=code.splitlines() or [code],
        static_features={"language": "c"},
    )


def _packet(sample_id="s1", code="void f(){ memcpy(d,s,n); }"):
    return build_verification_packet(
        feature_record=_feature(sample_id, code),
        alerts=[
            StaticAlertRecord(
                sample_id=sample_id,
                tool="codeql",
                query_id="q",
                message="m",
                severity="high",
                file="a.c",
                start_line=1,
                end_line=1,
            )
        ],
        rank_score=0.9,
    )


def test_verify_one_with_mock_rule_client():
    verifier = LLMVerifier(client=MockLLMClient("rule"))
    verdict = verifier.verify_one(_packet())
    assert isinstance(verdict, LLMVerdict)
    assert verdict.sample_id == "s1"
    assert verdict.verdict == "vulnerable"  # unguarded memcpy


def test_verify_batch_preserves_order():
    verifier = LLMVerifier(client=MockLLMClient("vulnerable"))
    packets = [_packet("a"), _packet("b"), _packet("c")]
    verdicts = verifier.verify_batch(packets)
    assert [v.sample_id for v in verdicts] == ["a", "b", "c"]
    assert all(v.verdict == "vulnerable" for v in verdicts)


class _JSONOnlyClient:
    """A client that only implements complete_json (legacy interface)."""

    def complete_json(self, messages):
        return {
            "sample_id": "",
            "verdict": "benign",
            "confidence": 0.7,
            "predicted_cwe": "",
            "vulnerable_lines": [],
            "evidence": [],
            "need_more_context": False,
            "missing_context": [],
            "patch_hint": "",
        }


def test_verifier_supports_legacy_complete_json_client():
    verifier = LLMVerifier(client=_JSONOnlyClient())
    verdict = verifier.verify_one(_packet("s1"))
    assert verdict.verdict == "benign"
    assert verdict.sample_id == "s1"  # filled from packet


class _BadClient:
    """A client whose complete returns content that never validates."""

    def complete(self, messages):
        return LLMResponse(content="not json at all", total_tokens=5)


def test_verifier_degrades_to_uncertain_on_unparseable():
    verifier = LLMVerifier(client=_BadClient(), max_retries=1)
    verdict = verifier.verify_one(_packet("s1"))
    assert verdict.verdict == "uncertain"
    assert verdict.need_more_context is True


class _RaisingClient:
    """A client that raises a transport-style error."""

    def complete(self, messages):
        raise RuntimeError("connection reset")


def test_verifier_handles_client_exception(tmp_path: Path):
    cost_path = tmp_path / "cost.jsonl"
    verifier = LLMVerifier(
        client=_RaisingClient(), cost_logger=CostLogger(cost_path)
    )
    verdict = verifier.verify_one(_packet("s1"))
    assert verdict.verdict == "uncertain"
    # The failure is logged with an error type and success=False.
    rec = json.loads(cost_path.read_text().strip())
    assert rec["success"] is False
    assert rec["error_type"] == "RuntimeError"


def test_verifier_logs_cost_on_success(tmp_path: Path):
    cost_path = tmp_path / "cost.jsonl"
    verifier = LLMVerifier(
        client=MockLLMClient("rule"), cost_logger=CostLogger(cost_path)
    )
    verifier.verify_one(_packet("s1"))
    rec = json.loads(cost_path.read_text().strip())
    assert rec["success"] is True
    assert rec["total_tokens"] is not None
