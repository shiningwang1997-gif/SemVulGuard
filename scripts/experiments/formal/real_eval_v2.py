"""Phase 11 (v2): REAL test-only fusion + evaluation matrix (top-k 0/10/30/50).

For each dataset with real top-50 verdicts, run the method x top-k matrix on the
test_only/ artifacts using the real DeepSeek verdicts + real cost log. All
metrics are test-only. Writes per-dataset real_top50/ summaries.

Methods: static_only, ranker_only, static_ranker, static_llm, full, llm_only.
Top-k: 0, 10, 30, 50.

Top-k masking is handled by runner.run_cell: for a given k it slices the verdicts
file to exactly the top-k test sample_ids (by rank score), so samples outside the
selected top-k never receive an LLM score, and k=0 uses no LLM verdicts at all.
Because real verdicts exist only for the top-50, k in {10,30,50} use the top-10 /
top-30 / all-50 of those verdicts respectively.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts.experiments.formal.config_v2 import MODEL, ROOT, SUBSET_TARGETS
from scripts.experiments.formal.matrix import run_matrix, write_dataset_summaries

KS_REAL_V2 = [0, 10, 30, 50]


def _cost_total(path: Path) -> tuple[float, int]:
    if not path.exists():
        return 0.0, 0
    rows = [json.loads(l) for l in path.open() if l.strip()]
    return sum(float(r.get("api_cost_usd", 0.0)) for r in rows), len(rows)


def run_one(ds: str) -> dict:
    t = ROOT / ds / "test_only"
    base = ROOT / ds / "real_top50"
    cost_log = t / "real_llm_cost_log_top50.jsonl"
    verdicts = t / "llm_verdicts_real_top50.jsonl"
    cost, calls = _cost_total(cost_log)

    rows, completed, failed = run_matrix(
        dataset=ds, base_dir=base,
        features_path=t / "features_test.jsonl",
        rank_scores_path=t / "rank_scores_test.jsonl",
        alerts_path=t / "static_alerts_test.jsonl",
        verdicts_path=verdicts,
        ks=KS_REAL_V2, cost_log_path=cost_log,
    )
    write_dataset_summaries(
        ds=ds, out=base, rows=rows, ks=KS_REAL_V2, completed=completed,
        failed=failed, banner="REAL DeepSeek top-50 / TEST-only", mode="real",
        rank_scores_path=t / "rank_scores_test.jsonl",
        full_fusion_scores=base / "full" / f"topk_{max(KS_REAL_V2)}" / "fusion_scores.jsonl",
        api_calls=calls, cost=cost,
    )
    print(f"{ds}: real_top50 matrix {len(completed)} ok / {len(failed)} failed, "
          f"{calls} calls ${cost:.6f}")
    return {"dataset": ds, "completed": len(completed), "failed": len(failed),
            "failed_cells": failed, "api_calls": calls, "cost_usd": cost}


def main(argv: list[str] | None = None) -> int:
    targets = argv if argv else list(SUBSET_TARGETS)
    results = [run_one(ds) for ds in targets]
    (ROOT / "real_top50_eval_summary.json").write_text(
        json.dumps({"model": MODEL, "top_k_values": KS_REAL_V2,
                    "results": results}, indent=2) + "\n",
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or None))
