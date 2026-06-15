"""The semantic verifier: orchestrate prompt -> client -> parse -> verdict.

:class:`LLMVerifier` ties the subsystem together. For each
:class:`~semvulguard.schemas.records.VerificationPacket` it builds the
verification messages, calls the client (real or mock), parses the response with
JSON-repair retries, logs cost, and returns a validated
:class:`~semvulguard.schemas.records.LLMVerdict`.

The verifier is client-agnostic: it prefers a client exposing ``complete`` (so
it can capture token usage) and falls back to ``complete_json``. A single bad
sample degrades to a conservative ``uncertain`` verdict rather than aborting a
batch.
"""

from __future__ import annotations

import time

from semvulguard.llm.client import LLMResponse
from semvulguard.llm.cost import CostLogger
from semvulguard.llm.parser import LLMResponseParser
from semvulguard.llm.prompt_builder import PromptBuilder
from semvulguard.llm.retry import RetryPolicy
from semvulguard.schemas.records import LLMVerdict, VerificationPacket
from semvulguard.utils.logging import get_logger

LOGGER = get_logger("semvulguard.llm.verifier")


class LLMVerifier:
    """Verify candidate functions with a schema-constrained LLM call."""

    def __init__(
        self,
        client,
        model: str = "deepseek-chat",
        max_retries: int = 3,
        cost_logger: CostLogger | None = None,
        prompt_builder: PromptBuilder | None = None,
        parser: LLMResponseParser | None = None,
    ) -> None:
        self.client = client
        self.model = model
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.parser = parser or LLMResponseParser()
        self.retry_policy = RetryPolicy(
            parser=self.parser,
            prompt_builder=self.prompt_builder,
            max_retries=max_retries,
        )
        self.cost_logger = cost_logger

    def verify_one(self, packet: VerificationPacket) -> LLMVerdict:
        """Verify a single packet, returning a validated verdict."""
        messages = self.prompt_builder.build_verification_messages(packet)

        start = time.perf_counter()
        response: LLMResponse | None = None
        error_type: str | None = None
        try:
            raw, response = self._call(messages)
            verdict = self.retry_policy.parse_with_repair(
                raw=raw,
                expected_sample_id=packet.sample_id,
                client_call=self._repair_call,
            )
            success = True
        except Exception as exc:  # transport / client error
            error_type = type(exc).__name__
            LOGGER.warning(
                "client error for %s: %s; returning uncertain verdict",
                packet.sample_id,
                error_type,
            )
            from semvulguard.llm.retry import conservative_uncertain_verdict

            verdict = conservative_uncertain_verdict(
                packet.sample_id, f"client error: {error_type}"
            )
            success = False

        latency = time.perf_counter() - start
        if self.cost_logger is not None:
            self.cost_logger.log(
                sample_id=packet.sample_id,
                model=self.model,
                response=response,
                latency_seconds=latency,
                success=success,
                error_type=error_type,
            )
        return verdict

    def verify_batch(self, packets: list[VerificationPacket]) -> list[LLMVerdict]:
        """Verify a list of packets in order."""
        return [self.verify_one(packet) for packet in packets]

    # -- client adapters ----------------------------------------------------

    def _call(self, messages: list[dict]) -> tuple[str | dict, LLMResponse | None]:
        """Call the client, returning ``(raw, response_or_None)``.

        Prefers ``complete`` (captures token usage) and falls back to
        ``complete_json`` for clients that only implement the legacy interface.
        """
        if hasattr(self.client, "complete"):
            response = self.client.complete(messages)
            return response.content, response
        raw = self.client.complete_json(messages)
        return raw, None

    def _repair_call(self, messages: list[dict]) -> str | dict:
        """Raw client call used by the retry policy for repair rounds."""
        raw, _ = self._call(messages)
        return raw


__all__ = ["LLMVerifier"]
