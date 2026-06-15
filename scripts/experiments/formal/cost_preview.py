"""Phase 9: real DeepSeek cost preview for top-10 TEST candidates (NO API CALLS).

Renders the exact prompts that would be sent for the top-10 ranked TEST
candidates (via the verifier's dry_run_prompts), measures character counts, and
estimates token usage + dollar cost under deepseek-v4-flash pricing.

Estimation (per brief): input_tokens ~= chars/4; output_tokens ~= 500/sample;
price input cache-miss $0.14/1M, output $0.28/1M. Makes NO network calls.

Writes .../formal_multidataset_v1/real_api_cost_preview.md.
"""

from __future__ import annotations

import json
import sys

from semvulguard.llm.verify import dry_run_prompts

from scripts.experiments.formal.config import (
    MODEL,
    OUT_TOKENS_PER_SAMPLE,
    PRICE_IN_PER_1M,
    PRICE_OUT_PER_1M,
    REAL_TOPK,
    ROOT,
    SUBSET_TARGETS,
)


def preview_one(ds: str) -> dict:
    t = ROOT / ds / "test_only"
    tmp = t / "_cost_preview_prompts.jsonl"
    n = dry_run_prompts(
        features_path=t / "features_test.jsonl",
        rank_scores_path=t / "rank_scores_test.jsonl",
        alerts_path=t / "static_alerts_test.jsonl",
        output_path=tmp,
        top_k=REAL_TOPK,
    )
    total_chars = 0
    for line in tmp.open(encoding="utf-8"):
        rec = json.loads(line)
        for m in rec["messages"]:
            total_chars += len(str(m.get("content", "")))
    tmp.unlink(missing_ok=True)
    avg = total_chars / n if n else 0.0
    in_tok = total_chars / 4
    out_tok = OUT_TOKENS_PER_SAMPLE * n
    cost_in = in_tok / 1_000_000 * PRICE_IN_PER_1M
    cost_out = out_tok / 1_000_000 * PRICE_OUT_PER_1M
    return {"dataset": ds, "candidates": n, "avg_input_chars": avg,
            "est_input_tokens": in_tok, "est_output_tokens": out_tok,
            "est_cost_total_usd": cost_in + cost_out}


def main(argv: list[str] | None = None) -> int:
    targets = argv if argv else list(SUBSET_TARGETS)
    rows = [preview_one(ds) for ds in targets]
    total = sum(r["est_cost_total_usd"] for r in rows)
    total_calls = sum(r["candidates"] for r in rows)
    L = [f"# Real DeepSeek API Cost Preview (top-k={REAL_TOPK}, TEST-only)", "",
         "**No API calls were made to produce this preview.**", "",
         f"- Model: `{MODEL}`",
         f"- top-k: {REAL_TOPK} TEST candidates per dataset (selected from rank_scores_test.jsonl)",
         f"- Pricing: input cache-miss ${PRICE_IN_PER_1M}/1M, output ${PRICE_OUT_PER_1M}/1M",
         f"- Token estimate: input = chars/4; output = {OUT_TOKENS_PER_SAMPLE}/sample (assumed)",
         "", "## Per-dataset estimate", "",
         "| dataset | candidates | avg input chars | est input tok | est output tok | est cost (USD) |",
         "|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['dataset']} | {r['candidates']} | {r['avg_input_chars']:.0f} "
                 f"| {r['est_input_tokens']:.0f} | {r['est_output_tokens']:.0f} "
                 f"| ${r['est_cost_total_usd']:.5f} |")
    L += ["", "## Totals", "",
          f"- Total real API calls if run: **{total_calls}** ({len(rows)} datasets x {REAL_TOPK})",
          f"- **Estimated total cost: ${total:.5f} USD**", "",
          "## Notes", "",
          "- Cost is for ONE real verification pass at top-10 per dataset.",
          "- The 500-token output assumption dominates; real JSON completions are "
          "typically 150-300 tokens, so actual cost is likely LOWER.",
          "- Static-alert evidence is sparse/empty for these wrapped functions, so "
          "prompts are mostly code + ranker score; input size is modest.", ""]
    out = ROOT / "real_api_cost_preview.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {out}; total ${total:.5f} over {total_calls} calls")
    (ROOT / "real_api_cost_preview.json").write_text(
        json.dumps({"rows": rows, "total_cost_usd": total,
                    "total_calls": total_calls}, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or None))
