"""Phase 4 validation: verify FeatureRecord JSONL aligns with the manifest.

Checks per dataset: schema validity, sample_id alignment (1:1 with manifest),
label consistency, function_code availability, no missing sample_id. Writes
feature_build_report.md per dataset.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from semvulguard.schemas.features import FeatureRecord
from semvulguard.schemas.records import SampleRecord
from semvulguard.utils.jsonl import read_models

from scripts.experiments.formal.config import ROOT, SUBSET_TARGETS


def validate_one(ds: str) -> dict:
    ddir = ROOT / ds
    manifest = read_models(ddir / "manifest.jsonl", SampleRecord)
    features = read_models(ddir / "features.jsonl", FeatureRecord)

    m_ids = {s.sample_id for s in manifest}
    f_ids = [f.sample_id for f in features]
    f_id_set = set(f_ids)
    m_labels = {s.sample_id: s.label for s in manifest}

    checks: list[tuple[str, bool, str]] = []
    checks.append(("no duplicate feature ids", len(f_ids) == len(f_id_set),
                   f"{len(f_ids)} rows, {len(f_id_set)} unique"))
    checks.append(("1:1 manifest/feature alignment",
                   m_ids == f_id_set,
                   f"missing={len(m_ids - f_id_set)} extra={len(f_id_set - m_ids)}"))
    label_mismatch = sum(1 for f in features if m_labels.get(f.sample_id) != f.label)
    checks.append(("label consistency with manifest", label_mismatch == 0,
                   f"{label_mismatch} mismatches"))
    empty_code = sum(1 for f in features if not (f.function_code or "").strip())
    checks.append(("function_code present", empty_code == 0,
                   f"{empty_code} empty"))

    ok = all(c[1] for c in checks)
    labels = Counter(f.label for f in features)

    L = [f"# Feature Build Report — {ds}", "",
         f"- Records: **{len(features)}** (target subset {SUBSET_TARGETS[ds]})",
         f"- Label dist: benign(0)={labels.get(0,0)}, vulnerable(1)={labels.get(1,0)}",
         f"- Status: **{'ALL CHECKS PASSED' if ok else 'CHECKS FAILED'}**", "",
         "## Checks", ""]
    for name, passed, detail in checks:
        L.append(f"- {'PASS' if passed else 'FAIL'}: {name} ({detail})")
    L += ["", "## Notes", "",
          "- Features built without static alerts baked in (graph_node_count=0); "
          "CodeQL alert features are supplied separately to the ranker at train/infer "
          "time via static_alerts_codeql.jsonl (Phase 5/6).",
          "- No graph slices available (Joern not run); nodes/edges empty by design.", ""]
    (ddir / "feature_build_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"{ds}: {len(features)} features, {'OK' if ok else 'FAILED'}")
    return {"dataset": ds, "ok": ok, "n": len(features)}


def main(argv: list[str] | None = None) -> int:
    targets = argv if argv else list(SUBSET_TARGETS)
    results = [validate_one(ds) for ds in targets]
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:] or None))
