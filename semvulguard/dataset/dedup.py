"""Deduplication helpers for the dataset manifest.

Two hashing strategies are provided:

* ``exact_hash`` — digest of the raw code string.
* ``normalized_code_hash`` — digest after a conservative normalization that
  strips comments and collapses whitespace, so cosmetically different copies of
  the same function collapse together.

Normalization deliberately does **not** lowercase code: C/C++ identifiers are
case-sensitive, so lowercasing would conflate distinct symbols.
"""

from __future__ import annotations

import hashlib
import re
from typing import Literal

from semvulguard.schemas.records import SampleRecord

# Conservative comment stripping for C-family code.
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"//[^\n]*")
_WHITESPACE = re.compile(r"\s+")


def exact_hash(text: str) -> str:
    """Return a SHA-256 digest of the raw text."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _normalize_code(text: str) -> str:
    """Strip comments and collapse whitespace, preserving identifier case."""
    if not text:
        return ""
    without_block = _BLOCK_COMMENT.sub(" ", text)
    without_comments = _LINE_COMMENT.sub(" ", without_block)
    collapsed = _WHITESPACE.sub(" ", without_comments)
    return collapsed.strip()


def normalized_code_hash(text: str) -> str:
    """Return a SHA-256 digest of the normalized code."""
    return hashlib.sha256(_normalize_code(text).encode("utf-8")).hexdigest()


def deduplicate_samples(
    samples: list[SampleRecord],
    code_lookup: dict[str, str],
    mode: Literal["exact", "normalized"] = "normalized",
) -> list[SampleRecord]:
    """Drop duplicate samples based on their function code.

    The first occurrence wins; input order is otherwise preserved. Samples whose
    code is absent from ``code_lookup`` are hashed on the empty string, so they
    collapse to a single representative.
    """
    hasher = exact_hash if mode == "exact" else normalized_code_hash
    seen: set[str] = set()
    unique: list[SampleRecord] = []
    for sample in samples:
        code = code_lookup.get(sample.sample_id, "")
        digest = hasher(code)
        if digest in seen:
            continue
        seen.add(digest)
        unique.append(sample)
    return unique


__all__ = [
    "exact_hash",
    "normalized_code_hash",
    "deduplicate_samples",
]
