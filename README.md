# SemVulGuard

**SemVulGuard: Static-Analysis-Grounded Vulnerability Detection with Code
Representation Learning and LLM-Based Semantic Verification.**

Static analysis generates structural evidence and candidates → graph/sequence
joint representation learning ranks them → a DeepSeek-based LLM verifies only the
Top-K candidates → late fusion and line-level localization emit SARIF/reports.

## What it does

SemVulGuard is a function-level vulnerability discovery pipeline. Each stage is
a self-contained module with a `python -m` CLI that consumes upstream JSONL
artifacts and emits downstream ones. The cross-module contracts are the Pydantic
records in `semvulguard/schemas/records.py`:

| Record | Role |
|---|---|
| `CodeSpan` | 1-indexed inclusive line span in a file |
| `SampleRecord` | normalized, function-level dataset sample |
| `StaticAlertRecord` | a single static-analysis alert |
| `VerificationPacket` | compressed evidence bundle sent to the LLM |
| `LLMVerdict` | structured LLM verification output |
| `FinalFinding` | fused, calibrated, localized finding |

## Pipeline

```
Raw Datasets / Git Repos
  → Dataset & Labeling Pipeline      (semvulguard.dataset.build)
  → Static Analysis Module           (semvulguard.static: codeql / joern / clang)
  → Code Representation Builder       (semvulguard.features.build)
  → Code Representation Encoder       (semvulguard.models.encoder)
  → Candidate Ranker                  (semvulguard.models.ranker.train / .infer)
  → DeepSeek LLM Semantic Verifier    (semvulguard.llm.verify)
  → Fusion & Alignment Module         (semvulguard.models.fusion.run)
  → Localization & Report Generation  (semvulguard.report.build)
  → Evaluation Harness                (semvulguard.eval.run)
```

## Requirements

* **Python ≥ 3.10** (developed and tested on 3.10).
* No Node.js/JavaScript components — this is a pure-Python project.
* **Core runtime** needs only `pydantic`, `pyyaml`, `requests`.
* **Optional, only for specific stages:**
  * `torch` — required to train/run the neural encoder and candidate ranker
    (`semvulguard.models.*`). The rest of the pipeline runs without it.
  * `transformers`, `torch_geometric` — imported lazily by the encoders for
    HuggingFace sequence encoding (e.g. GraphCodeBERT) and GATv2 graph encoding;
    the encoders fall back to dependency-light modes when these are absent.
  * `scikit-learn` — used lazily by the evaluation harness for ROC-AUC / PR-AUC;
    those two metrics report `None` without it, all others still work.
* **External tools (optional):** CodeQL and Joern CLIs are wrapped by
  `semvulguard.static.*` but are not Python packages — install them separately
  only if you run those static analyzers. Nothing imports them at module load.

## Installation

Create a virtual environment, then install the dependency set you need.

### Quick start (core pipeline: static evidence → LLM verify → fusion → report → eval)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Editable install (equivalent, recommended for development)

```bash
pip install -e .
```

### Optional stages

```bash
# Neural encoder + candidate ranker (adds torch):
pip install -r requirements-models.txt
# ...or with the HuggingFace / GATv2 backends:
pip install -e ".[models-full]"

# ROC-AUC / PR-AUC evaluation metrics (adds scikit-learn):
pip install -r requirements-eval.txt        # or:  pip install -e ".[eval]"

# Development (tests + linter):
pip install -r requirements-dev.txt          # or:  pip install -e ".[dev]"
```

The `requirements*.txt` files mirror the extras declared in `pyproject.toml`;
either mechanism works. `pip install -e .` is preferred when developing because
it also registers the `semvulguard` package itself.

## Environment variables

| Variable | Used by | Purpose |
|---|---|---|
| `DEEPSEEK_API_KEY` | `semvulguard.llm` (`DeepSeekClient`) | DeepSeek API key for the real LLM verifier. Read only from the environment; never logged and scrubbed from error text. **Not required** for `--mock` or `--dry-run-prompts` runs. |

Export it before any real LLM run:

```bash
export DEEPSEEK_API_KEY=...   # do not commit; not read from any config file
```

## Running the pipeline

Every stage ships with runnable examples in its module docstring and accepts
`--help`. The test fixtures under `tests/fixtures/` make convenient tiny inputs.

```bash
# 1. Normalize a raw dataset into a SampleRecord manifest
python -m semvulguard.dataset.build \
    --dataset devign \
    --input tests/fixtures/datasets/devign_sample.jsonl \
    --output artifacts/sample_manifest.jsonl --split random

# 2. Build model-ready FeatureRecords (see `--help` for the manifest convention)
python -m semvulguard.features.build --help

# 3. (optional, needs torch) Train + run the candidate ranker
python -m semvulguard.models.ranker.train \
    --features tests/fixtures/model/features.jsonl \
    --output-dir artifacts/ranker --epochs 2 --batch-size 2 --fallback

# 4. LLM semantic verification of the Top-K candidates
#    --mock runs offline (no API key); drop it for a real DeepSeek run.
python -m semvulguard.llm.verify \
    --features tests/fixtures/llm/features.jsonl \
    --rank-scores tests/fixtures/llm/rank_scores.jsonl \
    --alerts tests/fixtures/llm/alerts.jsonl \
    --output artifacts/llm_verdicts.jsonl \
    --top-k 3 --cost-log artifacts/cost_log.jsonl --mock

# 5. Fuse signals and emit the final report (JSON + JSONL + SARIF)
python -m semvulguard.report.build \
    --features tests/fixtures/fusion/features.jsonl \
    --rank-scores tests/fixtures/fusion/rank_scores.jsonl \
    --alerts tests/fixtures/fusion/static_alerts.jsonl \
    --llm-verdicts tests/fixtures/fusion/llm_verdicts.jsonl \
    --output-dir artifacts/report

# 6. Evaluate against labels / ground truth
python -m semvulguard.eval.run \
    --features tests/fixtures/eval/features.jsonl \
    --findings tests/fixtures/eval/findings.jsonl \
    --rank-scores tests/fixtures/eval/rank_scores.jsonl \
    --output-dir artifacts/eval --threshold 0.5
```

### LLM verifier modes

`semvulguard.llm.verify` has three modes:

* **real** (default) — uses `DeepSeekClient`; requires `DEEPSEEK_API_KEY`.
* `--mock` — offline `MockLLMClient`, no network or key (used by the tests).
* `--dry-run-prompts` — writes the rendered prompts to `--output` without
  calling any LLM.

It also writes an optional per-call cost/latency log via `--cost-log` (tokens,
latency, model, success — never prompt content or the key).

## Input / output artifacts

* **Inputs** are JSONL files of the schema records above (see `tests/fixtures/`
  for canonical examples). Each stage keys records by `sample_id`.
* **Outputs** land in `artifacts/` (intermediate JSONL) and `reports/` (final
  findings, SARIF, metrics). These directories ship with a `.gitkeep`; their
  contents are generated and need not be committed.
* **Configuration** lives in `configs/*.yaml` (dataset, static, train, llm,
  eval) and is loaded via `semvulguard.utils.config`. Secrets are **not** stored
  in configs — the API key comes only from the environment.

## Layout

```
configs/        YAML configs (dataset, static, train, llm, eval)
semvulguard/    library package
  schemas/      Pydantic data contracts
  utils/        JSONL I/O, config loader, logging
  dataset/ static/ features/ models/ llm/ localization/ report/ eval/
artifacts/      generated intermediate artifacts (gitkeep'd)
reports/        final findings, metrics, figures (gitkeep'd)
tests/          unit / integration tests + fixtures
```

## Development

```bash
pip install -e ".[dev]"     # or: pip install -r requirements-dev.txt && pip install -e .
pytest                       # 369 tests, runs fully offline (no API key needed)
ruff check .
```

The full test suite is offline by design — it uses the mock LLM client and
dependency-light fallback encoders, so it needs neither `DEEPSEEK_API_KEY`,
`torch`, nor any external analyzer.
