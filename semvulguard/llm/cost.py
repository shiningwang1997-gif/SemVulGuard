"""Per-call cost / latency logging for the verifier.

:class:`CostLogger` appends one JSONL record per verification so a later run of
the evaluation harness (``semvulguard.eval.cost``) can aggregate token usage,
latency, and dollar cost. By design it records only metadata -- never prompt
content and never the API key.
"""

from __future__ import annotations

import json
from pathlib import Path

from semvulguard.llm.client import LLMResponse

# Rough per-1K-token prices (USD) used only when a caller does not supply an
# explicit cost. Kept conservative and easy to override.
DEFAULT_PRICE_PER_1K = 0.0


class CostLogger:
    """Append cost/latency records to a JSONL file.

    A ``None`` path disables logging entirely (every method becomes a no-op),
    which is the common case for tests and dry runs.
    """

    def __init__(self, path: Path | None) -> None:
        self.path = Path(path) if path is not None else None
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Truncate so a run starts with a fresh log.
            self.path.write_text("", encoding="utf-8")

    @property
    def enabled(self) -> bool:
        return self.path is not None

    def log(
        self,
        sample_id: str,
        model: str,
        response: LLMResponse | None,
        latency_seconds: float,
        success: bool,
        error_type: str | None = None,
        api_cost_usd: float | None = None,
    ) -> dict | None:
        """Write one record; return it (or ``None`` when logging is disabled).

        Token fields are pulled from ``response`` when present. Prompt content is
        never included.
        """
        if not self.enabled:
            return None

        record: dict = {
            "sample_id": sample_id,
            "model": model,
            "prompt_tokens": response.prompt_tokens if response else None,
            "completion_tokens": response.completion_tokens if response else None,
            "total_tokens": response.total_tokens if response else None,
            "latency_seconds": round(latency_seconds, 6),
            "success": success,
        }
        if api_cost_usd is not None:
            record["api_cost_usd"] = api_cost_usd
        if error_type is not None:
            record["error_type"] = error_type

        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record


__all__ = ["CostLogger"]
