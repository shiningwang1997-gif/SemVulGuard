"""Retry / JSON-repair policy for parsing model output.

:class:`RetryPolicy` wraps the parse step: when a response fails to parse or
validate, it asks the client to repair its own output using a JSON-repair
prompt, up to ``max_retries`` times. If every attempt fails, it returns a
conservative ``uncertain`` verdict that records the failure reason in
``missing_context`` rather than raising -- a batch run should degrade gracefully
on a single bad sample.

The policy never raises for a bad response; it always yields an ``LLMVerdict``.
"""

from __future__ import annotations

from collections.abc import Callable

from semvulguard.llm.parser import LLMResponseParser
from semvulguard.llm.prompt_builder import PromptBuilder
from semvulguard.schemas.records import LLMVerdict
from semvulguard.utils.logging import get_logger

LOGGER = get_logger("semvulguard.llm.retry")

# Signature of the client call the policy drives: messages -> raw response.
# Raw may be a str or a dict depending on the client/JSON-mode.
ClientCall = Callable[[list[dict]], "str | dict"]


def conservative_uncertain_verdict(
    sample_id: str, reason: str
) -> LLMVerdict:
    """Build the fallback verdict used when parsing ultimately fails."""
    return LLMVerdict(
        sample_id=sample_id,
        verdict="uncertain",
        confidence=0.0,
        predicted_cwe="unknown",
        vulnerable_lines=[],
        evidence=[],
        need_more_context=True,
        missing_context=[f"parse/validation failure: {reason}"],
        patch_hint="",
    )


class RetryPolicy:
    """Drive parse-then-repair retries around a client call."""

    def __init__(
        self,
        parser: LLMResponseParser | None = None,
        prompt_builder: PromptBuilder | None = None,
        max_retries: int = 3,
    ) -> None:
        self.parser = parser or LLMResponseParser()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.max_retries = max_retries

    def parse_with_repair(
        self,
        raw: str | dict,
        expected_sample_id: str,
        client_call: ClientCall,
    ) -> LLMVerdict:
        """Parse ``raw``; on failure, ask the client to repair up to N times.

        ``client_call`` takes a messages list and returns the next raw response
        (the same callable the verifier used for the first attempt). Returns a
        validated verdict, or a conservative ``uncertain`` verdict if all
        repair attempts fail.
        """
        current = raw
        last_error = ""
        # One initial parse plus up to ``max_retries`` repair rounds.
        for attempt in range(self.max_retries + 1):
            try:
                return self.parser.parse_raw_response(current, expected_sample_id)
            except Exception as exc:  # parse or schema validation failed
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt >= self.max_retries:
                    break
                LOGGER.warning(
                    "parse failed for %s (attempt %d/%d); requesting repair",
                    expected_sample_id,
                    attempt + 1,
                    self.max_retries,
                )
                repair_messages = self.prompt_builder.build_json_repair_messages(
                    raw_response=_as_text(current),
                    error_message=last_error,
                    expected_sample_id=expected_sample_id,
                )
                current = client_call(repair_messages)

        LOGGER.warning(
            "giving up on %s after repairs; returning uncertain verdict",
            expected_sample_id,
        )
        return conservative_uncertain_verdict(expected_sample_id, last_error)


def _as_text(raw: str | dict) -> str:
    """Render a raw response as text for embedding in a repair prompt."""
    if isinstance(raw, str):
        return raw
    import json

    return json.dumps(raw, ensure_ascii=False)


__all__ = ["RetryPolicy", "conservative_uncertain_verdict"]
