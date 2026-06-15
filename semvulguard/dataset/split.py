"""Train/valid/test split assignment.

Both strategies return new :class:`SampleRecord` objects (via ``model_copy``)
with the ``split`` field set; the inputs are left untouched. Ratios are applied
by stable index boundaries so a fixed seed yields a reproducible partition.
"""

from __future__ import annotations

import random

from semvulguard.schemas.records import SampleRecord


def _split_labels_for(n: int, train_ratio: float, valid_ratio: float) -> list[str]:
    """Return a list of ``n`` split labels by position boundaries."""
    n_train = int(n * train_ratio)
    n_valid = int(n * valid_ratio)
    labels = ["train"] * n_train + ["valid"] * n_valid
    labels += ["test"] * (n - len(labels))
    return labels


def assign_random_split(
    samples: list[SampleRecord],
    train_ratio: float = 0.7,
    valid_ratio: float = 0.1,
    test_ratio: float = 0.2,
    seed: int = 42,
) -> list[SampleRecord]:
    """Shuffle deterministically by ``seed`` and assign splits.

    The returned list preserves the original sample order; only each sample's
    ``split`` field is updated.
    """
    del test_ratio  # implied by the remainder; kept for an explicit API
    order = list(range(len(samples)))
    # Shuffle on a stable key first so input ordering never leaks into results.
    order.sort(key=lambda i: samples[i].sample_id)
    rng = random.Random(seed)
    rng.shuffle(order)

    split_for_index: dict[int, str] = {}
    labels = _split_labels_for(len(samples), train_ratio, valid_ratio)
    for label, idx in zip(labels, order, strict=True):
        split_for_index[idx] = label

    return [
        sample.model_copy(update={"split": split_for_index[i]})
        for i, sample in enumerate(samples)
    ]


def assign_time_split(
    samples: list[SampleRecord],
    time_lookup: dict[str, float] | None = None,
    train_ratio: float = 0.7,
    valid_ratio: float = 0.1,
    test_ratio: float = 0.2,
) -> list[SampleRecord]:
    """Assign splits in chronological order.

    When ``time_lookup`` (``sample_id`` -> timestamp) is missing entries, those
    samples fall back to a stable ordering by ``sample_id`` after the timed
    ones. The earliest samples become ``train`` and the latest ``test``.
    """
    del test_ratio  # implied by the remainder; kept for an explicit API
    time_lookup = time_lookup or {}

    def sort_key(sample: SampleRecord) -> tuple[int, float | str, str]:
        # Timed samples (group 0) sort before untimed ones (group 1); ties and
        # untimed samples fall back to a stable sample_id ordering.
        if sample.sample_id in time_lookup:
            return (0, time_lookup[sample.sample_id], sample.sample_id)
        return (1, sample.sample_id, sample.sample_id)

    ordered = sorted(samples, key=sort_key)
    labels = _split_labels_for(len(ordered), train_ratio, valid_ratio)
    split_for_id = {
        sample.sample_id: label
        for sample, label in zip(ordered, labels, strict=True)
    }
    return [
        sample.model_copy(update={"split": split_for_id[sample.sample_id]})
        for sample in samples
    ]


__all__ = ["assign_random_split", "assign_time_split"]
