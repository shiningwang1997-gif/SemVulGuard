"""Sequence (token) encoder for function source.

The encoder has two modes:

* **HuggingFace mode** — when ``model_name`` is given, ``transformers`` is
  installed, and the model is available locally, it wraps ``AutoTokenizer`` /
  ``AutoModel`` (e.g. GraphCodeBERT) and projects the pooled hidden state.
* **Fallback mode** — a dependency-light hashing embedding with mean pooling.
  This is the default for tests so nothing is ever downloaded.

Both modes return a ``[batch_size, hidden_size]`` tensor. The fallback never
touches the network and is fully deterministic given its initialized weights.
"""

from __future__ import annotations

import re
import zlib

import torch
from torch import nn

# Whole-token split mirroring features.tokenizer; kept local to avoid coupling.
_TOKEN = re.compile(r"[A-Za-z_]\w*|\d+|[^\s\w]")


def stable_hash(text: str) -> int:
    """Process-independent non-negative hash (unlike the randomized ``hash``)."""
    return zlib.crc32(text.encode("utf-8"))


def _try_import_transformers():
    """Return the transformers module, or None if it is not installed."""
    try:
        import transformers  # noqa: PLC0415

        return transformers
    except Exception:  # pragma: no cover - environment dependent
        return None


class SequenceEncoder(nn.Module):
    """Encode a batch of code strings into fixed-size vectors."""

    def __init__(
        self,
        model_name: str | None = None,
        hidden_size: int = 256,
        fallback: bool = True,
        vocab_size: int = 4096,
        max_tokens: int = 256,
    ) -> None:
        super().__init__()
        self.hidden_size = hidden_size
        self.vocab_size = vocab_size
        self.max_tokens = max_tokens
        self.model_name = model_name
        self._hf = None
        self._tokenizer = None

        if model_name is not None and not fallback:
            self._init_huggingface(model_name, hidden_size)

        if self._hf is None:
            # Fallback hashing-embedding path (also the test default).
            self.embedding = nn.Embedding(vocab_size, hidden_size)
            self.proj = nn.Linear(hidden_size, hidden_size)

    def _init_huggingface(self, model_name: str, hidden_size: int) -> None:
        """Best-effort load of a local HF model; silently fall back on failure."""
        transformers = _try_import_transformers()
        if transformers is None:
            return
        try:
            # local_files_only avoids any network access during load.
            self._tokenizer = transformers.AutoTokenizer.from_pretrained(
                model_name, local_files_only=True
            )
            self._hf = transformers.AutoModel.from_pretrained(
                model_name, local_files_only=True
            )
            hf_hidden = self._hf.config.hidden_size
            self.proj = nn.Linear(hf_hidden, hidden_size)
        except Exception:  # pragma: no cover - environment dependent
            # Model not cached locally / load failed -> use fallback.
            self._hf = None
            self._tokenizer = None

    @property
    def uses_huggingface(self) -> bool:
        return self._hf is not None

    # -- fallback encoding --------------------------------------------------

    def _hash_token_ids(self, text: str) -> list[int]:
        tokens = _TOKEN.findall(text)[: self.max_tokens]
        return [stable_hash(tok) % self.vocab_size for tok in tokens]

    def _forward_fallback(self, input_texts: list[str]) -> torch.Tensor:
        device = self.embedding.weight.device
        pooled = torch.zeros(
            len(input_texts), self.hidden_size, device=device
        )
        for i, text in enumerate(input_texts):
            ids = self._hash_token_ids(text)
            if not ids:
                continue
            idx = torch.tensor(ids, dtype=torch.long, device=device)
            pooled[i] = self.embedding(idx).mean(dim=0)
        return self.proj(pooled)

    # -- huggingface encoding ----------------------------------------------

    def _forward_huggingface(self, input_texts: list[str]) -> torch.Tensor:
        device = self.proj.weight.device
        encoded = self._tokenizer(
            input_texts,
            padding=True,
            truncation=True,
            max_length=self.max_tokens,
            return_tensors="pt",
        ).to(device)
        outputs = self._hf(**encoded)
        # Mean-pool the last hidden state over the attention mask.
        hidden = outputs.last_hidden_state
        mask = encoded["attention_mask"].unsqueeze(-1).to(hidden.dtype)
        summed = (hidden * mask).sum(dim=1)
        counts = mask.sum(dim=1).clamp(min=1.0)
        pooled = summed / counts
        return self.proj(pooled)

    def forward(self, input_texts: list[str]) -> torch.Tensor:
        if not input_texts:
            return torch.zeros(0, self.hidden_size)
        if self.uses_huggingface:
            return self._forward_huggingface(input_texts)
        return self._forward_fallback(input_texts)


__all__ = ["SequenceEncoder", "stable_hash"]
