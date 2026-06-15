"""Prompt text for the semantic verifier.

All prompt strings live here so they can be reviewed and tuned in one place,
separate from the rendering logic in :mod:`semvulguard.llm.prompt_builder`.
There are two flows: the primary verification prompt and a JSON-repair prompt
used when a response fails to parse or validate.

``RESPONSE_SCHEMA`` is the machine-readable contract embedded in the prompts;
``REQUIRED_JSON_SCHEMA_TEXT`` is its stable, indented rendering.
"""

from __future__ import annotations

import json

VERIFICATION_SYSTEM_PROMPT = (
    "You are a secure-code semantic verifier.\n"
    "Judge whether the target C/C++ function is truly vulnerable based ONLY on "
    "the provided function code and the structured static evidence. Do not "
    "invent facts that are not supported by the code or the evidence.\n"
    "Be conservative: only return verdict=\"vulnerable\" when the code and "
    "evidence together demonstrate a concrete, exploitable flaw.\n"
    "Return JSON only. Do not emit prose, markdown, or code fences.\n"
    "If the evidence is insufficient to decide, return verdict=\"uncertain\" "
    "and set need_more_context=true, listing what you would need in "
    "missing_context."
)

# The exact JSON object the model must return, described field-by-field so the
# contract is unambiguous inside the prompt.
RESPONSE_SCHEMA: dict = {
    "sample_id": "string, echo back the provided sample_id",
    "verdict": "one of: vulnerable | benign | uncertain",
    "confidence": "float in [0, 1]",
    "predicted_cwe": "string CWE id like CWE-416, or empty string if none",
    "vulnerable_lines": "array of positive integer line numbers (1-indexed)",
    "evidence": "array of objects describing supporting evidence",
    "need_more_context": "boolean",
    "missing_context": "array of strings naming missing context",
    "patch_hint": "short string suggesting a fix, or empty string",
}

REQUIRED_JSON_SCHEMA_TEXT = json.dumps(
    RESPONSE_SCHEMA, indent=2, ensure_ascii=False, sort_keys=False
)

# The verification user prompt is assembled from labeled sections. The builder
# fills these placeholders; keeping the layout here makes the contract visible.
VERIFICATION_USER_TEMPLATE = """\
sample_id: {sample_id}
language: {language}
function span: {span_file} lines {span_start}-{span_end} (1-indexed, inclusive)

Target function code:
```c
{function_code}
```

Static analysis alerts (JSON):
{alerts_json}

Structured static evidence (JSON):
{evidence_json}
{context_section}
Return JSON only, matching exactly this schema (no extra keys):
{schema_json}"""

JSON_REPAIR_SYSTEM_PROMPT = (
    "You are a JSON repair assistant for a secure-code verifier.\n"
    "You will be given a previous response that failed to parse or validate, "
    "and the error.\n"
    "Return a corrected JSON object ONLY -- no prose, no markdown, no code "
    "fences -- that conforms exactly to the required schema. Preserve the "
    "original judgement where possible; only fix structure, types, and missing "
    "or invalid fields."
)

JSON_REPAIR_USER_TEMPLATE = """\
The previous response for sample_id "{expected_sample_id}" was invalid.

Validation error:
{error_message}

Previous response:
{raw_response}

Return a corrected JSON object matching exactly this schema (no extra keys):
{schema_json}"""


__all__ = [
    "VERIFICATION_SYSTEM_PROMPT",
    "VERIFICATION_USER_TEMPLATE",
    "JSON_REPAIR_SYSTEM_PROMPT",
    "JSON_REPAIR_USER_TEMPLATE",
    "RESPONSE_SCHEMA",
    "REQUIRED_JSON_SCHEMA_TEXT",
]
