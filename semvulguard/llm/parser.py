"""Parse and validate raw model output into an :class:`LLMVerdict`.

:class:`LLMResponseParser` is tolerant of the formatting noise real models emit
-- JSON wrapped in ``string`` payloads, ```json fenced blocks, a missing or
empty ``sample_id``, a confidence a hair outside ``[0, 1]`` -- but strict about
anything semantically wrong: a bad verdict label, non-positive line numbers, or
a wildly out-of-range confidence all raise.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from semvulguard.schemas.records import LLMVerdict

# A confidence within this slack of [0, 1] is clamped; further out is an error.
CONFIDENCE_SLACK = 0.05

# Matches a leading ```json / ``` fence and the closing fence.
_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*\n?(?P<body>.*?)\n?\s*```\s*$",
    re.DOTALL | re.IGNORECASE,
)


class LLMResponseParser:
    """Turn a raw model response into a validated :class:`LLMVerdict`."""

    def parse_raw_response(
        self, raw: str | dict, expected_sample_id: str
    ) -> LLMVerdict:
        """Parse, normalize, and validate ``raw`` into an ``LLMVerdict``.

        ``raw`` may be a dict (already-parsed JSON mode) or a string (possibly
        markdown-fenced). Raises ``json.JSONDecodeError`` for unparseable text
        and ``ValidationError``/``ValueError`` for schema violations.
        """
        if isinstance(raw, str):
            text = self.strip_markdown_code_fence(raw)
            data = json.loads(text)
        else:
            data = dict(raw)

        if not isinstance(data, dict):
            raise ValueError(
                f"verdict must be a JSON object, got {type(data).__name__}"
            )

        normalized = self.normalize_response_dict(data, expected_sample_id)
        return LLMVerdict.model_validate(normalized)

    @staticmethod
    def strip_markdown_code_fence(text: str) -> str:
        """Strip a surrounding ```json ... ``` (or bare ```) fence if present."""
        match = _FENCE_RE.match(text)
        if match:
            return match.group("body").strip()
        return text.strip()

    def normalize_response_dict(
        self, data: dict, expected_sample_id: str
    ) -> dict:
        """Repair formatting noise without masking semantic errors.

        Fills a missing/empty ``sample_id`` from ``expected_sample_id`` and
        clamps a marginally out-of-range confidence; everything else is left for
        schema validation to judge.
        """
        result = dict(data)
        if not result.get("sample_id"):
            result["sample_id"] = expected_sample_id
        if "confidence" in result:
            result["confidence"] = self._repair_confidence(result["confidence"])
        return result

    @staticmethod
    def _repair_confidence(value: object) -> float:
        """Clamp a confidence only when marginally outside [0, 1]."""
        conf = float(value)  # raises TypeError/ValueError for non-numerics
        if conf < 0.0:
            if conf < -CONFIDENCE_SLACK:
                raise ValueError(f"confidence {conf} is out of range")
            return 0.0
        if conf > 1.0:
            if conf > 1.0 + CONFIDENCE_SLACK:
                raise ValueError(f"confidence {conf} is out of range")
            return 1.0
        return conf


# Backward-compatible functional API. Older callers import this name directly.
def parse_llm_verdict(raw: dict | str, sample_id: str) -> LLMVerdict:
    """Parse a raw response into an ``LLMVerdict`` (functional wrapper)."""
    return LLMResponseParser().parse_raw_response(raw, expected_sample_id=sample_id)


__all__ = ["LLMResponseParser", "parse_llm_verdict", "ValidationError"]
