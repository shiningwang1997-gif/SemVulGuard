"""Static-evidence collection for the semantic verifier.

:class:`EvidenceCollector` distills a feature record, its static alerts, the
ranker score, and optional Joern graph evidence into a compact, deterministic
summary dict. The summary is what guides the LLM: it surfaces dangerous API
call sites, taint sources/sinks, and alert traces without dumping raw artifacts
into the prompt.

This module never calls the LLM and performs no I/O.
"""

from __future__ import annotations

from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import StaticAlertRecord

# Heuristic term sets, matched as substrings against a line of source. These are
# intentionally simple, language-agnostic lexical cues -- not a parser.
DANGEROUS_API_TERMS = (
    "memcpy",
    "strcpy",
    "strcat",
    "sprintf",
    "gets",
    "scanf",
    "system",
    "free",
    "malloc",
    "realloc",
)
SOURCE_TERMS = ("read", "recv", "scanf", "argv", "getenv", "input")
SINK_TERMS = ("memcpy", "strcpy", "strcat", "sprintf", "system", "free")

# Cap on how much code we embed, to keep prompts bounded and deterministic.
MAX_EXCERPT_LINES = 200


class EvidenceCollector:
    """Build a deterministic static-evidence summary for one candidate."""

    def __init__(
        self,
        dangerous_terms: tuple[str, ...] = DANGEROUS_API_TERMS,
        source_terms: tuple[str, ...] = SOURCE_TERMS,
        sink_terms: tuple[str, ...] = SINK_TERMS,
        max_excerpt_lines: int = MAX_EXCERPT_LINES,
    ) -> None:
        self.dangerous_terms = dangerous_terms
        self.source_terms = source_terms
        self.sink_terms = sink_terms
        self.max_excerpt_lines = max_excerpt_lines

    def collect(
        self,
        feature_record: FeatureRecord,
        alerts: list[StaticAlertRecord],
        rank_score: float | None = None,
        joern_evidence: dict | None = None,
    ) -> dict:
        """Return the structured evidence summary for a candidate function.

        The summary is JSON-serializable and stable: line lists are sorted and
        de-duplicated so the same inputs always produce the same dict.
        """
        span = feature_record.span
        absolute_lines = self._absolute_lines(feature_record)

        return {
            "sample_id": feature_record.sample_id,
            "static_alert_count": len(alerts),
            "alert_summaries": [self._summarize_alert(a) for a in alerts],
            "trace_lines": self._trace_lines(feature_record, alerts),
            "dangerous_api_lines": self._match_lines(
                absolute_lines, self.dangerous_terms
            ),
            "source_like_lines": self._match_lines(
                absolute_lines, self.source_terms
            ),
            "sink_like_lines": self._match_lines(absolute_lines, self.sink_terms),
            "rank_score": rank_score,
            "function_span": {
                "file": span.file,
                "start_line": span.start_line,
                "end_line": span.end_line,
            },
            "code_excerpt": self._code_excerpt(feature_record),
            "joern_summary": self._joern_summary(joern_evidence),
        }

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _summarize_alert(alert: StaticAlertRecord) -> dict:
        """A compact, prompt-friendly view of a single static alert."""
        return {
            "tool": alert.tool,
            "query_id": alert.query_id,
            "message": alert.message,
            "severity": alert.severity,
            "start_line": alert.start_line,
            "end_line": alert.end_line,
            "cwe": list(alert.cwe),
        }

    @staticmethod
    def _trace_lines(
        feature_record: FeatureRecord, alerts: list[StaticAlertRecord]
    ) -> list[int]:
        """Sorted, unique taint-trace lines from alerts and the feature record."""
        lines: set[int] = set(feature_record.trace_lines)
        for alert in alerts:
            lines.update(alert.trace_lines)
        return sorted(lines)

    def _absolute_lines(
        self, feature_record: FeatureRecord
    ) -> list[tuple[int, str]]:
        """Pair each source line with its absolute (1-indexed) line number."""
        start = feature_record.span.start_line
        return [
            (start + offset, text)
            for offset, text in enumerate(feature_record.code_lines)
        ]

    @staticmethod
    def _match_lines(
        numbered_lines: list[tuple[int, str]], terms: tuple[str, ...]
    ) -> list[int]:
        """Absolute line numbers whose source text contains any of ``terms``."""
        matched = {
            line_no
            for line_no, text in numbered_lines
            if any(term in text for term in terms)
        }
        return sorted(matched)

    def _code_excerpt(self, feature_record: FeatureRecord) -> str:
        """The function source, truncated to ``max_excerpt_lines`` lines."""
        lines = feature_record.code_lines
        if lines:
            if len(lines) <= self.max_excerpt_lines:
                return "\n".join(lines)
            kept = lines[: self.max_excerpt_lines]
            return "\n".join(kept) + "\n... [truncated]"
        # Fall back to the raw code blob when code_lines is empty.
        return feature_record.function_code

    @staticmethod
    def _joern_summary(joern_evidence: dict | None) -> dict:
        """Pass through Joern evidence as a plain dict (empty when absent)."""
        if not joern_evidence:
            return {}
        return dict(joern_evidence)


__all__ = [
    "EvidenceCollector",
    "DANGEROUS_API_TERMS",
    "SOURCE_TERMS",
    "SINK_TERMS",
]
