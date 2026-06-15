"""Phase 11: REAL test-only fusion + evaluation matrix (top-k 0 and 10).

For each dataset with real top-10 verdicts, run the method x top-k matrix on the
test_only/ artifacts using the real DeepSeek verdicts + real cost log. All
metrics are test-only. Writes per-dataset real/ summaries.

Methods: static_only, ranker_only, static_ranker, static_llm, full, llm_only.
Top-k: 0, 10.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts.experiments.formal.config import KS_REAL, MODEL, ROOT, SUBSET_TARGETS
from scripts.experiments.formal.matrix import run_matrix, write_dataset_summaries


def _cost_total(path: Path) -> tuple[float, int]:
    if not path.exists():
        return 0.0, 0
    rows = [json.loads(l) for l in path.open() if l.strip()]
    return sum(float(r.get("api_cost_usd", 0.0)) for r in rows), len(rows)


def run_one(ds: str) -> dict:
    t = ROOT / ds / "test_only"
    base = ROOT / ds / "real"
    cost_log = t / "real_llm_cost_log_top10.jsonl"
    verdicts = t / "llm_verdicts_real_top10.jsonl"
    cost, calls = _cost_total(cost_log)

    rows, completed, failed = run_matrix(
        dataset=ds, base_dir=base,
        features_path=t / "features_test.jsonl",
        rank_scores_path=t / "rank_scores_test.jsonl",
        alerts_path=t / "static_alerts_test.jsonl",
        verdicts_path=verdicts,
        ks=KS_REAL, cost_log_path=cost_log,
    )
    write_dataset_summaries(
        ds=ds, out=base, rows=rows, ks=KS_REAL, completed=completed,
        failed=failed, banner="", mode="real",
        rank_scores_path=t / "rank_scores_test.jsonl",
        full_fusion_scores=base / "full" / f"topk_{max(KS_REAL)}" / "fusion_scores.jsonl",
        api_calls=calls, cost=cost,
    )
    print(f"{ds}: real matrix {len(completed)} ok / {len(failed)} failed, "
          f"{calls} calls ${cost:.6f}")
    return {"dataset": ds, "completed": len(completed), "failed": len(failed),
            "api_calls": calls, "cost_usd": cost}


def main(argv: list[str] | None = None) -> int:
    targets = argv if argv else list(SUBSET_TARGETS)
    results = [run_one(ds) for ds in targets]
    (ROOT / "real_eval_summary.json").write_text(
        json.dumps({"model": MODEL, "results": results}, indent=2) + "\n",
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or None))
