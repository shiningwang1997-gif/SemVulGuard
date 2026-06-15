"""Lightweight scikit-learn ranker (``sklearn_tfidf`` backend).

A deterministic, CPU-only alternative to the torch ``CandidateRanker`` that
strengthens the Code-Representation-Learning channel without any deep model or
network access. It combines three feature families into one sparse design
matrix and fits a linear / tree classifier whose positive-class probability is
used as the candidate ``rank_score``:

1. **TF-IDF** over the raw ``function_code`` (character + word level signal);
2. **simple code metrics** (length, token, and risky-construct counts);
3. **CodeQL static-alert features** (alert/severity/query/CWE/trace counts);
4. the existing numeric ``static_features`` carried on each ``FeatureRecord``.

The TF-IDF block and the dense numeric block are concatenated into a single
sparse matrix (numeric columns standardized with a mean-free scaler so they stay
sparse-compatible). Everything is seeded, so repeated runs are bit-stable.

This module only *defines* the model and feature extraction; training and
inference live in :mod:`semvulguard.models.ranker.train_sklearn` and
:mod:`semvulguard.models.ranker.infer_sklearn`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
from scipy import sparse
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import StaticAlertRecord
from semvulguard.utils.jsonl import read_models

# -- feature layout (fixed, ordered) ----------------------------------------

CODE_METRIC_KEYS = (
    "line_count",
    "char_count",
    "token_count",
    "dangerous_api_count",
    "pointer_operator_count",
    "array_access_count",
    "loop_count",
    "if_count",
    "return_count",
)

STATIC_ALERT_KEYS = (
    "alert_count",
    "has_codeql_alert",
    "high_severity_count",
    "unique_query_count",
    "cwe_count",
    "trace_line_count",
)

# Numeric static_features carried on each FeatureRecord that we reuse if present.
FEATURE_RECORD_STATIC_KEYS = (
    "alert_count",
    "trace_line_count",
    "unique_query_count",
    "has_codeql_alert",
    "max_severity_score",
    "function_line_count",
    "graph_node_count",
    "graph_edge_count",
    "dangerous_api_count",
)

# Severities CodeQL emits that we treat as "high".
_HIGH_SEVERITIES = {"error", "critical", "high"}

# A small, conservative set of memory/format/command APIs frequently implicated
# in C/C++ vulnerabilities. Used only as a cheap density signal.
DANGEROUS_APIS = (
    "strcpy", "strcat", "sprintf", "vsprintf", "gets", "scanf", "sscanf",
    "memcpy", "memmove", "memset", "alloca", "malloc", "calloc", "realloc",
    "free", "strncpy", "strncat", "snprintf", "system", "popen", "exec",
    "execl", "execlp", "execle", "execv", "execvp", "fscanf", "vscanf",
)

_TOKEN_RE = re.compile(r"[A-Za-z_]\w*|\d+|[^\s\w]")
_IDENT_RE = re.compile(r"[A-Za-z_]\w*")
_WORD_BOUND = re.compile(r"\b")


def compute_code_metrics(function_code: str) -> dict[str, float]:
    """Cheap syntactic metrics over the raw function source."""
    code = function_code or ""
    tokens = _TOKEN_RE.findall(code)
    idents = _IDENT_RE.findall(code)
    ident_counts: dict[str, int] = {}
    for tok in idents:
        ident_counts[tok] = ident_counts.get(tok, 0) + 1

    dangerous = sum(ident_counts.get(api, 0) for api in DANGEROUS_APIS)
    # pointer/deref/arrow operators
    pointer_ops = code.count("->") + code.count("*") + code.count("&")
    array_access = code.count("[")
    loop_count = ident_counts.get("for", 0) + ident_counts.get("while", 0)
    if_count = ident_counts.get("if", 0)
    return_count = ident_counts.get("return", 0)

    return {
        "line_count": float(code.count("\n") + 1 if code else 0),
        "char_count": float(len(code)),
        "token_count": float(len(tokens)),
        "dangerous_api_count": float(dangerous),
        "pointer_operator_count": float(pointer_ops),
        "array_access_count": float(array_access),
        "loop_count": float(loop_count),
        "if_count": float(if_count),
        "return_count": float(return_count),
    }


def compute_static_alert_features(
    alerts: list[StaticAlertRecord],
) -> dict[str, float]:
    """Aggregate per-sample CodeQL alert features."""
    if not alerts:
        return {k: 0.0 for k in STATIC_ALERT_KEYS}
    high = sum(1 for a in alerts if (a.severity or "").lower() in _HIGH_SEVERITIES)
    queries = {a.query_id for a in alerts}
    cwes = {c for a in alerts for c in (a.cwe or [])}
    trace_lines = sum(len(a.trace_lines or []) for a in alerts)
    return {
        "alert_count": float(len(alerts)),
        "has_codeql_alert": 1.0,
        "high_severity_count": float(high),
        "unique_query_count": float(len(queries)),
        "cwe_count": float(len(cwes)),
        "trace_line_count": float(trace_lines),
    }


def _coerce_number(value) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def extract_record_static_features(
    static_features: dict,
) -> dict[str, float]:
    """Pull the reusable numeric FeatureRecord.static_features (prefixed)."""
    return {
        f"rec_{k}": _coerce_number(static_features.get(k, 0))
        for k in FEATURE_RECORD_STATIC_KEYS
    }


# Fully-ordered numeric feature column names (stable across train/infer).
NUMERIC_FEATURE_NAMES: tuple[str, ...] = (
    tuple(CODE_METRIC_KEYS)
    + tuple(STATIC_ALERT_KEYS)
    + tuple(f"rec_{k}" for k in FEATURE_RECORD_STATIC_KEYS)
)


@dataclass
class RankerSample:
    """One ranking example: source text + numeric features + label."""

    sample_id: str
    label: int
    function_code: str
    numeric: dict[str, float]
    metadata: dict = field(default_factory=dict)

    def numeric_vector(self) -> list[float]:
        return [self.numeric.get(name, 0.0) for name in NUMERIC_FEATURE_NAMES]


def group_alerts_by_sample(
    static_alerts_path: str | Path | None,
) -> dict[str, list[StaticAlertRecord]]:
    """Group CodeQL alerts by ``sample_id`` (empty dict if no path/file)."""
    grouped: dict[str, list[StaticAlertRecord]] = {}
    if not static_alerts_path:
        return grouped
    path = Path(static_alerts_path)
    if not path.exists():
        return grouped
    for alert in read_models(path, StaticAlertRecord):
        grouped.setdefault(alert.sample_id, []).append(alert)
    return grouped


def build_samples(
    features_path: str | Path,
    static_alerts_path: str | Path | None = None,
) -> list[RankerSample]:
    """Read feature records + CodeQL alerts into ordered :class:`RankerSample`s.

    Order follows the feature file. Every feature record yields one sample; a
    sample with no alerts simply gets zeroed alert features.
    """
    records = read_models(Path(features_path), FeatureRecord)
    alerts_by_sample = group_alerts_by_sample(static_alerts_path)

    samples: list[RankerSample] = []
    for rec in records:
        numeric: dict[str, float] = {}
        numeric.update(compute_code_metrics(rec.function_code))
        numeric.update(
            compute_static_alert_features(alerts_by_sample.get(rec.sample_id, []))
        )
        numeric.update(extract_record_static_features(rec.static_features))
        samples.append(
            RankerSample(
                sample_id=rec.sample_id,
                label=int(rec.label),
                function_code=rec.function_code or "",
                numeric=numeric,
                metadata=dict(rec.metadata or {}),
            )
        )
    return samples


def _build_classifier(model: str, seed: int):
    """Construct the deterministic classifier requested by name."""
    if model == "logistic_regression":
        return LogisticRegression(
            class_weight="balanced",
            max_iter=2000,
            solver="liblinear",
            random_state=seed,
        )
    if model == "random_forest":
        return RandomForestClassifier(
            n_estimators=300,
            class_weight="balanced",
            random_state=seed,
            n_jobs=1,
        )
    raise ValueError(
        f"unknown model {model!r}; expected 'logistic_regression' or 'random_forest'"
    )


class SklearnRanker:
    """TF-IDF + numeric-feature classifier producing a [0,1] ``rank_score``.

    The fitted artifact bundles the TF-IDF vectorizer, the numeric-feature
    scaler, the classifier, and the ordered numeric column names so inference is
    reproducible from a saved file alone.
    """

    BACKEND = "sklearn_tfidf"

    def __init__(
        self,
        model: str = "logistic_regression",
        seed: int = 42,
        max_features: int = 20000,
        ngram_range: tuple[int, int] = (1, 2),
        min_df: int = 1,
    ) -> None:
        self.model_name = model
        self.seed = seed
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=ngram_range,
            min_df=min_df,
            token_pattern=r"[A-Za-z_]\w+|\d+|[^\s\w]",
            lowercase=False,
            sublinear_tf=True,
        )
        self.scaler = StandardScaler(with_mean=False)
        self.classifier = _build_classifier(model, seed)
        self.numeric_feature_names: list[str] = list(NUMERIC_FEATURE_NAMES)
        self._positive_index: int = 1

    # -- matrix assembly ----------------------------------------------------

    def _numeric_matrix(self, samples: list[RankerSample]) -> np.ndarray:
        return np.asarray(
            [s.numeric_vector() for s in samples], dtype=np.float64
        )

    def _design_matrix(self, tfidf, numeric_scaled) -> sparse.csr_matrix:
        return sparse.hstack(
            [tfidf, sparse.csr_matrix(numeric_scaled)], format="csr"
        )

    # -- fit / predict ------------------------------------------------------

    def fit(self, samples: list[RankerSample]) -> SklearnRanker:
        texts = [s.function_code for s in samples]
        labels = np.asarray([s.label for s in samples], dtype=np.int64)
        tfidf = self.vectorizer.fit_transform(texts)
        numeric = self._numeric_matrix(samples)
        numeric_scaled = self.scaler.fit_transform(numeric)
        design = self._design_matrix(tfidf, numeric_scaled)
        self.classifier.fit(design, labels)
        classes = list(self.classifier.classes_)
        self._positive_index = classes.index(1) if 1 in classes else len(classes) - 1
        return self

    def predict_scores(self, samples: list[RankerSample]) -> np.ndarray:
        """Positive-class probability in [0,1] for each sample."""
        if not samples:
            return np.zeros((0,), dtype=np.float64)
        texts = [s.function_code for s in samples]
        tfidf = self.vectorizer.transform(texts)
        numeric = self._numeric_matrix(samples)
        numeric_scaled = self.scaler.transform(numeric)
        design = self._design_matrix(tfidf, numeric_scaled)
        proba = self.classifier.predict_proba(design)
        return proba[:, self._positive_index].astype(np.float64)

    def feature_importance(self) -> list[tuple[str, float]]:
        """Numeric-feature importances/coefficients (TF-IDF terms excluded).

        Returns ``(feature_name, weight)`` for the numeric block only, sorted by
        descending absolute weight. The numeric block is the final
        ``len(numeric_feature_names)`` columns of the design matrix.
        """
        n_numeric = len(self.numeric_feature_names)
        if isinstance(self.classifier, LogisticRegression):
            coef = np.ravel(self.classifier.coef_)
            weights = coef[-n_numeric:]
        elif isinstance(self.classifier, RandomForestClassifier):
            imp = self.classifier.feature_importances_
            weights = imp[-n_numeric:]
        else:  # pragma: no cover
            return []
        pairs = list(
            zip(
                self.numeric_feature_names,
                (float(w) for w in weights),
                strict=True,
            )
        )
        pairs.sort(key=lambda kv: abs(kv[1]), reverse=True)
        return pairs

    # -- persistence --------------------------------------------------------

    def save(self, model_dir: str | Path) -> tuple[Path, Path]:
        """Persist the classifier bundle + vectorizer to ``model_dir``.

        Writes ``model.joblib`` (classifier, scaler, config) and
        ``vectorizer.joblib`` (the fitted TF-IDF vectorizer). Returns both paths.
        """
        model_dir = Path(model_dir)
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / "model.joblib"
        vec_path = model_dir / "vectorizer.joblib"
        joblib.dump(
            {
                "backend": self.BACKEND,
                "model_name": self.model_name,
                "seed": self.seed,
                "classifier": self.classifier,
                "scaler": self.scaler,
                "numeric_feature_names": self.numeric_feature_names,
                "positive_index": self._positive_index,
            },
            model_path,
        )
        joblib.dump(self.vectorizer, vec_path)
        return model_path, vec_path

    @classmethod
    def load(cls, model_dir: str | Path) -> SklearnRanker:
        model_dir = Path(model_dir)
        bundle = joblib.load(model_dir / "model.joblib")
        vectorizer = joblib.load(model_dir / "vectorizer.joblib")
        obj = cls.__new__(cls)
        obj.model_name = bundle["model_name"]
        obj.seed = bundle["seed"]
        obj.classifier = bundle["classifier"]
        obj.scaler = bundle["scaler"]
        obj.numeric_feature_names = list(bundle["numeric_feature_names"])
        obj._positive_index = bundle.get("positive_index", 1)
        obj.vectorizer = vectorizer
        return obj


__all__ = [
    "SklearnRanker",
    "RankerSample",
    "build_samples",
    "group_alerts_by_sample",
    "compute_code_metrics",
    "compute_static_alert_features",
    "extract_record_static_features",
    "CODE_METRIC_KEYS",
    "STATIC_ALERT_KEYS",
    "FEATURE_RECORD_STATIC_KEYS",
    "NUMERIC_FEATURE_NAMES",
    "DANGEROUS_APIS",
]
