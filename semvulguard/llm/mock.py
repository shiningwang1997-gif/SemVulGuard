"""Deterministic mock LLM client for tests and offline development.

Mirrors :meth:`DeepSeekClient.complete_json` but never touches the network.
Four modes are supported: fixed ``vulnerable`` / ``benign`` / ``uncertain``
verdicts, and a ``rule`` heuristic that inspects the prompt for risky sink
calls without an obvious guarding check.

Responses are returned as plain dicts shaped like an :class:`LLMVerdict`; the
``sample_id`` is recovered from the rendered prompt when present so the mock
echoes it back the way a real model would.
"""

from __future__ import annotations

import json
import re

from semvulguard.llm.client import LLMResponse

# Risky sink calls that, absent an obvious guard, suggest a real flaw.
RISKY_SINKS = ("memcpy", "strcpy", "strcat", "sprintf", "system", "free", "gets")

# Cheap signals that the code already guards the operation. Used only to make
# the rule-mode heuristic a little less trigger-happy.
CHECK_TOKENS = ("if (", "if(", "sizeof", "strncpy", "snprintf", "bounds", "assert")

_SAMPLE_ID_RE = re.compile(r"^sample_id:\s*(\S+)", re.MULTILINE)


def _user_content(messages: list[dict]) -> str:
    """Concatenate the user-role message contents from a chat request."""
    return "\n".join(
        str(m.get("content", "")) for m in messages if m.get("role") == "user"
    )


def _extract_sample_id(messages: list[dict]) -> str:
    """Recover the sample_id embedded in the rendered prompt, if any."""
    match = _SAMPLE_ID_RE.search(_user_content(messages))
    return match.group(1) if match else ""


def _vulnerable(sample_id: str, cwe: str = "CWE-119") -> dict:
    return {
        "sample_id": sample_id,
        "verdict": "vulnerable",
        "confidence": 0.9,
        "predicted_cwe": cwe,
        "vulnerable_lines": [1],
        "evidence": [{"kind": "mock", "reason": "risky sink without guard"}],
        "need_more_context": False,
        "missing_context": [],
        "patch_hint": "Validate sizes/lifetimes before the flagged operation.",
    }


def _benign(sample_id: str) -> dict:
    return {
        "sample_id": sample_id,
        "verdict": "benign",
        "confidence": 0.8,
        "predicted_cwe": "",
        "vulnerable_lines": [],
        "evidence": [],
        "need_more_context": False,
        "missing_context": [],
        "patch_hint": "",
    }


def _uncertain(sample_id: str) -> dict:
    return {
        "sample_id": sample_id,
        "verdict": "uncertain",
        "confidence": 0.5,
        "predicted_cwe": "",
        "vulnerable_lines": [],
        "evidence": [],
        "need_more_context": True,
        "missing_context": ["caller context", "buffer size definitions"],
        "patch_hint": "",
    }


class MockLLMClient:
    """Drop-in replacement for :class:`DeepSeekClient` that fabricates verdicts.

    ``mode`` selects the behavior: ``vulnerable`` / ``benign`` / ``uncertain``
    always return that verdict, while ``rule`` derives one from the prompt.
    """

    MODES = ("vulnerable", "benign", "uncertain", "rule")

    def __init__(self, mode: str = "rule") -> None:
        if mode not in self.MODES:
            raise ValueError(
                f"mode must be one of {self.MODES}, got {mode!r}"
            )
        self.mode = mode

    def complete_json(self, messages: list[dict]) -> dict:
        """Return a verdict dict without any network access."""
        sample_id = _extract_sample_id(messages)
        if self.mode == "vulnerable":
            return _vulnerable(sample_id)
        if self.mode == "benign":
            return _benign(sample_id)
        if self.mode == "uncertain":
            return _uncertain(sample_id)
        return self._rule_verdict(sample_id, messages)

    def complete(self, messages: list[dict]) -> LLMResponse:
        """Mirror :meth:`DeepSeekClient.complete`, returning serialized JSON.

        Token usage is fabricated deterministically from message length so cost
        logging has something non-trivial to record in tests.
        """
        verdict = self.complete_json(messages)
        content = json.dumps(verdict, ensure_ascii=False)
        prompt_tokens = sum(len(str(m.get("content", ""))) for m in messages) // 4
        completion_tokens = len(content) // 4
        return LLMResponse(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model=f"mock-{self.mode}",
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        )

    def _rule_verdict(self, sample_id: str, messages: list[dict]) -> dict:
        """Heuristic verdict: risky sink + no obvious check => vulnerable."""
        content = _user_content(messages)
        has_sink = any(sink in content for sink in RISKY_SINKS)
        has_check = any(token in content for token in CHECK_TOKENS)
        if has_sink and not has_check:
            return _vulnerable(sample_id)
        if has_sink and has_check:
            return _uncertain(sample_id)
        return _benign(sample_id)


__all__ = ["MockLLMClient", "RISKY_SINKS"]
