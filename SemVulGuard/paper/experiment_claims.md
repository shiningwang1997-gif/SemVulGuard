# Experiment Claims: Evidence-Based Assessment

## SUPPORTED CLAIMS ✅

### 1. Ranker Provides Effective Candidate Prioritization
**Evidence**: 
- Ranker achieves ROC-AUC of 0.62-0.74 across datasets (Table 2)
- Top-10 ranker precision: Devign 0.80, BigVul 0.40, DiverseVul 0.30 (Table 5)
- Meaningful separation of vulnerable and benign code

**How to phrase**:
> "Our ranker effectively prioritizes vulnerability candidates, achieving ROC-AUC scores between 0.62 and 0.74 across three datasets, with top-10 precision ranging from 0.30 to 0.80."

**Supports**: RQ1 (Can ranker prioritize vulnerabilities?)

---

### 2. Real DeepSeek API Verification is Cost-Effective
**Evidence**:
- Total cost: $0.125 for 150 samples across 3 datasets (Table 4)
- 100% success rate (0 failures)
- ~$0.0008 per candidate verification

**How to phrase**:
> "LLM-based verification using DeepSeek-v4-flash is highly cost-effective, with a total experimental cost of $0.125 for verifying 150 top-ranked candidates (100% success rate)."

**Supports**: RQ4 (Cost-effectiveness)

---

### 3. LLM Top-K Verification Improves Candidate Precision on BigVul and DiverseVul
**Evidence**:
- BigVul: precision gains of +0.10, +0.48, +0.28 at top-10/30/50 (Table 5)
- DiverseVul: precision gains of +0.20, +0.14, +0.20 at top-10/30/50 (Table 5)
- Consistent positive improvements on imbalanced datasets

**How to phrase**:
> "For imbalanced datasets (BigVul, DiverseVul), LLM verification consistently improves top-k candidate precision, with gains ranging from +0.10 to +0.48 depending on k."

**Supports**: RQ3 (LLM candidate verification effectiveness)

---

### 4. Modular Architecture Enables Flexible Deployment
**Evidence**:
- CodeQL runs independently (sparse evidence layer)
- Ranker operates without LLM (standalone baseline)
- LLM verification optional (applied only to top-k)
- Each component can be deployed separately

**How to phrase**:
> "SemVulGuard's modular architecture allows flexible deployment: the ranker provides baseline detection, with optional CodeQL static evidence and LLM verification for high-priority candidates."

**Supports**: System design goals

---

### 5. Static Analysis Coverage is Sparse but Valid
**Evidence**:
- Coverage: 0.5-1.3% of test samples (Table 3)
- When alerts exist, they correspond to valid CWE categories
- Function-level datasets lack full project build context

**How to phrase**:
> "CodeQL static analysis provides sparse but valid evidence (0.5-1.3% coverage), limited by function-level datasets lacking full project compilation context."

**Supports**: RQ2 (Static evidence utility) - with strong caveats

---

## PARTIALLY SUPPORTED CLAIMS ⚠️

### 1. LLM Helps with Candidate Verification (Dataset-Dependent)
**Evidence**:
- **Positive**: BigVul (+0.28 to +0.48), DiverseVul (+0.14 to +0.20)
- **Mixed**: Devign (+0.20 at top-10, but -0.07 to -0.20 at top-30/50)
- Not universally beneficial

**How to phrase**:
> "LLM verification improves candidate precision on imbalanced datasets (BigVul, DiverseVul) but shows mixed results on balanced datasets (Devign), suggesting effectiveness depends on dataset characteristics."

**Limitation**: Must acknowledge dataset-dependent behavior

**Supports**: RQ3 - with caveats

---

### 2. Calibrated Fusion Provides Modest Improvements
**Evidence**:
- Average F1 improvement: +0.0020 (essentially zero)
- Average MCC improvement: +0.0025 (essentially zero)
- BigVul shows largest gain: +0.0044 F1, +0.0058 MCC (Table 6)

**How to phrase**:
> "Calibrated fusion yields minimal whole-corpus improvements (average F1 +0.002), primarily because LLM verdicts cover only 5% of test samples."

**Limitation**: Cannot claim significant whole-corpus improvement

**Supports**: Sensitivity analysis only (not main performance claim)

---

### 3. CodeQL-Ranker-LLM Pipeline is Functional
**Evidence**:
- All three components successfully integrate
- Pipeline completes end-to-end
- But: CodeQL sparse, LLM limited to top-k, fusion gains minimal

**How to phrase**:
> "The integrated pipeline successfully combines static analysis, ML ranking, and LLM verification, though each component contributes differently to overall performance."

**Limitation**: Integration works, but benefits are component-specific

---

## UNSUPPORTED CLAIMS ❌

### 1. ❌ Full Method Significantly Outperforms Ranker-Only on Whole-Corpus F1
**Counter-Evidence**:
- Average F1 improvement: +0.0020 (Table 6)
- Devign: -0.0000, BigVul: +0.0044, DiverseVul: +0.0016
- Improvements are within noise margin

**Why unsupported**:
- LLM only covers top-50 (5% of test set)
- Limited coverage cannot significantly impact whole-corpus metrics
- No validation set available for threshold calibration

**DO NOT claim**: "Our full method achieves superior whole-corpus detection compared to ranker-only baseline."

**Instead, claim**: "The ranker provides the primary whole-corpus detection capability, with optional LLM verification for top candidates."

---

### 2. ❌ LLM Universally Reduces False Positives
**Counter-Evidence**:
- Devign: negative precision gains at top-30 (-0.20) and top-50 (-0.07)
- Mixed results across k values and datasets
- Not consistent across all scenarios

**Why unsupported**:
- Dataset-dependent behavior
- K-dependent behavior
- No universal pattern

**DO NOT claim**: "LLM verification reduces false positives across all datasets."

**Instead, claim**: "LLM verification improves precision on specific datasets (BigVul, DiverseVul) and k values, but effectiveness varies."

---

### 3. ❌ Calibrated Fusion is the Best Whole-Corpus Classifier
**Counter-Evidence**:
- Minimal improvements over ranker-only (Table 6)
- Policy A (incremental adjustment) barely different from Policy D (ranker-only)
- Statistical and practical significance questionable

**Why unsupported**:
- Gains are negligible (+0.002 F1)
- No statistical significance testing conducted
- Improvements likely within measurement noise

**DO NOT claim**: "Calibrated fusion achieves the best whole-corpus classification performance."

**Instead, claim**: "Calibrated fusion provides a framework for evidence aggregation, with the ranker remaining the primary performance driver."

---

### 4. ❌ CodeQL Provides Comprehensive Static Evidence
**Counter-Evidence**:
- Coverage: 0.5-1.3% (Table 3)
- Function-level datasets lack build context
- Most samples have zero static alerts

**Why unsupported**:
- Coverage is objectively sparse
- Cannot claim "comprehensive" with <2% coverage

**DO NOT claim**: "CodeQL static analysis provides comprehensive vulnerability evidence."

**Instead, claim**: "CodeQL provides sparse static evidence limited by function-level evaluation context."

---

### 5. ❌ LLM is Essential for Good Performance
**Counter-Evidence**:
- Ranker-only achieves comparable whole-corpus performance (Table 6)
- LLM adds minimal F1 improvement
- System works without LLM

**Why unsupported**:
- Ranker alone is competitive
- LLM is optional enhancement, not requirement

**DO NOT claim**: "LLM integration is essential for effective vulnerability detection."

**Instead, claim**: "LLM provides optional verification for top candidates, while the ranker delivers baseline performance."

---

## Research Question Support Summary

| RQ | Question | Support Level | Primary Evidence |
|----|----------|---------------|------------------|
| RQ1 | Ranker effectiveness? | ✅ **Supported** | Table 2, Table 5 (top-k precision) |
| RQ2 | Static evidence utility? | ⚠️ **Partial** | Table 3 (sparse but valid) |
| RQ3 | LLM top-k verification? | ⚠️ **Partial** | Table 5 (dataset-dependent) |
| RQ4 | Cost-effectiveness? | ✅ **Supported** | Table 4, Table 8 ($0.125 total) |
| RQ5 | Fusion whole-corpus improvement? | ❌ **Not supported** | Table 6 (+0.002 F1) |

---

## How to Frame Limitations

### 1. CodeQL Coverage
**Limitation**: "Function-level datasets lack full project build context required for comprehensive static analysis."

**Impact**: "CodeQL coverage is sparse (0.5-1.3%), limiting static evidence availability."

**Mitigation**: "Despite sparse coverage, identified alerts correspond to valid CWE categories."

---

### 2. LLM Coverage
**Limitation**: "LLM verification applied only to top-50 candidates (5% of test set) due to cost considerations."

**Impact**: "Limited LLM coverage restricts impact on whole-corpus classification metrics."

**Mitigation**: "Top-50 strategy balances cost-effectiveness with candidate verification utility."

---

### 3. Dataset Characteristics
**Limitation**: "Dataset imbalance varies significantly (Devign 45.6% vs BigVul/DiverseVul ~5.6%)."

**Impact**: "LLM verification effectiveness depends on dataset characteristics and imbalance ratios."

**Mitigation**: "Results across three datasets with different characteristics demonstrate generalization patterns."

---

### 4. Validation Unavailable
**Limitation**: "No validation set available for threshold calibration in calibrated fusion experiments."

**Impact**: "Fixed threshold (0.5) used instead of calibrated threshold, potentially suboptimal."

**Mitigation**: "Calibrated fusion treated as sensitivity analysis rather than optimized integration."

---

### 5. Train-Test Gap
**Limitation**: "Significant train-test performance gap observed (expected for security tasks)."

**Impact**: "Test F1 substantially lower than training F1 (e.g., Devign: 0.83 → 0.56)."

**Mitigation**: "ROC-AUC remains stable, indicating preserved ranking capability despite classification difficulty."

---

## Final Claim Boundary Summary

### ✅ SAFE TO CLAIM
1. Ranker provides effective vulnerability candidate prioritization
2. DeepSeek API verification is cost-effective ($0.125 total)
3. LLM improves top-k precision on BigVul and DiverseVul
4. Modular architecture enables flexible deployment
5. System reduces manual review burden through ranking

### ⚠️ CLAIM WITH CAVEATS
1. LLM helps with candidate verification (dataset-dependent)
2. CodeQL provides sparse but valid static evidence
3. Calibrated fusion provides minimal whole-corpus improvements
4. Integration pipeline is functional but benefits vary by component

### ❌ DO NOT CLAIM
1. Full method significantly beats ranker-only on whole-corpus F1
2. LLM universally reduces false positives
3. Calibrated fusion is the best classifier
4. CodeQL provides comprehensive static evidence
5. LLM is essential for good performance

**Recommended positioning**: SemVulGuard as a ranker-driven vulnerability candidate discovery framework with optional LLM-based semantic verification for top-ranked candidates.
