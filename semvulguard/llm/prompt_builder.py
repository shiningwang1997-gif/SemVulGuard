"""Render verification packets into OpenAI-compatible chat messages.

:class:`PromptBuilder` is the only place that turns a
:class:`~semvulguard.schemas.records.VerificationPacket` into the ``messages``
list sent to a client, and that builds the JSON-repair follow-up. It pulls the
structured evidence summary from ``packet.context["evidence_summary"]`` when
present (the packet builder puts it there), and falls back to the packet's own
fields otherwise so a hand-built packet still renders sensibly.

Pure and deterministic: no I/O, no network, stable JSON serialization.
"""

from __future__ import annotations

import json

from semvulguard.llm.prompt_templates import (
    JSON_REPAIR_SYSTEM_PROMPT,
    JSON_REPAIR_USER_TEMPLATE,
    REQUIRED_JSON_SCHEMA_TEXT,
    VERIFICATION_SYSTEM_PROMPT,
    VERIFICATION_USER_TEMPLATE,
)
from semvulguard.schemas.records import VerificationPacket

EVIDENCE_SUMMARY_KEY = "evidence_summary"


def _dumps(obj: object) -> str:
    """Stable, readable JSON for embedding in a prompt."""
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False)


class PromptBuilder:
    """Build verification and JSON-repair message lists from packets."""

    def build_verification_messages(self, packet: VerificationPacket) -> list[dict]:
        """Render a packet into ``[system, user]`` verification messages."""
        evidence_summary, extra_context = self._split_context(packet)
        span = packet.span

        context_section = ""
        if extra_context:
            context_section = (
                "\nAdditional context (JSON):\n"
                + _dumps(extra_context)
                + "\n"
            )

        user_content = VERIFICATION_USER_TEMPLATE.format(
            sample_id=packet.sample_id,
            language=packet.language,
            span_file=span.file,
            span_start=span.start_line,
            span_end=span.end_line,
            function_code=packet.function_code,
            alerts_json=_dumps([a.model_dump() for a in packet.static_alerts]),
            evidence_json=_dumps(evidence_summary),
            context_section=context_section,
            schema_json=REQUIRED_JSON_SCHEMA_TEXT,
        )

        return [
            {"role": "system", "content": VERIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

    def build_json_repair_messages(
        self,
        raw_response: str,
        error_message: str,
        expected_sample_id: str,
    ) -> list[dict]:
        """Render the JSON-repair follow-up for an invalid response."""
        user_content = JSON_REPAIR_USER_TEMPLATE.format(
            expected_sample_id=expected_sample_id,
            error_message=error_message,
            raw_response=raw_response,
            schema_json=REQUIRED_JSON_SCHEMA_TEXT,
        )
        return [
            {"role": "system", "content": JSON_REPAIR_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

    @staticmethod
    def _split_context(packet: VerificationPacket) -> tuple[dict, dict]:
        """Separate the evidence summary from any other context on the packet.

        Returns ``(evidence_summary, extra_context)``. When the packet carries
        no pre-built summary, the Joern evidence is used as a minimal stand-in so
        the prompt still conveys structured evidence.
        """
        context = dict(packet.context or {})
        evidence_summary = context.pop(EVIDENCE_SUMMARY_KEY, None)
        if evidence_summary is None:
            evidence_summary = {}
            if packet.joern_evidence:
                evidence_summary = {"joern_evidence": packet.joern_evidence}
        return evidence_summary, context


__all__ = ["PromptBuilder", "EVIDENCE_SUMMARY_KEY"]
