"""Phase 10 (v2): REAL DeepSeek verification of the top-50 TEST candidates.

Mirror of real_verify.py, but scaled to the v2 experiment:
  * output root = formal_multidataset_v2_scaled (never touches v1);
  * top-k = 50 (REAL_TOPK_V2);
  * also dumps the selected candidate id list per dataset.

Runs the existing verifier (verify()) with a real DeepSeekClient over the top-50
candidates from rank_scores_test.jsonl per dataset. temperature=0.0, JSON mode.
The API key is read from the environment by DeepSeekClient and is never printed,
logged, or written to disk. After the run we enrich the cost log with a per-call
api_cost_usd computed from token usage x deepseek-v4-flash pricing.

Outputs per dataset under .../{ds}/test_only/:
  real_top50_candidate_ids.jsonl   (the selected top-50 sample_ids, ranked)
  llm_verdicts_real_top50.jsonl
  real_llm_cost_log_top50.jsonl

Guardrails:
  * top-k = 50 ONLY (REAL_TOPK_V2); never expands beyond.
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
from semvulguard.llm.packet import select_topk_candidates
from semvulguard.llm.verify import verify
from semvulguard.schemas.records import LLMVerdict
from semvulguard.utils.jsonl import read_models

from scripts.experiments.formal.config_v2 import (
    MODEL,
    PRICE_IN_PER_1M,
    PRICE_OUT_PER_1M,
    ROOT,
    SUBSET_TARGETS,
)

REAL_TOPK_V2 = 50


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
        r["estimated_api_cost_usd"] = round(cost, 8)
        r["api_cost_usd"] = round(cost, 8)  # kept for the eval cost aggregator
        total += cost
        if r.get("success"):
            ok += 1
    with path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return total, len(records), ok


def _dump_candidate_ids(t: Path, top_k: int) -> list[str]:
    """Select and persist the ranked top-k test candidate ids."""
    ids = select_topk_candidates(t / "rank_scores_test.jsonl", top_k)
    out = t / "real_top50_candidate_ids.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for rank, sid in enumerate(ids, start=1):
            fh.write(json.dumps({"rank": rank, "sample_id": sid},
                                ensure_ascii=False) + "\n")
    return ids


def run_one(ds: str) -> dict:
    t = ROOT / ds / "test_only"
    verdicts_out = t / "llm_verdicts_real_top50.jsonl"
    cost_out = t / "real_llm_cost_log_top50.jsonl"

    candidate_ids = _dump_candidate_ids(t, REAL_TOPK_V2)

    client = DeepSeekClient(model=MODEL, temperature=0.0, json_mode=True)
    verify(
        features_path=t / "features_test.jsonl",
        rank_scores_path=t / "rank_scores_test.jsonl",
        alerts_path=t / "static_alerts_test.jsonl",
        output_path=verdicts_out,
        top_k=REAL_TOPK_V2,
        client=client,
        model=MODEL,
        cost_log_path=cost_out,
    )
    # validate every verdict against schema (re-read from disk)
    reload = read_models(verdicts_out, LLMVerdict)
    total_cost, calls, ok = _enrich_cost_log(cost_out)
    vc: dict[str, int] = {}
    for v in reload:
        vc[v.verdict] = vc.get(v.verdict, 0) + 1
    print(f"{ds}: real top-{REAL_TOPK_V2} -> {len(reload)} verdicts {dict(vc)}, "
          f"{ok}/{calls} api ok, cost ${total_cost:.6f}")
    return {"dataset": ds, "candidates": len(candidate_ids),
            "verdicts": len(reload), "verdict_counts": vc,
            "api_calls": calls, "api_ok": ok, "api_failed": calls - ok,
            "cost_usd": total_cost,
            "candidate_ids_path": str(t / "real_top50_candidate_ids.jsonl"),
            "verdicts_path": str(verdicts_out), "cost_log": str(cost_out)}


def main(argv: list[str] | None = None) -> int:
    targets = argv if argv else list(SUBSET_TARGETS)
    results = [run_one(ds) for ds in targets]
    total = sum(r["cost_usd"] for r in results)
    calls = sum(r["api_calls"] for r in results)
    ok = sum(r["api_ok"] for r in results)
    (ROOT / "real_top50_summary.json").write_text(
        json.dumps({"model": MODEL, "top_k": REAL_TOPK_V2, "total_calls": calls,
                    "total_api_ok": ok, "total_api_failed": calls - ok,
                    "total_cost_usd": round(total, 6), "results": results},
                   indent=2) + "\n", encoding="utf-8")
    print(f"\nREAL top-{REAL_TOPK_V2} done: {calls} calls ({ok} ok), ${total:.6f} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or None))
