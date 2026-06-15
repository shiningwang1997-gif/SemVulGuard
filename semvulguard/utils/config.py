"""YAML configuration loader.

Configs live as plain YAML files under ``configs/``. ``load_config`` returns a
dict; ``load_configs`` merges several files (later files win) so a base config
can be layered with experiment overrides.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a single YAML config file into a dict.

    An empty file yields an empty dict. A non-mapping top-level document is a
    configuration error.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"config file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"config root must be a mapping, got {type(data).__name__}")
    return data


def load_configs(*paths: str | Path) -> dict[str, Any]:
    """Load and shallow-merge several config files; later paths override."""
    merged: dict[str, Any] = {}
    for path in paths:
        merged.update(load_config(path))
    return merged


__all__ = ["load_config", "load_configs"]
