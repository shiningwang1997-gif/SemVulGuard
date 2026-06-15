"""Code representation builder.

Converts normalized samples, static alerts, and Joern graph slices into
model-ready :class:`FeatureRecord` artifacts: a line-aligned static-evidence
view plus an integer-indexed graph slice. No neural-model code lives here yet.
"""

from semvulguard.features.build import build_feature_record, build_features
from semvulguard.features.graph_features import (
    build_feature_graph,
    extract_static_features,
    severity_score,
)
from semvulguard.features.line_map import (
    absolute_to_relative_line,
    build_line_mask,
    relative_to_absolute_line,
    split_code_lines,
)
from semvulguard.features.tokenizer import (
    basic_code_tokenize,
    truncate_code_by_lines,
)

__all__ = [
    "build_feature_record",
    "build_features",
    "build_feature_graph",
    "extract_static_features",
    "severity_score",
    "split_code_lines",
    "absolute_to_relative_line",
    "relative_to_absolute_line",
    "build_line_mask",
    "basic_code_tokenize",
    "truncate_code_by_lines",
]
