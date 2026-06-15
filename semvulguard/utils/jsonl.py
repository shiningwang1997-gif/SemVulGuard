"""JSONL read/write helpers.

JSONL is the canonical interchange format for the record streams that flow
between modules. These helpers optionally validate each line against a pydantic
model so producers and consumers share one contract.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


def read_jsonl(path: str | Path) -> Iterator[dict]:
    """Yield raw dict records from a JSONL file, skipping blank lines."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def read_models(path: str | Path, model: type[ModelT]) -> list[ModelT]:
    """Read a JSONL file and validate every record against ``model``."""
    return [model.model_validate(record) for record in read_jsonl(path)]


def write_jsonl(path: str | Path, records: Iterable[dict | BaseModel]) -> int:
    """Write records to a JSONL file, creating parent directories.

    Pydantic models are serialized via ``model_dump``. Returns the number of
    records written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            if isinstance(record, BaseModel):
                payload = record.model_dump()
            else:
                payload = record
            fh.write(json.dumps(payload, ensure_ascii=False))
            fh.write("\n")
            count += 1
    return count


__all__ = ["read_jsonl", "read_models", "write_jsonl"]
