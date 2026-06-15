"""Configuration for the LLM semantic-verification subsystem.

:class:`LLMConfig` is the single place that holds the knobs shared across the
client, verifier, retry policy, and cost logger. It is a plain dataclass so it
is trivial to construct in tests and from CLI flags without pulling in pydantic
validation machinery.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class LLMConfig:
    """Runtime configuration for the semantic verifier.

    ``top_k`` accepts an int or the string ``"all"`` so callers can request the
    whole candidate set. ``cost_log_path`` and ``cache_dir`` are optional and
    default to disabled.
    """

    provider: str = "deepseek"
    model: str = "deepseek-chat"
    temperature: float = 0.0
    timeout: int = 60
    max_retries: int = 3
    top_k: int | str = 50
    json_mode: bool = True
    cost_log_path: Path | None = None
    cache_dir: Path | None = None


__all__ = ["LLMConfig"]
