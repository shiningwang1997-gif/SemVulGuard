"""Tests for the dependency-light tokenizer helpers."""

from __future__ import annotations

from semvulguard.features.tokenizer import (
    basic_code_tokenize,
    truncate_code_by_lines,
)


def test_tokenize_identifiers_and_numbers():
    tokens = basic_code_tokenize("int x = 42;")
    assert tokens == ["int", "x", "=", "42", ";"]


def test_tokenize_punctuation_split():
    tokens = basic_code_tokenize("a->b")
    assert tokens == ["a", "-", ">", "b"]


def test_tokenize_call():
    tokens = basic_code_tokenize("memcpy(dst, src, n)")
    assert tokens == ["memcpy", "(", "dst", ",", "src", ",", "n", ")"]


def test_tokenize_empty():
    assert basic_code_tokenize("") == []


def test_truncate_by_lines():
    lines = ["a", "b", "c", "d"]
    assert truncate_code_by_lines(lines, max_lines=2) == ["a", "b"]


def test_truncate_by_lines_none_keeps_all():
    lines = ["a", "b", "c"]
    assert truncate_code_by_lines(lines) == ["a", "b", "c"]


def test_truncate_by_chars():
    lines = ["abc", "def", "ghi"]
    # "abc" (3) + "\n" + "def" (3) = 7 <= 7; adding "ghi" would exceed.
    assert truncate_code_by_lines(lines, max_chars=7) == ["abc", "def"]


def test_truncate_by_chars_first_line_only():
    lines = ["abcdef", "g"]
    assert truncate_code_by_lines(lines, max_chars=6) == ["abcdef"]


def test_truncate_lines_then_chars():
    lines = ["abc", "def", "ghi", "jkl"]
    out = truncate_code_by_lines(lines, max_lines=3, max_chars=3)
    assert out == ["abc"]


def test_truncate_does_not_mutate_input():
    lines = ["a", "b", "c"]
    truncate_code_by_lines(lines, max_lines=1)
    assert lines == ["a", "b", "c"]
