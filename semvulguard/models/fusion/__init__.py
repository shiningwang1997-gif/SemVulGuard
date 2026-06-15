"""Late-fusion calibrator over static/ranker/LLM signals.

Combines the three independent risk signals into a calibrated final score and
assembles localized :class:`~semvulguard.schemas.records.FinalFinding` records.
"""

from semvulguard.models.fusion.scoring import (
    build_final_finding,
    compute_final_score,
    compute_llm_score,
    compute_static_score,
    final_label_from_score,
    select_predicted_cwe,
)

__all__ = [
    "build_final_finding",
    "compute_final_score",
    "compute_llm_score",
    "compute_static_score",
    "final_label_from_score",
    "select_predicted_cwe",
]
