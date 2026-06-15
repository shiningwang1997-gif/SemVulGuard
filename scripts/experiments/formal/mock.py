"""Phase 8: mock LLM dry-run on the TEST SET only (pipeline validation).

For each usable dataset:
  1. generate MOCK verdicts for the top-50 TEST candidates (offline rule-based
     MockLLMClient; NO DeepSeek call), reading test_only/ artifacts;
  2. run the method x top-k matrix entirely on test_only/ artifacts via the
     existing runner.run_cell (so every metric is test-only);
  3. emit dataset-level mock summary CSVs + markdown + run_status.json.

Methods: static_only, ranker_only, static_ranker, static_llm, full, llm_only.
Top-k: 0, 10, 30, 50. All clearly labeled MOCK / NOT FINAL SCIENTIFIC RESULTS.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from semvulguard.llm.mock import MockLLMClient
from semvulguard.llm.verify import verify

from scripts.experiments.formal.config import KS_MOCK, ROOT, SUBSET_TARGETS
from scripts.experiments.formal.matrix import (
    BANNER_MOCK,
    METHODS_ALL,
    run_matrix,
    write_dataset_summaries,
)


def gen_mock_verdicts(ds: str) -> int:
    t = ROOT / ds / "test_only"
    out = t / "llm_verdicts_mock_top50.jsonl"
    verdicts = verify(
        features_path=t / "features_test.jsonl",
        rank_scores_path=t / "rank_scores_test.jsonl",
        alerts_path=t / "static_alerts_test.jsonl",
        output_path=out,
        top_k=50,
        client=MockLLMClient(mode="rule"),
        model="mock-rule",
        cost_log_path=None,
    )
    return len(verdicts)


def run_one(ds: str) -> dict:
    t = ROOT / ds / "test_only"
    n_v = gen_mock_verdicts(ds)
    base = ROOT / ds / "mock"
    rows, completed, failed = run_matrix(
        dataset=ds, base_dir=base,
        features_path=t / "features_test.jsonl",
        rank_scores_path=t / "rank_scores_test.jsonl",
        alerts_path=t / "static_alerts_test.jsonl",
        verdicts_path=t / "llm_verdicts_mock_top50.jsonl",
        ks=KS_MOCK, cost_log_path=None,
    )
    write_dataset_summaries(
        ds=ds, out=base, rows=rows, ks=KS_MOCK, completed=completed,
        failed=failed, banner=BANNER_MOCK, mode="mock",
        rank_scores_path=t / "rank_scores_test.jsonl",
        full_fusion_scores=base / "full" / f"topk_{max(KS_MOCK)}" / "fusion_scores.jsonl",
        api_calls=0, cost=0.0,
    )
    print(f"{ds}: mock matrix {len(completed)} ok / {len(failed)} failed "
          f"(verdicts={n_v})")
    return {"dataset": ds, "completed": len(completed), "failed": len(failed),
            "mock_verdicts": n_v}


def main(argv: list[str] | None = None) -> int:
    targets = argv if argv else list(SUBSET_TARGETS)
    results = [run_one(ds) for ds in targets]
    (ROOT / "mock_run_summary.json").write_text(
        json.dumps({"generated": datetime.now(timezone.utc).isoformat(),
                    "results": results}, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or None))
