"""Tests for the verification-packet builder and Top-K selection."""

from __future__ import annotations

from pathlib import Path

import pytest

from semvulguard.llm.packet import (
    build_verification_packet,
    select_topk_candidates,
)
from semvulguard.llm.prompt_builder import EVIDENCE_SUMMARY_KEY
from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import StaticAlertRecord, VerificationPacket
from semvulguard.utils.jsonl import read_models


def _llm_dir(fixtures_dir: Path) -> Path:
    return fixtures_dir / "llm"


def _feature(fixtures_dir: Path, sample_id: str) -> FeatureRecord:
    records = read_models(_llm_dir(fixtures_dir) / "features.jsonl", FeatureRecord)
    return next(r for r in records if r.sample_id == sample_id)


def test_build_packet_returns_verification_packet(fixtures_dir: Path):
    feature = _feature(fixtures_dir, "vuln_001")
    alerts = read_models(_llm_dir(fixtures_dir) / "alerts.jsonl", StaticAlertRecord)
    sample_alerts = [a for a in alerts if a.sample_id == "vuln_001"]

    packet = build_verification_packet(
        feature_record=feature,
        alerts=sample_alerts,
        rank_score=0.95,
        joern_evidence={"sinks": ["memcpy"]},
        context={"caller": "handle"},
    )

    assert isinstance(packet, VerificationPacket)
    assert packet.sample_id == "vuln_001"
    assert packet.language == "c"
    assert packet.function_code == feature.function_code
    assert packet.span == feature.span
    assert len(packet.static_alerts) == 2
    assert packet.joern_evidence == {"sinks": ["memcpy"]}
    # Caller context is preserved alongside the evidence summary.
    assert packet.context["caller"] == "handle"
    assert EVIDENCE_SUMMARY_KEY in packet.context


def test_packet_embeds_structured_evidence_summary(fixtures_dir: Path):
    feature = _feature(fixtures_dir, "vuln_001")
    alerts = read_models(_llm_dir(fixtures_dir) / "alerts.jsonl", StaticAlertRecord)
    sample_alerts = [a for a in alerts if a.sample_id == "vuln_001"]

    packet = build_verification_packet(
        feature_record=feature, alerts=sample_alerts, rank_score=0.95
    )
    summary = packet.context[EVIDENCE_SUMMARY_KEY]
    assert summary["sample_id"] == "vuln_001"
    assert summary["rank_score"] == 0.95
    assert summary["static_alert_count"] == 2
    assert "dangerous_api_lines" in summary


def test_build_packet_defaults_for_optional_fields(fixtures_dir: Path):
    feature = _feature(fixtures_dir, "benign_002")
    packet = build_verification_packet(feature_record=feature, alerts=[])
    assert packet.static_alerts == []
    assert packet.joern_evidence == {}
    # Only the evidence summary is added when no extra context is supplied.
    assert set(packet.context) == {EVIDENCE_SUMMARY_KEY}


def test_topk_orders_by_descending_score(fixtures_dir: Path):
    ids = select_topk_candidates(_llm_dir(fixtures_dir) / "rank_scores.jsonl", k=2)
    assert ids == ["vuln_001", "tie_alpha"]


def test_topk_tie_break_is_stable_by_sample_id(fixtures_dir: Path):
    ids = select_topk_candidates(_llm_dir(fixtures_dir) / "rank_scores.jsonl", k=3)
    assert ids == ["vuln_001", "tie_alpha", "tie_beta"]


def test_topk_larger_than_available_returns_all(fixtures_dir: Path):
    ids = select_topk_candidates(_llm_dir(fixtures_dir) / "rank_scores.jsonl", k=100)
    assert len(ids) == 5


def test_topk_rejects_non_positive_k(fixtures_dir: Path):
    path = _llm_dir(fixtures_dir) / "rank_scores.jsonl"
    with pytest.raises(ValueError):
        select_topk_candidates(path, k=0)
    with pytest.raises(ValueError):
        select_topk_candidates(path, k=-3)
