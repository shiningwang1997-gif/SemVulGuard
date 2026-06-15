"""Line-level vulnerability localization.

Scores individual source lines by combining static, taint-trace, LLM, and graph
evidence, and selects the most suspect lines for a finding.
"""

from semvulguard.localization.line_score import compute_line_scores, top_k_lines

__all__ = ["compute_line_scores", "top_k_lines"]
