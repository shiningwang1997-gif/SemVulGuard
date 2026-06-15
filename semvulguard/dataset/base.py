"""Base dataset loader interface and shared normalization helpers.

Concrete loaders (Devign, BigVul, DiverseVul) subclass :class:`DatasetLoader`
and turn heterogeneous raw rows into the canonical :class:`SampleRecord`
contract. Loaders also expose a ``code_lookup`` mapping (``sample_id`` ->
function source) populated during :meth:`DatasetLoader.load`, so downstream
deduplication can hash the underlying code without re-parsing the raw input.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path

from semvulguard.schemas.records import CodeSpan, SampleRecord

ALLOWED_SPLITS = {"train", "valid", "test", "unknown"}


def deterministic_hash(*parts: str) -> str:
    """Return a short, stable hex digest for the given string parts.

    Used to mint reproducible ``sample_id`` values when a dataset row carries
    no native identifier.
    """
    joined = "\x00".join(parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]


def coerce_label(value: object) -> int:
    """Coerce a raw target/vulnerable flag into a 0/1 integer label."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return 1 if int(value) != 0 else 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "vulnerable", "vul", "yes", "bad"}:
            return 1
        if text in {"0", "false", "benign", "safe", "no", "good", ""}:
            return 0
        # Fall back to numeric parsing; anything non-zero is vulnerable.
        try:
            return 1 if int(float(text)) != 0 else 0
        except ValueError:
            return 0
    return 0


def coerce_cwe(value: object) -> list[str]:
    """Normalize a CWE field (None / str / list) into a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        # Allow comma/semicolon separated strings.
        if "," in text or ";" in text:
            parts = [p.strip() for p in text.replace(";", ",").split(",")]
            return [p for p in parts if p]
        return [text]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value)]


def normalize_split(value: object) -> str:
    """Return a valid split label, defaulting unknown/missing values."""
    if value is None:
        return "unknown"
    text = str(value).strip().lower()
    aliases = {
        "training": "train",
        "validation": "valid",
        "val": "valid",
        "dev": "valid",
        "testing": "test",
        "eval": "test",
    }
    text = aliases.get(text, text)
    return text if text in ALLOWED_SPLITS else "unknown"


def count_lines(code: str | None) -> int:
    """Return the line count of a function body, at least 1."""
    if not code:
        return 1
    return max(1, code.count("\n") + 1)


def make_span(file: str, code: str | None) -> CodeSpan:
    """Build a default span covering the whole function body."""
    return CodeSpan(file=file, start_line=1, end_line=count_lines(code))


def first_present(row: dict, *keys: str) -> object | None:
    """Return the first non-empty value among ``keys`` in ``row``."""
    for key in keys:
        if key in row:
            value = row[key]
            if value is not None and value != "":
                return value
    return None


class DatasetLoader(ABC):
    """Abstract base for raw-dataset loaders.

    Subclasses implement :meth:`load` to produce normalized
    :class:`SampleRecord` objects. During loading they should register each
    sample's function source via :meth:`_register_code` so that downstream
    deduplication can access it through :attr:`code_lookup`.
    """

    #: Canonical dataset name written into every emitted ``SampleRecord``.
    dataset_name: str = "unknown"

    def __init__(self) -> None:
        self.code_lookup: dict[str, str] = {}

    @abstractmethod
    def load(self, input_path: Path) -> list[SampleRecord]:
        """Load and normalize samples from ``input_path``."""
        raise NotImplementedError

    def _register_code(self, sample_id: str, code: str | None) -> None:
        """Record the raw function source for a sample."""
        self.code_lookup[sample_id] = code or ""


__all__ = [
    "ALLOWED_SPLITS",
    "DatasetLoader",
    "deterministic_hash",
    "coerce_label",
    "coerce_cwe",
    "normalize_split",
    "count_lines",
    "make_span",
    "first_present",
]
