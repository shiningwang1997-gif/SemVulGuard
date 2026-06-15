"""Backward-compatibility wrapper for the old prompt API.

The prompt text now lives in :mod:`semvulguard.llm.prompt_templates` and the
rendering logic in :mod:`semvulguard.llm.prompt_builder`. This module preserves
the historical ``build_verification_prompt`` / ``SYSTEM_PROMPT`` /
``RESPONSE_SCHEMA`` names so existing callers keep working.
"""

from __future__ import annotations

from semvulguard.llm.prompt_builder import PromptBuilder
from semvulguard.llm.prompt_templates import (
    RESPONSE_SCHEMA,
    VERIFICATION_SYSTEM_PROMPT,
)
from semvulguard.schemas.records import VerificationPacket

# Historical alias for the verification system prompt.
SYSTEM_PROMPT = VERIFICATION_SYSTEM_PROMPT

_BUILDER = PromptBuilder()


def build_verification_prompt(packet: VerificationPacket) -> list[dict]:
    """Render a packet into ``[system, user]`` messages (compat wrapper)."""
    return _BUILDER.build_verification_messages(packet)


__all__ = ["build_verification_prompt", "SYSTEM_PROMPT", "RESPONSE_SCHEMA"]
