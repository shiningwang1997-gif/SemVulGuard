"""DeepSeek (OpenAI-compatible) chat client.

Speaks the OpenAI ``/chat/completions`` protocol over a minimal ``requests``
call (imported lazily so the module loads offline and the test suite never needs
the dependency). It is deterministic by default (``temperature=0.0``) and
retries transient transport/HTTP errors with bounded backoff.

Two entry points share one request path:

* :meth:`DeepSeekClient.complete` returns an :class:`LLMResponse` carrying the
  raw content string and token usage (used by the verifier for cost logging);
* :meth:`DeepSeekClient.complete_json` returns just the parsed JSON object and
  is kept for backward compatibility with existing callers.

The API key is read from ``DEEPSEEK_API_KEY``, is never logged, and is scrubbed
from any exception text so it cannot leak through error propagation.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

# parse_llm_verdict is re-exported for backward compatibility: callers
# historically imported the parser from this module.
from semvulguard.llm.parser import parse_llm_verdict  # noqa: F401
from semvulguard.utils.logging import get_logger

LOGGER = get_logger("semvulguard.llm.client")

# HTTP statuses worth retrying: rate limiting and transient server errors.
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class LLMClientError(RuntimeError):
    """Raised for configuration, transport, or response-shape failures."""


@dataclass
class LLMResponse:
    """A model response: the raw content plus best-effort token usage."""

    content: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    model: str | None = None
    usage: dict = field(default_factory=dict)


def _sanitize(text: str, secret: str | None) -> str:
    """Remove a secret from a message so it cannot leak through exceptions."""
    if secret and text:
        return text.replace(secret, "***")
    return text


class DeepSeekClient:
    """Minimal OpenAI-compatible client for DeepSeek.

    A missing API key raises immediately so callers fall back to the mock client
    in offline/test settings rather than hitting the network with no credentials.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        temperature: float = 0.0,
        timeout: int = 60,
        max_retries: int = 3,
        json_mode: bool = True,
    ) -> None:
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise LLMClientError(
                "no DeepSeek API key: pass api_key= or set DEEPSEEK_API_KEY "
                "(use the mock client for offline/test runs)"
            )
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        self.json_mode = json_mode

    @property
    def _endpoint(self) -> str:
        return f"{self.base_url}/chat/completions"

    def complete(self, messages: list[dict]) -> LLMResponse:
        """Send a chat request and return content + token usage.

        Retries transient HTTP/transport errors up to ``max_retries`` times with
        linear backoff. The API key is never written to logs and is scrubbed
        from any raised error.
        """
        import requests  # lazy: keeps the module importable without the dep

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if self.json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(
                    self._endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:  # network/transport error
                last_error = exc
                LOGGER.warning(
                    "request error (attempt %d/%d)", attempt, self.max_retries
                )
                self._backoff(attempt)
                continue

            if resp.status_code in _RETRYABLE_STATUS:
                last_error = LLMClientError(f"transient HTTP {resp.status_code}")
                LOGGER.warning(
                    "transient HTTP %d (attempt %d/%d)",
                    resp.status_code,
                    attempt,
                    self.max_retries,
                )
                self._backoff(attempt)
                continue

            if resp.status_code != 200:
                # Non-retryable status: surface without leaking auth header.
                raise LLMClientError(
                    f"DeepSeek API returned HTTP {resp.status_code}"
                )

            return self._build_response(resp.json())

        message = _sanitize(
            f"DeepSeek request failed after {self.max_retries} attempts: "
            f"{last_error}",
            self.api_key,
        )
        raise LLMClientError(message)

    def complete_json(self, messages: list[dict]) -> dict:
        """Send a chat request and return the parsed JSON object.

        Kept for backward compatibility; prefer :meth:`complete` when token
        usage is needed.
        """
        response = self.complete(messages)
        try:
            return json.loads(response.content)
        except (json.JSONDecodeError, TypeError) as exc:
            raise LLMClientError("response content was not valid JSON") from exc

    @staticmethod
    def _backoff(attempt: int) -> None:
        time.sleep(min(2.0 * attempt, 10.0))

    def _build_response(self, body: dict) -> LLMResponse:
        """Extract content and usage from a chat-completion response body."""
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError("malformed chat-completion response") from exc
        if isinstance(content, dict):
            content = json.dumps(content)
        usage = body.get("usage") or {}
        return LLMResponse(
            content=content,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            model=body.get("model", self.model),
            usage=dict(usage),
        )


__all__ = ["DeepSeekClient", "LLMClientError", "LLMResponse", "parse_llm_verdict"]
