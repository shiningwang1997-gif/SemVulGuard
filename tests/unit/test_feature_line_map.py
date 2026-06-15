"""Tests for line mapping helpers."""

from __future__ import annotations

from semvulguard.features.line_map import (
    absolute_to_relative_line,
    build_line_mask,
    relative_to_absolute_line,
    split_code_lines,
)
from semvulguard.schemas.records import CodeSpan


def _span(start: int = 100, end: int = 120) -> CodeSpan:
    return CodeSpan(file="a.c", start_line=start, end_line=end)


def test_split_code_lines_basic():
    assert split_code_lines("a\nb\nc") == ["a", "b", "c"]


def test_split_code_lines_trailing_newline():
    assert split_code_lines("a\nb\n") == ["a", "b"]


def test_split_code_lines_empty():
    assert split_code_lines("") == []


def test_absolute_to_relative_first_line():
    span = _span()
    assert absolute_to_relative_line(100, span) == 1


def test_absolute_to_relative_interior():
    span = _span()
    assert absolute_to_relative_line(105, span) == 6


def test_absolute_to_relative_last_line():
    span = _span()
    assert absolute_to_relative_line(120, span) == 21


def test_absolute_to_relative_outside_returns_none():
    span = _span()
    assert absolute_to_relative_line(99, span) is None
    assert absolute_to_relative_line(121, span) is None


def test_relative_to_absolute_round_trip():
    span = _span()
    for abs_line in (100, 110, 120):
        rel = absolute_to_relative_line(abs_line, span)
        assert rel is not None
        assert relative_to_absolute_line(rel, span) == abs_line


def test_build_line_mask_length_and_positions():
    span = _span(100, 104)  # 5 lines
    mask = build_line_mask([100, 102, 104], span)
    assert mask == [1, 0, 1, 0, 1]


def test_build_line_mask_ignores_out_of_span():
    span = _span(100, 102)
    mask = build_line_mask([99, 101, 500], span)
    assert mask == [0, 1, 0]


def test_build_line_mask_empty_lines():
    span = _span(1, 3)
    assert build_line_mask([], span) == [0, 0, 0]
