"""Dependency-light code tokenization and truncation helpers.

This phase deliberately avoids HuggingFace tokenizers. ``basic_code_tokenize``
provides a simple, deterministic split into identifier/number tokens and
single-character punctuation, adequate for sanity checks and lightweight
features until a real subword tokenizer is wired in.
"""

from __future__ import annotations

import re

# Identifiers/numbers as whole tokens; every other non-space char is its own
# punctuation token (covers operators and separators in C-family code).
_TOKEN = re.compile(r"[A-Za-z_]\w*|\d+|[^\s\w]")


def basic_code_tokenize(code: str) -> list[str]:
    """Tokenize source into identifiers, numbers, and punctuation tokens."""
    if not code:
        return []
    return _TOKEN.findall(code)


def truncate_code_by_lines(
    code_lines: list[str],
    max_lines: int | None = None,
    max_chars: int | None = None,
) -> list[str]:
    """Truncate a list of code lines by line count and/or cumulative chars.

    Limits are applied in order: first ``max_lines`` (keep the leading lines),
    then ``max_chars`` (stop once including the next line would exceed the
    character budget, counting a newline between kept lines). ``None`` disables
    the corresponding limit.
    """
    lines = code_lines
    if max_lines is not None:
        lines = lines[:max_lines]

    if max_chars is None:
        return list(lines)

    kept: list[str] = []
    used = 0
    for line in lines:
        # Account for the newline joining this line to the previous one.
        extra = len(line) + (1 if kept else 0)
        if used + extra > max_chars:
            break
        kept.append(line)
        used += extra
    return kept


__all__ = ["basic_code_tokenize", "truncate_code_by_lines"]
