"""Tests for the sequence encoder (fallback mode; no downloads)."""

from __future__ import annotations

import torch

from semvulguard.models.encoder.sequence import SequenceEncoder, stable_hash


def test_fallback_output_shape():
    enc = SequenceEncoder(hidden_size=32, fallback=True)
    out = enc(["int main() { return 0; }", "void f() {}"])
    assert out.shape == (2, 32)
    assert out.dtype == torch.float32


def test_fallback_is_default_without_model_name():
    enc = SequenceEncoder(hidden_size=16)
    assert enc.uses_huggingface is False


def test_empty_batch_returns_zero_rows():
    enc = SequenceEncoder(hidden_size=8)
    out = enc([])
    assert out.shape == (0, 8)


def test_empty_string_is_handled():
    enc = SequenceEncoder(hidden_size=8)
    out = enc(["", "x"])
    assert out.shape == (2, 8)
    assert torch.isfinite(out).all()


def test_stable_hash_is_deterministic():
    assert stable_hash("memcpy") == stable_hash("memcpy")
    assert stable_hash("a") != stable_hash("b")


def test_forward_is_deterministic_for_same_weights():
    torch.manual_seed(0)
    enc = SequenceEncoder(hidden_size=16)
    a = enc(["free(p); use(p);"])
    b = enc(["free(p); use(p);"])
    assert torch.allclose(a, b)


def test_missing_local_model_falls_back(tmp_path):
    # A model_name that is not cached locally must not error or download.
    enc = SequenceEncoder(
        model_name="definitely/not-a-real-local-model",
        hidden_size=16,
        fallback=False,
    )
    assert enc.uses_huggingface is False
    out = enc(["int x;"])
    assert out.shape == (1, 16)
