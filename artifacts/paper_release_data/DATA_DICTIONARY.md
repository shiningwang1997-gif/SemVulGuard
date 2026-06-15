# Data Dictionary - SemVulGuard Paper Release Package

**Version**: 1.0  
**Date**: 2026-06-15

---

## Overview

This document defines all columns, metrics, and terminology used in the SemVulGuard paper release data package.

---

## Common Columns

### Identifiers
- **`Dataset`**: Dataset name (devign, bigvul, diversevul)
- **`sample_id`**: Unique sample identifier (format: `{dataset}_{id}`)
- **`split`**: Data split (train, valid, test)
- **`label`**: Ground truth label (0=benign, 1=vulnerable)

### Scores and Rankings
- **`rank_score`**: ML ranker score (0-1, higher = more likely vulnerable)
- **`rank`**: Sample rank by score (1 = highest score)

### LLM Verdicts
- **`verdict`**: LLM verdict (vulnerable, benign, uncertain)
- **`confidence`**: LLM confidence score (0-1)
- **`predicted_cwe`**: CWE ID predicted by LLM (e.g., "CWE-125")
- **`need_more_context`**: Boolean indicating if LLM needs more context

### Static Analysis
- **`alert_count`**: Number of CodeQL alerts for this sample
- **`cwe_ids`**: Comma-separated CWE IDs from static analysis
- **`query_ids`**: Comma-separated CodeQL query IDs

---

## Metrics Definitions

### Classification Metrics

**Precision** = TP / (TP + FP)
- Of samples predicted as vulnerable, what fraction are truly vulnerable?
- Range: [0, 1], higher is better

**Recall** = TP / (TP + FN)
- Of truly vulnerable samples, what fraction are detected?
- Range: [0, 1], higher is better

**F1** = 2 × (Precision × Recall) / (Precision + Recall)
- Harmonic mean of precision and recall
- Range: [0, 1], higher is better

**MCC (Matthews Correlation Coefficient)** = (TP×TN - FP×FN) / sqrt((TP+FP)(TP+FN)(TN+FP)(TN+FN))
- Balanced metric considering all confusion matrix entries
- Range: [-1, 1], higher is better, 0 = random

### Ranking Metrics

**ROC-AUC (Receiver Operating Characteristic - Area Under Curve)**
- Probability that ranker scores a random vulnerable sample higher than a random benign sample
- Range: [0, 1], 0.5 = random, 1.0 = perfect

**PR-AUC (Precision-Recall - Area Under Curve)**
- Area under precision-recall curve
- More informative for imbalanced datasets
- Range: [0, 1], higher is better

### LLM Verification Metrics

**Ranker Top-K Precision**
- Ground truth precision of top-k samples ranked by ranker score
- Measures: Of top-k ranked samples, what fraction are truly vulnerable?

**LLM Filtered Precision**
- Precision of samples where LLM verdict = "vulnerable"
- Measures: Of samples LLM calls vulnerable, what fraction are truly vulnerable?

**Precision Gain**
- LLM Filtered Precision - Ranker Top-K Precision
- Positive gain = LLM improves precision
- Negative gain = LLM hurts precision

**Vulnerable Verdict Precision**
- Precision specifically for "vulnerable" verdicts
- Same as LLM Filtered Precision in most contexts

**Benign Verdict Precision**
- Precision for "benign" verdicts (inverted: fraction that are truly benign)

**Uncertain Rate**
- Fraction of samples where LLM returns "uncertain"
- Indicates how often LLM cannot make a confident judgment

---

## CSV File Descriptions

### tables/table1_dataset_statistics.csv

Columns:
- `Dataset`: Dataset name
- `Total_Samples`: Total samples in subset
- `Train`: Training set size
- `Valid`: Validation set size
- `Test`: Test set size
- `Vulnerable_Percent_Test`: Percentage of vulnerable samples in test set
- `Source`: Dataset source description

---

### tables/table2_ranker_performance.csv

Ranker performance on held-out test sets.

Columns:
- `Dataset`: Dataset name
- `Precision`: Test precision at threshold 0.5
- `Recall`: Test recall at threshold 0.5
- `F1`: Test F1 score
- `MCC`: Matthew's Correlation Coefficient
- `ROC_AUC`: Area under ROC curve
- `PR_AUC`: Area under precision-recall curve

---

### tables/table3_codeql_coverage.csv

CodeQL static analysis coverage.

Columns:
- `Dataset`: Dataset name
- `Test_Samples`: Number of test samples
- `Alerts_Parsed`: Total CodeQL alerts mapped
- `Samples_w_Alerts`: Number of samples with ≥1 alert
- `Coverage_Percent`: Percentage of samples with alerts
- `Unique_CWEs`: Number of unique CWE types
- `Unique_Query_IDs`: Number of unique CodeQL queries triggered

**Note**: Shows total alerts; test-only alerts are 5 (Devign), 1 (BigVul), 1 (DiverseVul)

---

### tables/table4_deepseek_verdict_distribution.csv

LLM verdict distribution (CORRECTED VALUES).

Columns:
- `Dataset`: Dataset name
- `API_Calls`: Number of LLM API calls
- `Vulnerable`: Number of "vulnerable" verdicts
- `Benign`: Number of "benign" verdicts
- `Uncertain`: Number of "uncertain" verdicts
- `Success_Rate`: API success rate (100% for all)
- `Cost_USD`: Total API cost in USD

**Critical**: Uses corrected values from JSONL recount:
- Devign: 14/23/13
- BigVul: 8/33/9
- DiverseVul: 7/31/12

---

### tables/table6_calibrated_fusion_vs_ranker.csv

Calibrated fusion performance vs ranker-only baseline.

Columns:
- `Dataset`: Dataset name
- `Best_Policy`: Best policy identified
- `Best_F1`: F1 score of best policy
- `Ranker_F1`: F1 score of ranker-only
- `F1_Delta`: F1 improvement (Best - Ranker)
- `Best_MCC`: MCC of best policy
- `Ranker_MCC`: MCC of ranker-only
- `MCC_Delta`: MCC improvement (Best - Ranker)

**Key Finding**: Minimal improvements (average F1 +0.002)

---

### tables/table7_policy_comparison_summary.csv

Policy evaluation summary.

Columns:
- `Policy`: Policy identifier
- `Description`: Policy description
- `Grid_Size`: Number of configurations in this policy family
- `Selected_Count`: Number of datasets selecting this policy

**Critical**: Total = 1,533 policies evaluated (corrected)

---

### tables/table8_cost_analysis.csv

Cost breakdown for experimental pipeline.

Columns:
- `Component`: Pipeline component
- `Operation`: Operation description
- `Samples`: Number of samples processed
- `Cost_per_Sample_USD`: Cost per sample
- `Total_Cost_USD`: Total cost in USD
- `Time_Minutes`: Execution time in minutes

**Note**: Monetary costs are marginal API costs only; computational costs (CPU, memory) excluded

---

### figures_data/ranker_roc_pr_auc.csv

Ranker ROC-AUC and PR-AUC values.

Columns: Same as table2_ranker_performance.csv

---

### figures_data/topk_precision_gain.csv

Top-K precision gain from LLM verification.

Columns:
- `dataset`: Dataset name
- `k`: Top-K value (10, 30, 50)
- `ranker_precision`: Ground truth precision of top-k by ranker
- `llm_filtered_precision`: Precision of LLM "vulnerable" verdicts
- `precision_gain`: LLM - Ranker precision

---

### figures_data/llm_verdict_distribution.csv

LLM verdict distribution (CORRECTED).

Columns:
- `dataset`: Dataset name
- `verdict_type`: Verdict type (vulnerable, benign, uncertain)
- `count`: Number of samples with this verdict
- `percentage`: Percentage of samples

---

### per_dataset/{dataset}/llm_verdicts_top50_sanitized.csv

Sanitized LLM verdicts for top-50 samples.

Columns:
- `sample_id`: Sample identifier
- `verdict`: LLM verdict
- `confidence`: Confidence score
- `predicted_cwe`: Predicted CWE ID
- `need_more_context`: Boolean

**Sanitization**: Raw code and evidence text removed

---

### per_dataset/{dataset}/llm_topk_metrics.csv

LLM top-k verification metrics per dataset.

Columns:
- `dataset`: Dataset name
- `k`: Top-K value
- `uncertain_setting`: How uncertain verdicts are handled
- `candidate_count`: Number of candidates considered
- `positives_in_topk`: Ground truth positives in top-k
- `vulnerable_verdict_count`: Number of "vulnerable" verdicts
- `benign_verdict_count`: Number of "benign" verdicts
- `uncertain_count`: Number of "uncertain" verdicts
- `uncertain_rate`: Fraction of uncertain verdicts
- `precision`: Overall precision
- `recall`: Overall recall
- `f1`: F1 score
- `accuracy`: Accuracy
- `mcc`: Matthews Correlation Coefficient
- `tp`, `fp`, `tn`, `fn`: Confusion matrix entries
- `vulnerable_verdict_precision`: Precision of "vulnerable" verdicts
- `benign_verdict_precision`: Precision of "benign" verdicts
- `ranker_topk_precision`: Ranker precision at top-k
- `llm_filtered_precision`: LLM filtered precision
- `precision_gain_over_ranker_topk`: Precision improvement

---

### metrics/ranker_metrics.csv

Aggregated ranker metrics across datasets.

Columns: Same as table2_ranker_performance.csv

---

### metrics/llm_verdict_distribution.csv

Aggregated LLM verdict distribution (CORRECTED).

Columns: Same as table4_deepseek_verdict_distribution.csv

---

### metrics/cost_summary.csv

Cost summary across pipeline components.

Columns:
- `Component`: Component name
- `Samples`: Samples processed
- `Cost_USD`: Total cost
- `Time_Minutes`: Execution time

---

### metrics/research_question_summary.csv

Support level for each research question.

Columns:
- `RQ`: Research question identifier
- `Question`: Question text
- `Support_Level`: Supported / Partial / Not supported
- `Primary_Evidence`: Primary evidence tables/figures

---

### llm_verification/llm_verdicts_top50_all_sanitized.csv

All LLM verdicts across datasets.

Columns:
- `dataset`: Dataset name
- `sample_id`: Sample identifier
- `verdict`: LLM verdict
- `confidence`: Confidence score
- `predicted_cwe`: Predicted CWE
- `need_more_context`: Boolean

Total: 150 verdicts (50 per dataset)

---

### llm_verification/llm_cost_log_summary.csv

LLM API cost summary.

Columns:
- `Dataset`: Dataset name
- `API_Calls`: Number of calls
- `Successful`: Successful calls
- `Failed`: Failed calls
- `Cost_USD`: Total cost

---

### calibrated_fusion/whole_corpus_metrics.csv

Whole-corpus metrics for fusion policies.

Columns:
- `policy`: Policy identifier
- `f1`, `mcc`, `precision`, `recall`: Metrics
- `tp`, `fp`, `tn`, `fn`: Confusion matrix
- `dataset`: Dataset name

---

### calibrated_fusion/per_dataset_best_policies.csv

Best policy selected per dataset.

Columns:
- `dataset`: Dataset name
- `best_policy`: Policy identifier
- `best_f1`: F1 of best policy
- `best_mcc`: MCC of best policy
- `ranker_only_f1`: Ranker-only F1
- `ranker_only_mcc`: Ranker-only MCC
- `f1_improvement`: F1 delta
- `mcc_improvement`: MCC delta

---

## Terminology

**Ranker**: ML-based vulnerability detection model (TF-IDF + code features)

**Static Analysis**: CodeQL queries run on isolated function code

**LLM Verification**: DeepSeek-v4-flash semantic verification of top-k candidates

**Top-K**: Highest-ranked k samples by ranker score

**Calibrated Fusion**: Policy-based combination of ranker, static, and LLM scores

**Policy A**: Ranker-preserving incremental LLM adjustment

**Test-Only Evaluation**: All metrics computed on held-out test sets, no test-set tuning

**Stratified Split**: 70/10/20 train/valid/test split preserving label distribution, seed 42

---

## Missing or Excluded Data

**Not Included**:
- Raw function code (dataset licensing)
- Full LLM evidence text (may contain code)
- LLM prompts (may contain code)
- API keys and credentials
- Raw JSONL files with full context

**Reason**: Privacy, licensing, and sanitization requirements

---

**For questions about specific columns or metrics, refer to the SemVulGuard paper or contact the authors.**

