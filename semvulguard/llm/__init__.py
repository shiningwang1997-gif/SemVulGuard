"""Static-Evidence-Guided LLM Semantic Verification subsystem.

A schema-constrained verifier (not a free-form agent): each Top-K candidate is
turned into a :class:`~semvulguard.schemas.records.VerificationPacket` carrying
a structured static-evidence summary, rendered into a JSON-only prompt, sent to
a client (:class:`DeepSeekClient` or the offline :class:`MockLLMClient`), and
parsed -- with JSON-repair retries -- into a validated
:class:`~semvulguard.schemas.records.LLMVerdict`.

Pipeline: :class:`EvidenceCollector` -> :func:`build_verification_packet` ->
:class:`PromptBuilder` -> client -> :class:`LLMResponseParser` /
:class:`RetryPolicy` -> :class:`CostLogger` -> :class:`LLMVerifier`.
"""

from semvulguard.llm.client import (
    DeepSeekClient,
    LLMClientError,
    LLMResponse,
)
from semvulguard.llm.config import LLMConfig
from semvulguard.llm.cost import CostLogger
from semvulguard.llm.evidence import EvidenceCollector
from semvulguard.llm.mock import MockLLMClient
from semvulguard.llm.packet import (
    build_verification_packet,
    select_topk_candidates,
)
from semvulguard.llm.parser import LLMResponseParser, parse_llm_verdict
from semvulguard.llm.prompt_builder import PromptBuilder
from semvulguard.llm.prompts import build_verification_prompt
from semvulguard.llm.retry import RetryPolicy
from semvulguard.llm.verifier import LLMVerifier

__all__ = [
    "LLMConfig",
    "EvidenceCollector",
    "PromptBuilder",
    "DeepSeekClient",
    "LLMClientError",
    "LLMResponse",
    "MockLLMClient",
    "LLMResponseParser",
    "RetryPolicy",
    "CostLogger",
    "LLMVerifier",
    "build_verification_packet",
    "select_topk_candidates",
    "build_verification_prompt",
    "parse_llm_verdict",
]
