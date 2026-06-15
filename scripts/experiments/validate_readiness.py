"""Phase 4: validate dataset readiness and emit dataset_readiness_report.md.

Checks per ready dataset:
  1. every manifest record validates against SampleRecord;
  2. sample_id values are unique;
  3. label distribution is non-empty (both classes present is noted);
  4. function code is locatable in the per-sample code dir;
  5. enough samples to run a small experiment.

Writes ``artifacts/experiments/dataset_readiness_report.md``.
Exit code is non-zero only if NO dataset is ready.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from semvulguard.schemas.records import SampleRecord
from semvulguard.utils.jsonl import read_jsonl

EXP = Path("artifacts/experiments")
DATASETS = ["devign", "bigvul", "diversevul"]
MIN_SAMPLES = 20


def validate(dataset: str) -> dict:
    ddir = EXP / dataset
    manifest = ddir / "manifest.jsonl"
    res: dict = {"dataset": dataset, "ready": False, "reasons": [], "info": {}}

    if not manifest.exists():
        err = ddir / "normalization_error.md"
        res["reasons"].append(
            f"no manifest.jsonl (excluded; see {err.name})"
            if err.exists() else "no manifest.jsonl"
        )
        return res

    rows = list(read_jsonl(manifest))
    # schema validation
    bad = 0
    labels: list[int] = []
    ids: list[str] = []
    for row in rows:
        try:
            rec = SampleRecord.model_validate(row)
            labels.append(rec.label)
            ids.append(rec.sample_id)
        except Exception:
            bad += 1
    res["info"]["count"] = len(rows)
    res["info"]["schema_invalid"] = bad
    res["info"]["unique_ids"] = len(set(ids))
    res["info"]["label_dist"] = dict(Counter(labels))
    res["info"]["cwe_present"] = any(
        SampleRecord.model_validate(r).cwe for r in rows
    )

    # code locatable
    code_dir = ddir / "code"
    located = 0
    if code_dir.exists():
        for sid in ids:
            if (code_dir / f"{sid}.c").exists():
                located += 1
    res["info"]["code_located"] = located

    # decide readiness
    ok = True
    if bad:
        res["reasons"].append(f"{bad} records fail SampleRecord schema")
        ok = False
    if len(set(ids)) != len(ids):
        res["reasons"].append("sample_id values are not unique")
        ok = False
    if not labels:
        res["reasons"].append("empty label distribution")
        ok = False
    pos = sum(labels)
    if pos == 0 or pos == len(labels):
        res["reasons"].append(
            f"single-class labels (pos={pos}, neg={len(labels)-pos}); "
            "classification metrics will be degenerate"
        )
        # single-class is a serious caveat but we still allow ranking; mark not ready
        ok = False
    if located < len(ids):
        res["reasons"].append(
            f"only {located}/{len(ids)} function bodies located in code/"
        )
        if located == 0:
            ok = False
    if len(rows) < MIN_SAMPLES:
        res["reasons"].append(f"too few samples ({len(rows)} < {MIN_SAMPLES})")
        ok = False

    res["ready"] = ok
    if ok and not res["reasons"]:
        res["reasons"].append("all checks passed")
    return res


def main() -> int:
    results = [validate(d) for d in DATASETS]
    ready = [r for r in results if r["ready"]]

    lines = ["# Dataset Readiness Report", ""]
    lines.append(f"- Datasets inspected: {', '.join(DATASETS)}")
    lines.append(f"- **Ready for experiment: {', '.join(r['dataset'] for r in ready) or 'NONE'}**")
    lines.append("")

    for r in results:
        lines.append(f"## {r['dataset']}")
        lines.append("")
        status = "READY ✅" if r["ready"] else "NOT READY / EXCLUDED ❌"
        lines.append(f"- Status: **{status}**")
        info = r["info"]
        if info:
            lines.append(f"- Sample count: {info.get('count')}")
            lines.append(f"- Unique sample_ids: {info.get('unique_ids')}")
            lines.append(f"- Schema-invalid records: {info.get('schema_invalid')}")
            ld = info.get("label_dist", {})
            lines.append(
                f"- Label distribution: benign(0)={ld.get(0,0)}, "
                f"vulnerable(1)={ld.get(1,0)}"
            )
            lines.append(f"- CWE labels present: {info.get('cwe_present')}")
            lines.append(
                f"- Function bodies located: {info.get('code_located')}/{info.get('count')}"
            )
        lines.append("- Notes:")
        for reason in r["reasons"]:
            lines.append(f"  - {reason}")
        lines.append("")

    if not ready:
        lines.append("## Conclusion")
        lines.append("")
        lines.append("**No dataset is ready. Experiments cannot proceed.**")

    report = EXP / "dataset_readiness_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {report}")
    for r in results:
        print(f"  {r['dataset']}: {'READY' if r['ready'] else 'not ready'} "
              f"-- {'; '.join(r['reasons'])}")

    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
