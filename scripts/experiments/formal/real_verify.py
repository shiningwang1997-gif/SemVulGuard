"""Phase 10: REAL DeepSeek verification of the top-10 TEST candidates.

Runs the existing verifier (verify()) with a real DeepSeekClient over the top-10
candidates from rank_scores_test.jsonl per dataset. temperature=0.0, JSON mode.
The API key is read from the environment by DeepSeekClient and is never printed,
logged, or written to disk. After the run we enrich the cost log with a per-call
api_cost_usd computed from token usage x deepseek-v4-flash pricing.

Outputs per dataset under .../{ds}/test_only/:
  llm_verdicts_real_top10.jsonl, real_llm_cost_log_top10.jsonl

Guardrails:
  * top-k = 10 ONLY (REAL_TOPK); never expands to 50.
  * candidates come from rank_scores_test.jsonl (test set), so NO train/valid
    sample is ever sent to the API.
  * every produced LLMVerdict is schema-validated (the verifier already does
    parse-repair/retry; invalid output degrades to a conservative uncertain
    verdict and is recorded as success=false).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from semvulguard.llm.client import DeepSeekClient
from semvulguard.llm.verify import verify
from semvulguard.schemas.records import LLMVerdict
from semvulguard.utils.jsonl import read_models

from scripts.experiments.formal.config import (
    MODEL,
    PRICE_IN_PER_1M,
    PRICE_OUT_PER_1M,
    REAL_TOPK,
    ROOT,
    SUBSET_TARGETS,
)


def _enrich_cost_log(path: Path) -> tuple[float, int, int]:
    """Add api_cost_usd to each record from token usage. Returns (total, calls, ok)."""
    if not path.exists():
        return 0.0, 0, 0
    records = []
    for line in path.open(encoding="utf-8"):
        line = line.strip()
        if line:
            records.append(json.loads(line))
    total = 0.0
    ok = 0
    for r in records:
        pt = r.get("prompt_tokens") or 0
        ct = r.get("completion_tokens") or 0
        cost = pt / 1_000_000 * PRICE_IN_PER_1M + ct / 1_000_000 * PRICE_OUT_PER_1M
        r["api_cost_usd"] = round(cost, 8)
        total += cost
        if r.get("success"):
            ok += 1
    with path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return total, len(records), ok


def run_one(ds: str) -> dict:
    t = ROOT / ds / "test_only"
    verdicts_out = t / "llm_verdicts_real_top10.jsonl"
    cost_out = t / "real_llm_cost_log_top10.jsonl"

    client = DeepSeekClient(model=MODEL, temperature=0.0, json_mode=True)
    verdicts = verify(
        features_path=t / "features_test.jsonl",
        rank_scores_path=t / "rank_scores_test.jsonl",
        alerts_path=t / "static_alerts_test.jsonl",
        output_path=verdicts_out,
        top_k=REAL_TOPK,
        client=client,
        model=MODEL,
        cost_log_path=cost_out,
    )
    # validate every verdict against schema (re-read from disk)
    reload = read_models(verdicts_out, LLMVerdict)
    total_cost, calls, ok = _enrich_cost_log(cost_out)
    vc = {}
    for v in reload:
        vc[v.verdict] = vc.get(v.verdict, 0) + 1
    print(f"{ds}: real top-{REAL_TOPK} -> {len(reload)} verdicts {dict(vc)}, "
          f"{ok}/{calls} api ok, cost ${total_cost:.6f}")
    return {"dataset": ds, "verdicts": len(reload), "verdict_counts": vc,
            "api_calls": calls, "api_ok": ok, "cost_usd": total_cost,
            "verdicts_path": str(verdicts_out), "cost_log": str(cost_out)}


def main(argv: list[str] | None = None) -> int:
    targets = argv if argv else list(SUBSET_TARGETS)
    results = [run_one(ds) for ds in targets]
    total = sum(r["cost_usd"] for r in results)
    calls = sum(r["api_calls"] for r in results)
    (ROOT / "real_top10_summary.json").write_text(
        json.dumps({"model": MODEL, "top_k": REAL_TOPK, "total_calls": calls,
                    "total_cost_usd": round(total, 6), "results": results},
                   indent=2) + "\n", encoding="utf-8")
    print(f"\nREAL top-{REAL_TOPK} done: {calls} calls, ${total:.6f} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or None))
