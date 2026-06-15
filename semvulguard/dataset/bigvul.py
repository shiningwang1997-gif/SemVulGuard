"""BigVul dataset loader.

BigVul is distributed as CSV with one row per function change. We read it with
the stdlib ``csv`` module (no pandas dependency) and use the pre-patch function
body (``func_before`` / ``before``) as the candidate code.
"""

from __future__ import annotations

import csv
from pathlib import Path

from semvulguard.dataset.base import (
    DatasetLoader,
    coerce_cwe,
    coerce_label,
    deterministic_hash,
    first_present,
    make_span,
    normalize_split,
)
from semvulguard.schemas.records import SampleRecord


class BigVulLoader(DatasetLoader):
    """Loader for BigVul-style CSV function-change records."""

    dataset_name = "bigvul"

    def load(self, input_path: Path) -> list[SampleRecord]:
        input_path = Path(input_path)
        samples: list[SampleRecord] = []
        with input_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                samples.append(self._normalize(row))
        return samples

    def _normalize(self, row: dict) -> SampleRecord:
        code = first_present(row, "func_before", "before", "func", "function")
        code = str(code) if code is not None else None
        file = first_present(row, "file", "file_name")
        file = str(file) if file is not None else "unknown"
        function = first_present(row, "function_name", "func_name")

        row_id = first_present(row, "id")
        if row_id is not None:
            sample_id = f"{self.dataset_name}_{row_id}"
        else:
            sample_id = f"{self.dataset_name}_{deterministic_hash(file, code or '')}"

        repo = first_present(row, "project", "repo")
        commit_before = first_present(row, "commit_id", "commit_before")
        commit_after = first_present(row, "after_commit", "commit_after")
        label = coerce_label(first_present(row, "vulnerable", "target", "label"))

        record = SampleRecord(
            sample_id=sample_id,
            dataset=self.dataset_name,
            language="c",
            repo=str(repo) if repo is not None else None,
            commit_before=str(commit_before) if commit_before is not None else None,
            commit_after=str(commit_after) if commit_after is not None else None,
            file=file,
            function=str(function) if function is not None else None,
            span=make_span(file, code),
            label=label,
            cwe=coerce_cwe(row.get("cwe")),
            split=normalize_split(row.get("split")),
        )
        self._register_code(sample_id, code)
        return record


__all__ = ["BigVulLoader"]
