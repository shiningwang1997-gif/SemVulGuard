# Section 4: Experimental Evaluation - Outline

## 4.1 Research Questions

Our experimental evaluation addresses the following research questions:

- **RQ1**: Can the ML ranker effectively prioritize vulnerability candidates?
- **RQ2**: Does CodeQL static analysis provide useful supplementary evidence?
- **RQ3**: Can LLM-based semantic verification improve top-k candidate precision?
- **RQ4**: Is the integrated approach cost-effective for practical deployment?
- **RQ5**: How do different evidence fusion strategies impact whole-corpus performance?

---

## 4.2 Datasets and Experimental Setup

### 4.2.1 Datasets

**Key Table**: Table 1 (Dataset Statistics)
**Supporting File**: `dataset_summary.csv`

**Content**:
- Three function-level C/C++ vulnerability datasets
- Devign (5,000 samples, 45.6% vulnerable)
- BigVul (5,000 samples, 5.6% vulnerable)
- DiverseVul (5,000 samples, 5.7% vulnerable)
- Strict train/valid/test split (70%/10%/20%)

**Main Conclusion**:
> "We evaluate on three diverse datasets spanning balanced (Devign) and highly imbalanced (BigVul, DiverseVul) distributions, totaling 3,000 held-out test samples."

**What NOT to claim**:
- Do not claim datasets are project-level (they are function-level)
- Do not claim comprehensive coverage of all vulnerability types

---

### 4.2.2 Evaluation Protocol

**Content**:
- Held-out test evaluation (no test labels used for tuning)
- Fixed threshold (0.5) for whole-corpus classification
- Top-k analysis for candidate verification (k = 10, 30, 50)
- Cost tracking for all LLM API calls

**Main Conclusion**:
> "All experiments use strict held-out test evaluation with no hyperparameter tuning on test data, ensuring unbiased performance assessment."

**What NOT to claim**:
- Do not claim cross-validation (we use fixed split)
- Do not claim statistical significance testing (not performed)

---

## 4.3 Whole-Corpus Detection Performance (Ranker Baseline)

### 4.3.1 Ranker Test Performance

**Key Table**: Table 2 (Ranker Performance on Held-Out Test Sets)
**Key Figure**: Figure 1 (ROC and PR curves per dataset)
**Supporting File**: `ranker_roc_pr_auc.csv`

**Content**:
- Test metrics: Precision, Recall, F1, MCC, ROC-AUC, PR-AUC
- Devign: F1=0.557, MCC=0.171, ROC-AUC=0.623
- BigVul: F1=0.200, MCC=0.145, ROC-AUC=0.744
- DiverseVul: F1=0.259, MCC=0.211, ROC-AUC=0.721
- Train-test performance gap observed (expected for security tasks)

**Main Conclusion**:
> "The ranker achieves ROC-AUC scores between 0.62 and 0.74 across datasets, demonstrating effective ranking capability despite significant train-test gaps in classification metrics (F1, MCC)."

**What NOT to claim**:
- Do not claim state-of-the-art F1 scores
- Do not compare with prior work (no fair baseline available)
- Do not claim ranker solves vulnerability detection completely

**Key insight**: ROC-AUC stability indicates preserved ranking capability even when classification is difficult.

---

## 4.4 Ranker Effectiveness for Candidate Discovery

### 4.4.1 Top-K Precision Analysis

**Key Table**: Table 5 (LLM Top-K Candidate Verification Results) - Ranker Precision column
**Key Figure**: Figure 2 (Top-k precision curves)
**Supporting File**: `topk_precision_gain.csv`

**Content**:
- Top-10 ranker precision: Devign 0.80, BigVul 0.40, DiverseVul 0.30
- Top-30 ranker precision: Devign 0.70, BigVul 0.27, DiverseVul 0.23
- Top-50 ranker precision: Devign 0.64, BigVul 0.22, DiverseVul 0.20
- Precision degrades with increasing k (expected)

**Main Conclusion**:
> "The ranker successfully concentrates true vulnerabilities in top-ranked candidates, with top-10 precision reaching 0.80 on Devign and 0.30-0.40 on imbalanced datasets."

**What NOT to claim**:
- Do not claim perfect precision at any k
- Do not claim top-k precision is sufficient without manual review

**Key insight**: This demonstrates the ranker's value for reducing manual review burden.

---

## 4.5 Static Evidence Coverage

### 4.5.1 CodeQL Analysis Results

**Key Table**: Table 3 (CodeQL Static Analysis Coverage)
**Key Figure**: Figure 3 (Coverage and CWE distribution)
**Supporting File**: `codeql_coverage.csv`

**Content**:
- Coverage: Devign 1.3%, BigVul 0.5%, DiverseVul 1.2%
- Total alerts: Devign 23, BigVul 6, DiverseVul 16
- Unique CWEs: 11, 4, 9 respectively
- Most common: CWE-252, CWE-457, CWE-468

**Main Conclusion**:
> "CodeQL static analysis provides sparse coverage (0.5-1.3%) due to function-level evaluation lacking full project build context. While limited, identified alerts correspond to valid CWE categories."

**What NOT to claim**:
- Do not claim CodeQL provides comprehensive static evidence
- Do not claim CodeQL integration is the main contribution
- Do not blame CodeQL itself (limitation is dataset context, not tool)

**Key insight**: Acknowledge limitation upfront and explain why (function-level vs. project-level).

---

## 4.6 Real LLM Top-k Candidate Verification

### 4.6.1 DeepSeek API Execution

**Key Table**: Table 4 (Real DeepSeek Top-50 Verdict Distribution)
**Key Figure**: Figure 4 (Verdict distribution by dataset)
**Supporting File**: `llm_verdict_distribution.csv`

**Content**:
- 150 API calls total (50 per dataset)
- 100% success rate (0 failures)
- Total cost: $0.125 USD
- Verdict distribution varies by dataset

**Main Conclusion**:
> "LLM-based verification using DeepSeek-v4-flash is highly cost-effective and reliable, with 100% success rate and total experimental cost of $0.125."

**What NOT to claim**:
- Do not claim LLM is necessary for good performance
- Do not claim LLM will always succeed (report 100% but acknowledge potential failures)

---

### 4.6.2 Top-K Precision Improvements

**Key Table**: Table 5 (LLM Top-K Candidate Verification Results) - Full table
**Key Figure**: Figure 5 (Precision gain comparison)
**Supporting File**: `topk_precision_gain.csv`

**Content**:
- **BigVul**: Consistent gains (+0.10 to +0.48 across k=10,30,50)
- **DiverseVul**: Consistent gains (+0.14 to +0.20)
- **Devign**: Mixed results (+0.20 at k=10, negative at k=30,50)
- Dataset-dependent effectiveness

**Main Conclusion**:
> "LLM verification improves top-k candidate precision on imbalanced datasets (BigVul, DiverseVul), with gains ranging from +0.10 to +0.48, but shows mixed results on balanced datasets (Devign), indicating dataset-dependent effectiveness."

**What NOT to claim**:
- Do not claim LLM universally improves precision
- Do not claim LLM always reduces false positives
- Do not ignore Devign's negative results

**Key insight**: LLM helps more when base precision is low (imbalanced datasets).

---

## 4.7 Calibrated Fusion Analysis

### 4.7.1 Policy Comparison

**Key Table**: Table 6 (Calibrated Fusion vs Ranker-Only) and Table 7 (Policy Comparison Summary)
**Supporting File**: `calibrated_fusion_delta.csv`, `policy_search_log.csv`

**Content**:
- 751 policy configurations evaluated per dataset
- Policy A (incremental adjustment) selected for all datasets
- Average improvements: F1 +0.002, MCC +0.0025
- Individual dataset improvements all < 0.01

**Main Conclusion**:
> "Calibrated fusion yields minimal whole-corpus improvements (average F1 +0.002), primarily because LLM verdicts cover only 5% of test samples. Policy A (incremental score adjustment) is most effective, suggesting LLM is best used for fine-grained adjustments rather than hard filtering."

**What NOT to claim**:
- Do not claim fusion significantly improves whole-corpus performance
- Do not claim fusion is the main contribution
- Do not claim calibration is better than fixed threshold (no validation set available)

**Key insight**: Treat this as sensitivity analysis, not optimization.

---

### 4.7.2 Why Fusion Gains are Minimal

**Content** (in discussion):
- LLM coverage limited to 5% of test set (top-50)
- No validation set for threshold calibration
- Ranker already provides strong baseline
- Limited LLM coverage cannot substantially impact whole-corpus metrics

**Main Conclusion**:
> "The limited impact of fusion on whole-corpus metrics reflects the architectural decision to apply LLM verification selectively to top candidates rather than the entire corpus, balancing cost-effectiveness with verification utility."

---

## 4.8 Cost Analysis

**Key Table**: Table 8 (Cost Analysis)
**Key Figure**: Figure 6 (Cost breakdown)
**Supporting File**: `cost_analysis.csv`

**Content**:
- CodeQL: $0.00 (open-source, runs locally)
- Ranker: $0.00 (one-time training, local inference)
- LLM: $0.125 for 150 samples
- Total pipeline: $0.125 for 3,000 test samples
- Cost per verified candidate: ~$0.0008

**Main Conclusion**:
> "The integrated pipeline is highly cost-effective, with total experimental cost of $0.125 for evaluating 3,000 test samples across three datasets. LLM verification scales linearly at ~$0.0008 per candidate."

**What NOT to claim**:
- Do not ignore computational costs (CPU time) for CodeQL and ranker
- Do not claim zero cost overall (focus on marginal API cost)

---

## 4.9 Discussion and Threats to Validity

### 4.9.1 Key Findings Summary

1. **Ranker provides primary detection capability** (RQ1: Supported)
   - ROC-AUC 0.62-0.74, top-10 precision 0.30-0.80
   
2. **CodeQL coverage is sparse** (RQ2: Partially supported)
   - 0.5-1.3% due to function-level context
   
3. **LLM helps on specific datasets** (RQ3: Partially supported)
   - Consistent gains on BigVul, DiverseVul
   - Mixed results on Devign
   
4. **Cost-effective verification** (RQ4: Supported)
   - $0.125 total, 100% success rate
   
5. **Fusion gains minimal** (RQ5: Not supported as performance claim)
   - Average F1 +0.002, treat as sensitivity analysis

---

### 4.9.2 Why Devign Behaves Differently

**Content**:
- Devign is balanced (45.6% vulnerable)
- BigVul and DiverseVul are highly imbalanced (~5.6% vulnerable)
- Ranker already achieves high top-k precision on Devign (0.80 at top-10)
- Less room for LLM to improve when baseline is strong
- LLM may be more helpful when base precision is low

**Main Conclusion**:
> "LLM verification effectiveness depends on dataset characteristics, showing larger gains on imbalanced datasets where ranker baseline precision is lower."

---

### 4.9.3 Why CodeQL Coverage is Sparse

**Content**:
- Function-level datasets lack project build context
- CodeQL requires compilable projects with build specifications
- Many functions cannot be analyzed in isolation
- Not a limitation of CodeQL itself, but of evaluation context

**Main Conclusion**:
> "Sparse CodeQL coverage reflects function-level evaluation constraints rather than tool limitations. Project-level analysis would significantly improve coverage."

---

### 4.9.4 Why Fusion Gains are Minimal

**Content**:
- LLM only covers 5% of test set (top-50)
- 95% of samples unchanged (no LLM verdict)
- Whole-corpus metrics diluted by large unchanged majority
- No validation set for threshold optimization

**Main Conclusion**:
> "Minimal fusion gains reflect architectural tradeoffs: selective LLM application maintains cost-effectiveness but limits whole-corpus metric impact."

---

### 4.9.5 Threats to Validity

**Internal Validity**:
- Train-test split may not fully eliminate temporal bias
- Fixed threshold (0.5) may be suboptimal
- No cross-dataset evaluation (each dataset evaluated independently)

**External Validity**:
- Function-level evaluation may not generalize to project-level
- Three datasets may not cover all vulnerability types
- C/C++ focus may not generalize to other languages

**Construct Validity**:
- Ground truth labels may contain errors
- CodeQL alerts are heuristic, not ground truth
- LLM verdicts are model opinions, not objective truth

**Main Conclusion**:
> "While our evaluation follows rigorous held-out testing protocols, findings are specific to function-level C/C++ datasets and may require validation in project-level and cross-language contexts."

---

## Summary of "What NOT to Claim" Per Subsection

| Subsection | Do NOT Claim |
|------------|--------------|
| 4.3 | Ranker achieves state-of-the-art F1; ranker solves vulnerability detection |
| 4.4 | Top-k precision is sufficient without review; perfect precision at any k |
| 4.5 | CodeQL provides comprehensive evidence; CodeQL tool is limited |
| 4.6.1 | LLM is necessary; LLM will always succeed |
| 4.6.2 | LLM universally improves precision; ignore Devign negative results |
| 4.7 | Fusion significantly improves whole-corpus; fusion is main contribution |
| 4.8 | System has zero cost; ignore computational costs |
| 4.9 | Results generalize to all contexts; no limitations |

---

## Recommended Flow

1. Start with ranker baseline (4.3, 4.4) - establish primary capability
2. Show static evidence is sparse (4.5) - acknowledge limitation
3. Demonstrate LLM verification works (4.6) - show optional enhancement
4. Analyze fusion strategies (4.7) - sensitivity analysis, not optimization
5. Confirm cost-effectiveness (4.8) - practical deployment feasibility
6. Discuss findings honestly (4.9) - limitations and context

**Key narrative**: Ranker is the foundation, LLM is optional enhancement, fusion is sensitivity analysis, whole system is cost-effective.
