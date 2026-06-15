"""Cross-module data contracts for SemVulGuard.

Every module in the pipeline consumes upstream artifacts and emits downstream
artifacts. The records defined here are the strongly-typed JSONL contracts that
flow between modules:

    SampleRecord        -> normalized sample manifest (dataset/labeling)
    StaticAlertRecord   -> static-analysis alerts (CodeQL / Joern / Clang)
    VerificationPacket  -> compressed evidence bundle handed to the LLM
    LLMVerdict          -> structured LLM semantic-verification output
    FinalFinding        -> fused, calibrated, localized finding

These models are validated with pydantic v2 and are the single source of truth
for the on-disk JSONL formats.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CodeSpan(BaseModel):
    """A line span inside a single source file.

    Lines are 1-indexed and inclusive on both ends.
    """

    file: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)

    @model_validator(mode="after")
    def _check_line_order(self) -> CodeSpan:
        if self.end_line < self.start_line:
            raise ValueError(
                f"end_line ({self.end_line}) must be >= start_line ({self.start_line})"
            )
        return self


class SampleRecord(BaseModel):
    """A normalized, function-level sample in the dataset manifest."""

    sample_id: str
    dataset: str
    language: str
    repo: str | None = None
    commit_before: str | None = None
    commit_after: str | None = None
    file: str
    function: str | None = None
    span: CodeSpan
    label: int
    cwe: list[str] = Field(default_factory=list)
    split: str

    @model_validator(mode="after")
    def _validate(self) -> SampleRecord:
        if self.label not in (0, 1):
            raise ValueError(f"label must be 0 or 1, got {self.label}")
        allowed_splits = {"train", "valid", "test", "unknown"}
        if self.split not in allowed_splits:
            raise ValueError(
                f"split must be one of {sorted(allowed_splits)}, got {self.split!r}"
            )
        # Normalize language to lowercase for stable downstream matching.
        self.language = self.language.lower()
        return self


class StaticAlertRecord(BaseModel):
    """A single static-analysis alert produced by a backend tool."""

    sample_id: str
    tool: str
    query_id: str
    message: str
    severity: str | None = None
    file: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    cwe: list[str] = Field(default_factory=list)
    trace_lines: list[int] = Field(default_factory=list)
    raw: dict | None = None

    @model_validator(mode="after")
    def _validate(self) -> StaticAlertRecord:
        if self.end_line < self.start_line:
            raise ValueError(
                f"end_line ({self.end_line}) must be >= start_line ({self.start_line})"
            )
        for line in self.trace_lines:
            if line < 1:
                raise ValueError(
                    f"trace_lines must contain positive integers, got {line}"
                )
        return self


class VerificationPacket(BaseModel):
    """Compressed evidence bundle handed to the LLM semantic verifier.

    The packet bundles the candidate function code, its span, the static alerts
    that fired on it, Joern-derived graph evidence, and any extra context (e.g.
    caller/callee summaries) gathered for the candidate.
    """

    sample_id: str
    language: str
    function_code: str
    span: CodeSpan
    static_alerts: list[StaticAlertRecord] = Field(default_factory=list)
    joern_evidence: dict = Field(default_factory=dict)
    context: dict = Field(default_factory=dict)


class LLMVerdict(BaseModel):
    """Structured output of the DeepSeek-based semantic verifier."""

    sample_id: str
    verdict: Literal["vulnerable", "benign", "uncertain"]
    confidence: float = Field(ge=0.0, le=1.0)
    predicted_cwe: str
    vulnerable_lines: list[int] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)
    need_more_context: bool
    missing_context: list[str] = Field(default_factory=list)
    patch_hint: str

    @model_validator(mode="after")
    def _validate(self) -> LLMVerdict:
        for line in self.vulnerable_lines:
            if line < 1:
                raise ValueError(
                    f"vulnerable_lines must contain positive integers, got {line}"
                )
        return self


class FinalFinding(BaseModel):
    """Fused, calibrated, and localized finding emitted by post-processing."""

    sample_id: str
    final_label: int
    final_confidence: float = Field(ge=0.0, le=1.0)
    predicted_cwe: str
    vulnerable_lines: list[int] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)
    patch_hint: str

    @model_validator(mode="after")
    def _validate(self) -> FinalFinding:
        if self.final_label not in (0, 1):
            raise ValueError(f"final_label must be 0 or 1, got {self.final_label}")
        for line in self.vulnerable_lines:
            if line < 1:
                raise ValueError(
                    f"vulnerable_lines must contain positive integers, got {line}"
                )
        return self


__all__ = [
    "CodeSpan",
    "SampleRecord",
    "StaticAlertRecord",
    "VerificationPacket",
    "LLMVerdict",
    "FinalFinding",
]
