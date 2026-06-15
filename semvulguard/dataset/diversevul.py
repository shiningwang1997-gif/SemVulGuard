"""DiverseVul dataset loader.

DiverseVul ships as JSONL with one row per function and a binary ``target``
label, covering many projects and CWEs.
"""

from __future__ import annotations

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
from semvulguard.utils.jsonl import read_jsonl


class DiverseVulLoader(DatasetLoader):
    """Loader for DiverseVul-style JSONL function records."""

    dataset_name = "diversevul"

    def load(self, input_path: Path) -> list[SampleRecord]:
        input_path = Path(input_path)
        samples: list[SampleRecord] = []
        for row in read_jsonl(input_path):
            samples.append(self._normalize(row))
        return samples

    def _normalize(self, row: dict) -> SampleRecord:
        code = first_present(row, "func", "function", "function_code")
        code = str(code) if code is not None else None
        file = first_present(row, "file", "file_name")
        file = str(file) if file is not None else "unknown"
        function = first_present(row, "function_name", "func_name")

        row_id = first_present(row, "id", "idx")
        if row_id is not None:
            sample_id = f"{self.dataset_name}_{row_id}"
        else:
            sample_id = f"{self.dataset_name}_{deterministic_hash(file, code or '')}"

        repo = first_present(row, "project", "repo")
        commit_before = first_present(row, "commit_id", "commit_before")
        label = coerce_label(first_present(row, "target", "label", "vulnerable"))

        record = SampleRecord(
            sample_id=sample_id,
            dataset=self.dataset_name,
            language="c",
            repo=str(repo) if repo is not None else None,
            commit_before=str(commit_before) if commit_before is not None else None,
            commit_after=None,
            file=file,
            function=str(function) if function is not None else None,
            span=make_span(file, code),
            label=label,
            cwe=coerce_cwe(row.get("cwe")),
            split=normalize_split(row.get("split")),
        )
        self._register_code(sample_id, code)
        return record


__all__ = ["DiverseVulLoader"]
