"""Line mapping between absolute source lines and function-relative lines.

A :class:`CodeSpan` is 1-indexed and inclusive. "Relative" lines are 1-indexed
positions inside the function body, so absolute ``span.start_line`` maps to
relative line ``1``. Lines outside the span have no relative position.
"""

from __future__ import annotations

from semvulguard.schemas.records import CodeSpan


def split_code_lines(function_code: str) -> list[str]:
    """Split a function body into lines, dropping a single trailing newline.

    An empty string yields an empty list. ``splitlines`` is used so ``\\r\\n``
    and ``\\n`` are both handled and no spurious trailing empty line appears.
    """
    if not function_code:
        return []
    return function_code.splitlines()


def absolute_to_relative_line(abs_line: int, span: CodeSpan) -> int | None:
    """Map an absolute source line to a 1-indexed function-relative line.

    Returns ``None`` when ``abs_line`` falls outside ``[start_line, end_line]``.
    """
    if abs_line < span.start_line or abs_line > span.end_line:
        return None
    return abs_line - span.start_line + 1


def relative_to_absolute_line(rel_line: int, span: CodeSpan) -> int:
    """Map a 1-indexed function-relative line back to an absolute source line."""
    return span.start_line + rel_line - 1


def build_line_mask(lines: list[int], span: CodeSpan) -> list[int]:
    """Build a per-line 0/1 mask over the span for the given absolute lines.

    The mask has one entry per line in ``[start_line, end_line]`` (so its length
    is ``end_line - start_line + 1``); entry ``i`` is ``1`` when absolute line
    ``start_line + i`` appears in ``lines``. Lines outside the span are ignored.
    """
    length = span.end_line - span.start_line + 1
    mask = [0] * length
    for line in lines:
        rel = absolute_to_relative_line(line, span)
        if rel is not None:
            mask[rel - 1] = 1
    return mask


__all__ = [
    "split_code_lines",
    "absolute_to_relative_line",
    "relative_to_absolute_line",
    "build_line_mask",
]
