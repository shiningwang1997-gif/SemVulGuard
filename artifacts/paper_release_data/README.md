# SemVulGuard Paper Release Data Package

**Package Version**: 1.0  
**Date**: 2026-06-15  
**Paper**: SemVulGuard: Static-Analysis-Grounded Vulnerability Detection with Code Representation Learning and LLM-Based Semantic Verification

---

## Purpose

This package contains all experimental results and data supporting the SemVulGuard paper, prepared for reviewers and potential public release. The data has been sanitized to remove secrets, raw dataset code, and sensitive information while preserving scientific reproducibility.

---

## Directory Structure

```
paper_release_data/
├── README.md                          # This file
├── DATA_DICTIONARY.md                 # Column definitions and metrics
├── REPRODUCIBILITY.md                 # How to reproduce results
├── LICENSE_NOTE.md                    # License and attribution
├── checksums_sha256.txt              # File integrity checksums
│
├── tables/                           # Paper tables as CSV
│   ├── table1_dataset_statistics.csv
│   ├── table2_ranker_performance.csv
│   ├── table3_codeql_coverage.csv
│   ├── table4_deepseek_verdict_distribution.csv
│   ├── table6_calibrated_fusion_vs_ranker.csv
│   ├── table7_policy_comparison_summary.csv
│   └── table8_cost_analysis.csv
│
├── figures_data/                     # Figure data CSVs
│   ├── ranker_roc_pr_auc.csv
│   ├── codeql_coverage.csv
│   ├── cost_analysis.csv
│   ├── calibrated_fusion_delta.csv
│   ├── topk_precision_gain.csv
│   └── llm_verdict_distribution.csv
│
├── metrics/                          # Aggregated metrics
│   ├── ranker_metrics.csv
│   ├── codeql_coverage.csv
│   ├── llm_verdict_distribution.csv
│   ├── cost_summary.csv
│   └── research_question_summary.csv
│
├── per_dataset/                      # Per-dataset results
│   ├── devign/
│   │   ├── llm_topk_metrics.csv
│   │   └── llm_verdicts_top50_sanitized.csv
│   ├── bigvul/
│   │   ├── llm_topk_metrics.csv
│   │   └── llm_verdicts_top50_sanitized.csv
│   └── diversevul/
│       ├── llm_topk_metrics.csv
│       └── llm_verdicts_top50_sanitized.csv
│
├── llm_verification/                 # LLM verification results
│   ├── llm_verdicts_top50_all_sanitized.csv
│   ├── llm_cost_log_summary.csv
│   └── (llm_topk_metrics_all.csv - if available)
│
├── calibrated_fusion/                # Calibrated fusion analysis
│   ├── whole_corpus_metrics.csv
│   ├── topk_candidate_metrics.csv
│   ├── per_dataset_best_policies.csv
│   └── claim_boundary_after_calibration.md
│
└── scripts/                          # Verification scripts
    └── verify_release_data.py
```

---

## Quick Start

### Verify Package Integrity

```bash
python3 scripts/verify_release_data.py
```

This checks:
- All required files exist
- Corrected verdict distribution (devign: 14/23/13, bigvul: 8/33/9, diversevul: 7/31/12)
- Corrected policy count (1,533)
- No obvious secrets or API keys

### Explore Data

All data is in CSV format for easy inspection:

```bash
# View dataset statistics
cat tables/table1_dataset_statistics.csv

# View ranker performance
cat tables/table2_ranker_performance.csv

# View LLM verdict distribution
cat metrics/llm_verdict_distribution.csv
```

---

## Paper Table Mapping

| Table | File | Description |
|-------|------|-------------|
| Table 1 | `tables/table1_dataset_statistics.csv` | Dataset statistics and splits |
| Table 2 | `tables/table2_ranker_performance.csv` | Ranker test metrics |
| Table 3 | `tables/table3_codeql_coverage.csv` | CodeQL coverage |
| Table 4 | `tables/table4_deepseek_verdict_distribution.csv` | LLM verdict distribution |
| Table 5 | `figures_data/topk_precision_gain.csv` | Top-K verification |
| Table 6 | `tables/table6_calibrated_fusion_vs_ranker.csv` | Fusion performance |
| Table 7 | `tables/table7_policy_comparison_summary.csv` | Policy comparison |
| Table 8 | `tables/table8_cost_analysis.csv` | Cost analysis |

---

## Figure Data Mapping

| Figure | File | Description |
|--------|------|-------------|
| Figure 3 | `figures_data/ranker_roc_pr_auc.csv` | Ranker ROC-AUC/PR-AUC |
| Figure 4 | `figures_data/topk_precision_gain.csv` | Top-K precision gain |
| Figure 5 | `figures_data/llm_verdict_distribution.csv` | LLM verdicts |
| Figure 6 | `figures_data/codeql_coverage.csv` | CodeQL coverage |
| Figure 7 | `figures_data/cost_analysis.csv` | Cost breakdown |
| Figure 8 | `figures_data/calibrated_fusion_delta.csv` | Fusion improvements |

---

## Key Corrected Values

This package uses **corrected values** from the final consistency audit:

### LLM Verdict Distribution (CORRECTED)
- **Devign**: 14 vulnerable, 23 benign, 13 uncertain
- **BigVul**: 8 vulnerable, 33 benign, 9 uncertain
- **DiverseVul**: 7 vulnerable, 31 benign, 12 uncertain

### Policy Evaluations (CORRECTED)
- **Total policies evaluated**: 1,533

### Split Protocol (CORRECTED)
- **Method**: 70/10/20 stratified random split with seed 42
- **NOT chronological**

### Fusion Performance
- **Average F1 improvement**: +0.0020
- **Average MCC improvement**: +0.0025

---

## Data Sanitization

The following sanitization has been applied:

✅ **Included**:
- Sample IDs and dataset labels
- Rank scores and rankings
- Static alert counts and CWE/query IDs
- LLM verdicts, confidence, and predicted CWEs
- All metrics (precision, recall, F1, MCC, AUC)
- Cost logs (tokens, USD costs)
- Experimental metadata

❌ **Excluded**:
- Raw function code snippets
- Full LLM evidence text (may contain code)
- API keys and credentials
- Local absolute file paths
- Third-party dataset raw contents

---

## Dataset Attribution

This work uses the following publicly available datasets:

1. **Devign** - Zhou et al., "Devign: Effective Vulnerability Identification by Learning Comprehensive Program Semantics via Graph Neural Networks"
   - Original source: https://sites.google.com/view/devign

2. **BigVul** - Fan et al., "A C/C++ Code Vulnerability Dataset with Code Changes and CVE Summaries"
   - Original source: https://github.com/ZeoVan/MSR_20_Code_vulnerability_CSV_Dataset

3. **DiverseVul** - Chen et al., "DiverseVul: A New Vulnerable Source Code Dataset for Deep Learning Based Vulnerability Detection"
   - Original source: https://github.com/wagner-group/diversevul

**Important**: Raw dataset files are NOT included in this package. Users should download the original datasets from their official sources and cite the original papers.

---

## Scientific Integrity

This package demonstrates scientific honesty:

✅ **Negative results reported**: Devign shows negative LLM gains at top-30 (-0.20) and top-50 (-0.07)  
✅ **Minimal fusion gains acknowledged**: Average F1 +0.002, MCC +0.003  
✅ **Sparse CodeQL coverage documented**: 0.5-1.3% test coverage  
✅ **Dataset-dependent effectiveness**: LLM helps BigVul/DiverseVul, mixed on Devign  
✅ **Limitations transparent**: Validation set exists but not used for LLM experiments

---

## Citation

If you use this data in your research, please cite:

```bibtex
@article{semvulguard2026,
  title={SemVulGuard: Static-Analysis-Grounded Vulnerability Detection with Code Representation Learning and LLM-Based Semantic Verification},
  author={[Authors]},
  journal={[Venue]},
  year={2026}
}
```

---

## Contact

For questions about this data package:
- See `REPRODUCIBILITY.md` for technical details
- See `DATA_DICTIONARY.md` for column definitions
- See `LICENSE_NOTE.md` for licensing information

---

## Package Statistics

- **CSV files**: 29
- **Documentation files**: 4 (README, DATA_DICTIONARY, REPRODUCIBILITY, LICENSE_NOTE)
- **Scripts**: 1 (verify_release_data.py)
- **Total test samples**: 3,000 (1,000 per dataset)
- **LLM verdicts**: 150 (50 per dataset)
- **Total experimental cost**: $0.125 USD

---

## Verification

To verify package integrity:

```bash
# Run verification script
python3 scripts/verify_release_data.py

# Check SHA256 checksums
sha256sum -c checksums_sha256.txt
```

Expected output: All checks pass, no secrets detected.

---

**Package Status**: ✅ Ready for reviewer sharing  
**Last Updated**: 2026-06-15  
**Package Version**: 1.0
