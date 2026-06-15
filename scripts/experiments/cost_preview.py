"""Phase 6: real DeepSeek cost preview for max_k=10 (NO API CALLS).

For each ready dataset we render the exact prompts that would be sent for the
top-10 ranked candidates (reusing the verifier's PromptBuilder via
``dry_run_prompts``), measure their character counts, and estimate token usage
and dollar cost under deepseek-v4-flash pricing.

Estimation rules (per the task brief):
  input_tokens  ~= input_chars / 4
  output_tokens ~= 500 per sample (assumed)
  price: input (cache miss) $0.14 / 1M, output $0.28 / 1M

Writes artifacts/experiments/real_api_cost_preview.md. Makes no network calls.
"""

from __future__ import annotations

import json
from pathlib import Path

from semvulguard.llm.verify import dry_run_prompts

EXP = Path("artifacts/experiments")
READY = ["devign"]
MAX_K = 10
MODEL = "deepseek-v4-flash"
PRICE_IN_PER_1M = 0.14
PRICE_OUT_PER_1M = 0.28
OUT_TOKENS_PER_SAMPLE = 500


def preview_one(ds: str) -> dict:
    d = EXP / ds
    tmp = d / "real" / "_cost_preview_prompts.jsonl"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    n = dry_run_prompts(
        features_path=d / "features.jsonl",
        rank_scores_path=d / "rank_scores.jsonl",
        alerts_path=d / "static_alerts.jsonl",
        output_path=tmp,
        top_k=MAX_K,
    )
    total_chars = 0
    for line in tmp.open(encoding="utf-8"):
        rec = json.loads(line)
        for m in rec["messages"]:
            total_chars += len(str(m.get("content", "")))
    avg_chars = total_chars / n if n else 0.0
    in_tokens = total_chars / 4
    out_tokens = OUT_TOKENS_PER_SAMPLE * n
    cost_in = in_tokens / 1_000_000 * PRICE_IN_PER_1M
    cost_out = out_tokens / 1_000_000 * PRICE_OUT_PER_1M
    return {
        "dataset": ds, "candidates": n, "total_input_chars": total_chars,
        "avg_input_chars": avg_chars, "est_input_tokens": in_tokens,
        "est_output_tokens": out_tokens, "est_cost_input_usd": cost_in,
        "est_cost_output_usd": cost_out, "est_cost_total_usd": cost_in + cost_out,
    }


def main() -> int:
    rows = [preview_one(ds) for ds in READY]
    total = sum(r["est_cost_total_usd"] for r in rows)
    total_calls = sum(r["candidates"] for r in rows)

    lines = ["# Real DeepSeek API Cost Preview (max_k=10)", "",
             "**No API calls were made to produce this preview.**", "",
             f"- Model: `{MODEL}`", f"- max_k: {MAX_K} candidates per dataset",
             f"- Pricing: input cache-miss ${PRICE_IN_PER_1M}/1M, output ${PRICE_OUT_PER_1M}/1M",
             f"- Token estimate: input = chars/4; output = {OUT_TOKENS_PER_SAMPLE}/sample (assumed)",
             "", "## Per-dataset estimate", "",
             "| dataset | candidates | avg input chars | est input tok | est output tok | est cost (USD) |",
             "| --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        lines.append(
            f"| {r['dataset']} | {r['candidates']} | {r['avg_input_chars']:.0f} | "
            f"{r['est_input_tokens']:.0f} | {r['est_output_tokens']:.0f} | "
            f"${r['est_cost_total_usd']:.5f} |"
        )
    lines += ["",
              f"## Totals", "",
              f"- Total candidates (real API calls if run): **{total_calls}**",
              f"- **Estimated total cost: ${total:.5f} USD**", "",
              "## Notes", "",
              "- This is the cost for ONE real verification pass at max_k=10. "
              "Smaller k (none below 10 requested for real) would reuse/slice these verdicts.",
              "- Output-token assumption (500/sample) dominates the estimate; actual "
              "completions for this JSON schema are typically 150-300 tokens, so real "
              "cost is likely LOWER than estimated.",
              "- Static-alert evidence is empty (no analyzer installed), so prompts are "
              "code + ranker-score only; input size is modest.", ""]
    out = EXP / "real_api_cost_preview.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # cleanup temp prompt files
    for ds in READY:
        (EXP / ds / "real" / "_cost_preview_prompts.jsonl").unlink(missing_ok=True)
    print(f"wrote {out}")
    print(f"total estimated cost: ${total:.5f} over {total_calls} calls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
