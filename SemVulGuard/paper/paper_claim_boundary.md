# Paper Claim Boundary - Final Assessment

## SUPPORTED CLAIMS ✅

### Claims with Strong Experimental Support

#### 1. Ranker Provides Effective Vulnerability Candidate Prioritization
**Evidence**:
- ROC-AUC: 0.623 (Devign), 0.744 (BigVul), 0.721 (DiverseVul)
- Top-10 precision: 0.80 (Devign), 0.40 (BigVul), 0.30 (DiverseVul)
- Meaningful separation of vulnerable and benign code samples

**Recommended Phrasing**:
> "Our ML ranker effectively prioritizes vulnerability candidates across three datasets, achieving ROC-AUC scores between 0.62 and 0.74, with top-10 precision ranging from 0.30 to 0.80."

**Supports**: RQ1 - Core contribution

---

#### 2. DeepSeek API Verification is Cost-Effective and Reliable
**Evidence**:
- Total cost: $0.125 for 150 API calls
- 100% success rate (0 failures)
- Cost per verification: ~$0.0008

**Recommended Phrasing**:
> "LLM-based semantic verification using DeepSeek-v4-flash is highly cost-effective ($0.0008 per candidate) and reliable (100% success rate in our experiments)."

**Supports**: RQ4 - Practical deployment feasibility

---

#### 3. LLM Verification Improves Top-K Precision on Imbalanced Datasets
**Evidence**:
- BigVul: precision gains of +0.10 to +0.48
- DiverseVul: precision gains of +0.14 to +0.20
- Consistent positive improvements across different k values

**Recommended Phrasing**:
> "For imbalanced datasets (BigVul, DiverseVul with ~5.6% vulnerability rate), LLM verification consistently improves top-k candidate precision, with gains ranging from +0.10 to +0.48 depending on k."

**Supports**: RQ3 - LLM verification utility (partial)

---

#### 4. Modular Architecture Enables Flexible Deployment
**Evidence**:
- Each component (CodeQL, Ranker, LLM) can operate independently
- Ranker provides baseline without requiring LLM
- LLM can be applied selectively based on budget

**Recommended Phrasing**:
> "SemVulGuard's modular architecture allows flexible deployment: the ranker provides baseline detection independently, with optional static analysis and LLM verification for resource-constrained or high-priority scenarios."

**Supports**: System design goals

---

#### 5. System Reduces Manual Review Burden Through Ranking
**Evidence**:
- Top-k concentrates vulnerabilities
- Top-10 precision 0.30-0.80 vs random baseline ~0.06-0.46
- Clear prioritization signal

**Recommended Phrasing**:
> "By concentrating vulnerabilities in top-ranked candidates, SemVulGuard reduces manual security review burden, enabling practitioners to focus on high-priority cases."

**Supports**: Practical utility claim

---

## PARTIALLY SUPPORTED CLAIMS ⚠️

### Claims That Require Significant Caveats

#### 1. LLM Helps with Candidate Verification (Dataset-Dependent)
**Evidence**:
- ✅ BigVul: +0.10 to +0.48
- ✅ DiverseVul: +0.14 to +0.20
- ❌ Devign: +0.20 at top-10, but -0.07 to -0.20 at top-30/50

**Caveat**: Not universally beneficial; depends on dataset characteristics

**Recommended Phrasing**:
> "LLM verification shows dataset-dependent effectiveness: consistent precision gains on imbalanced datasets (BigVul, DiverseVul) but mixed results on balanced data (Devign), suggesting effectiveness depends on baseline ranker precision and dataset imbalance."

**Supports**: RQ3 - with strong caveats about generalization

---

#### 2. CodeQL Provides Valid Static Evidence (When Available)
**Evidence**:
- ✅ Alerts correspond to valid CWE categories
- ❌ Coverage is only 0.5-1.3%
- ❌ Limited by function-level evaluation context

**Caveat**: "Valid" does not mean "comprehensive" or "sufficient"

**Recommended Phrasing**:
> "CodeQL provides sparse but valid static evidence (0.5-1.3% coverage), limited by function-level evaluation contexts lacking full project build specifications. When static analysis succeeds, identified alerts correspond to valid CWE categories."

**Supports**: RQ2 - with major limitations acknowledged

---

#### 3. Calibrated Fusion Demonstrates Evidence Aggregation Feasibility
**Evidence**:
- ✅ 1,533 configurations evaluated
- ✅ Policy A (incremental) consistently selected
- ❌ Whole-corpus gains minimal (+0.002 F1)

**Caveat**: Feasibility demonstrated, but not significant performance improvement

**Recommended Phrasing**:
> "Our exploration of calibrated fusion strategies demonstrates the feasibility of evidence aggregation, with incremental score adjustment proving most effective. However, whole-corpus improvements are minimal (+0.002 F1) due to limited LLM coverage (5% of test samples)."

**Supports**: Sensitivity analysis only, not performance claim

---

## UNSUPPORTED CLAIMS ❌

### Claims That Must NOT Be Made

#### 1. ❌ SemVulGuard Full Significantly Outperforms Ranker-Only on Whole-Corpus F1

**Counter-Evidence**:
- Average F1 improvement: +0.0020 (essentially zero)
- Devign: -0.0000, BigVul: +0.0044, DiverseVul: +0.0016
- All improvements within noise margin

**Why Unsupported**:
- LLM only covers 5% of test set
- No statistical significance testing
- Improvements negligible in magnitude

**DO NOT SAY**:
- "Our full method outperforms ranker-only baseline."
- "LLM integration significantly improves detection performance."
- "Fusion achieves superior whole-corpus results."

**INSTEAD SAY**:
> "The ranker provides the primary whole-corpus detection capability, with LLM verification offering optional enhancement for top candidates. Whole-corpus metrics show minimal change (+0.002 F1) when adding LLM verification, reflecting our design choice to apply LLM selectively (5% coverage) for cost-effectiveness."

---

#### 2. ❌ LLM Universally Reduces False Positives

**Counter-Evidence**:
- Devign top-30: precision decreases from 0.70 to 0.50 (-0.20)
- Devign top-50: precision decreases from 0.64 to 0.57 (-0.07)
- Mixed results across datasets and k values

**Why Unsupported**:
- Dataset-dependent behavior
- K-dependent behavior
- No universal pattern of improvement

**DO NOT SAY**:
- "LLM verification reduces false positives across all datasets."
- "Our approach universally improves precision."
- "LLM filtering eliminates false alarms."

**INSTEAD SAY**:
> "LLM verification improves precision on specific datasets and k values (e.g., BigVul top-30: +0.48) but shows mixed results in other scenarios (e.g., Devign top-30: -0.20), indicating that effectiveness depends on dataset characteristics and baseline ranker performance."

---

#### 3. ❌ Calibrated Fusion is the Best Whole-Corpus Classifier

**Counter-Evidence**:
- Minimal improvements over ranker-only (+0.002 F1, +0.003 MCC)
- No statistical significance demonstrated
- Ranker-only competitive with fusion

**Why Unsupported**:
- Gains are negligible
- Could be measurement noise
- Not practically significant

**DO NOT SAY**:
- "Calibrated fusion achieves the best classification performance."
- "Our optimized fusion method outperforms baselines."
- "Evidence aggregation maximizes detection accuracy."

**INSTEAD SAY**:
> "Calibrated fusion provides a framework for evidence aggregation, though whole-corpus gains are minimal (+0.002 F1). This positions fusion as a sensitivity analysis demonstrating incremental adjustment strategies, while the ranker remains the primary performance driver."

---

#### 4. ❌ CodeQL Provides Comprehensive Static Evidence

**Counter-Evidence**:
- Coverage: 0.5-1.3% of test samples
- Most samples have zero static alerts
- Function-level limitation acknowledged

**Why Unsupported**:
- "Comprehensive" contradicts 0.5-1.3% coverage
- Cannot claim completeness with <2% coverage
- Objectively sparse

**DO NOT SAY**:
- "CodeQL provides comprehensive vulnerability detection."
- "Static analysis covers all samples."
- "We integrate complete static analysis."

**INSTEAD SAY**:
> "CodeQL provides sparse static evidence (0.5-1.3% coverage) due to function-level evaluation lacking full project compilation environments. Despite limited coverage, identified alerts correspond to valid CWE categories, demonstrating value when applicable."

---

#### 5. ❌ LLM is Essential for Good Performance

**Counter-Evidence**:
- Ranker-only achieves comparable whole-corpus metrics
- ROC-AUC maintained without LLM (0.62-0.74)
- System works effectively without LLM

**Why Unsupported**:
- Ranker alone is competitive
- LLM adds minimal whole-corpus improvement
- Optional, not essential

**DO NOT SAY**:
- "LLM integration is necessary for effective vulnerability detection."
- "Without LLM, performance degrades significantly."
- "LLM is required for good results."

**INSTEAD SAY**:
> "While LLM verification provides optional enhancement for top candidates, the ranker delivers effective baseline performance independently (ROC-AUC 0.62-0.74). This modular design allows deployment without LLM when cost or latency constraints apply."

---

## Critical Statements That MUST Be Included

### 1. SemVulGuard Full Does Not Significantly Outperform Ranker-Only

**Required statement in paper** (Discussion or Limitations):
> "Our calibrated fusion experiments show that integrating LLM verdicts yields minimal whole-corpus improvement over ranker-only baseline (average F1 +0.002). This primarily reflects limited LLM coverage (5% of test samples) rather than ineffective integration. The ranker provides the primary detection capability, with LLM offering supplementary verification for top candidates."

**Where to place**: Section 4.7 (Calibrated Fusion) or Section 5 (Discussion)

---

### 2. DeepSeek Should Be Presented as Top-K Verifier, Not Whole-Corpus Classifier

**Required statement in paper** (Method or Discussion):
> "We employ LLM-based verification as a post-hoc validation step for top-ranked candidates rather than a whole-corpus classifier. This design choice balances cost-effectiveness (applying LLM to 5% of samples) with practical utility (verifying high-priority cases for manual review)."

**Where to place**: Section 3.4 (LLM Verification) or Section 4.6 (LLM Evaluation)

---

### 3. CodeQL Evidence is Sparse Due to Function-Level Context

**Required statement in paper** (Limitations):
> "CodeQL static analysis provides sparse coverage (0.5-1.3%) in our function-level evaluation. This limitation stems from dataset characteristics—isolated functions without project build context—rather than tool deficiencies. Project-level evaluation with complete build specifications would substantially improve static analysis coverage."

**Where to place**: Section 4.5 (Static Analysis) and Section 4.9 (Threats to Validity)

---

### 4. Strongest Positive Result: Candidate Precision on BigVul/DiverseVul

**Required statement in paper** (Results):
> "The strongest positive result is LLM verification's consistent improvement of top-k candidate precision on imbalanced datasets (BigVul, DiverseVul), with gains ranging from +0.10 to +0.48. This demonstrates LLM's value for verifying high-priority candidates flagged by the ranker."

**Where to place**: Section 4.6.2 (Top-K Verification Results) or Abstract

---

### 5. Calibrated Fusion is Sensitivity Analysis, Not Main Contribution

**Required statement in paper** (Method or Discussion):
> "We explore calibrated fusion strategies as a sensitivity analysis of evidence aggregation approaches rather than claiming fusion as the primary contribution. The minimal whole-corpus gains (+0.002 F1) reinforce that SemVulGuard's value lies in ranker-driven candidate discovery with optional verification, not in optimized fusion."

**Where to place**: Section 4.7 (Calibrated Fusion) introduction or Section 5 (Discussion)

---

## Summary: Three-Tier Claim Structure

### Tier 1: Primary Claims (Safe, Strong Evidence)
1. ✅ Ranker provides effective vulnerability candidate prioritization
2. ✅ Top-k precision demonstrates successful candidate concentration
3. ✅ LLM verification is cost-effective ($0.0008 per candidate)
4. ✅ System reduces manual review burden through ranking
5. ✅ Modular architecture enables flexible deployment

**Focus paper narrative on these claims.**

---

### Tier 2: Secondary Claims (Valid with Caveats)
1. ⚠️ LLM improves top-k precision on imbalanced datasets (dataset-dependent)
2. ⚠️ CodeQL provides valid evidence when available (coverage sparse)
3. ⚠️ Fusion demonstrates evidence aggregation feasibility (minimal impact)
4. ⚠️ System integrates three evidence sources (modular, not optimized)

**Present these with explicit caveats and limitations.**

---

### Tier 3: Avoided Claims (Unsupported)
1. ❌ Full method significantly beats ranker-only on whole-corpus F1
2. ❌ LLM universally reduces false positives
3. ❌ Calibrated fusion is the best classifier
4. ❌ CodeQL provides comprehensive evidence
5. ❌ LLM is essential for good performance

**Explicitly do NOT make these claims. Contradict them if needed.**

---

## Positioning Statement for Abstract/Conclusion

**Recommended Final Positioning**:

> "SemVulGuard is a ranker-driven vulnerability candidate discovery framework that effectively prioritizes code samples for security review (ROC-AUC 0.62-0.74). For top-ranked candidates, optional LLM-based semantic verification provides interpretable reasoning at low cost ($0.0008 per sample), improving precision on imbalanced datasets (gains up to +0.48). Our modular architecture allows flexible deployment, with the ranker providing reliable baseline performance while LLM verification offers targeted enhancement for high-priority cases. Evaluation on three C/C++ datasets demonstrates practical utility for reducing manual review burden, with total experimental cost of $0.125."

**Key messages**:
- Primary value: ranker-driven prioritization
- Secondary value: optional cost-effective LLM verification
- Tertiary value: modular, flexible architecture
- Honest about limitations: sparse static evidence, dataset-dependent LLM effectiveness

---

## Checklist for Paper Writing

Before submitting, verify:

- [ ] Abstract emphasizes ranker as primary component
- [ ] Introduction positions system as "ranker-driven with optional LLM"
- [ ] Method section describes modular architecture clearly
- [ ] Results section separates whole-corpus (ranker) from top-k (LLM) metrics
- [ ] Calibrated fusion presented as sensitivity analysis, not optimization
- [ ] Discussion includes "why fusion gains are minimal" explanation
- [ ] Limitations section acknowledges function-level evaluation constraints
- [ ] No claims that "full beats ranker-only on whole-corpus F1"
- [ ] No claims that "LLM universally improves results"
- [ ] CodeQL sparsity acknowledged upfront, not buried
- [ ] Devign negative results reported honestly
- [ ] All five critical statements included in appropriate sections

---

## Final Recommendation

**Write the paper as if the primary contribution is the ranker**, with LLM verification as an interesting optional module that adds value in specific scenarios. Do not write it as if the primary contribution is LLM-integration or fusion, because the experimental evidence does not support that narrative.

**Be proactive about limitations**: State them upfront in results sections, not just buried in limitations. This demonstrates scientific integrity and prevents reviewer criticism.

**Frame positively where possible**: "Cost-effective top-k verification" sounds better than "minimal whole-corpus improvement," even though both are true. Choose framing that emphasizes practical utility over benchmark metrics.

**Trust the experimental evidence**: The data tells a clear story—ranker works well, LLM helps in specific cases, fusion is minimal. Tell that story honestly rather than trying to force a "full method is best" narrative that the data doesn't support.
