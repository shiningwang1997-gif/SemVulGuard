"""Feature-builder data contracts.

These records are the model-ready artifacts emitted by ``semvulguard.features``.
They sit downstream of the cross-module contracts in
:mod:`semvulguard.schemas.records` and bundle, per sample, the tokenizable
function source, a line-aligned static-evidence view, and an integer-indexed
graph slice ready for tensorization in a later phase.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from semvulguard.schemas.records import CodeSpan


class FeatureNode(BaseModel):
    """A graph node enriched with line alignment and static flags."""

    node_id: str
    node_type: str
    code: str
    line: int | None = None
    line_index: int | None = None
    static_flags: dict[str, int | float] = Field(default_factory=dict)


class FeatureEdge(BaseModel):
    """A directed edge referencing nodes by integer index into the node list."""

    source: int
    target: int
    edge_type: str


class FeatureRecord(BaseModel):
    """All model-ready features for a single sample."""

    sample_id: str
    label: int
    cwe: list[str] = Field(default_factory=list)
    file: str
    function: str | None = None
    span: CodeSpan
    function_code: str
    code_lines: list[str] = Field(default_factory=list)
    alert_lines: list[int] = Field(default_factory=list)
    trace_lines: list[int] = Field(default_factory=list)
    nodes: list[FeatureNode] = Field(default_factory=list)
    edges: list[FeatureEdge] = Field(default_factory=list)
    static_features: dict[str, int | float | str] = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


__all__ = ["FeatureNode", "FeatureEdge", "FeatureRecord"]
