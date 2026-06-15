"""Logging helper.

Provides a single ``get_logger`` factory so every module logs with a consistent
format. Idempotent: repeated calls for the same name reuse one handler.
"""

from __future__ import annotations

import logging

_DEFAULT_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def get_logger(name: str = "semvulguard", level: int = logging.INFO) -> logging.Logger:
    """Return a configured logger that writes to stderr."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


__all__ = ["get_logger"]
