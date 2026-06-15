# Method Positioning for SemVulGuard

## Final System Positioning

**SemVulGuard: A Ranker-Driven Vulnerability Candidate Discovery Framework with Optional LLM-Based Semantic Verification**

---

## Architecture Components and Their Roles

### 1. **Ranker: Primary Detection Engine** (Core Component)

**Role**: Whole-corpus vulnerability candidate prioritization

**Function**:
- Processes all code samples through ML-based ranking
- Combines static features (complexity, tokens) with semantic features (code embeddings)
- Produces ranked list of vulnerability candidates with confidence scores
- Serves as the baseline detection system

**Performance**:
- Provides primary whole-corpus detection capability
- ROC-AUC: 0.62-0.74 across datasets
- Test F1: 0.20-0.56 depending on dataset characteristics

**Positioning in paper**:
> "The ranker forms the core of SemVulGuard, providing reliable whole-corpus vulnerability candidate prioritization through gradient boosting over static and semantic features."

**Key message**: This is the main contribution and primary performance source.

---

### 2. **CodeQL: Sparse Static Evidence Layer** (Supporting Component)

**Role**: Supplementary static analysis evidence when available

**Function**:
- Executes industry-standard static analysis queries
- Provides CWE mappings and alert metadata when compilable
- Enriches feature space with static evidence signals

**Coverage**:
- Sparse: 0.5-1.3% of test samples
- Limited by function-level evaluation context
- Requires full project build context for comprehensive coverage

**Positioning in paper**:
> "CodeQL static analysis provides supplementary evidence where available, though coverage is limited (0.5-1.3%) by the function-level evaluation context lacking full project compilation environments."

**Key message**: This is a supporting component, not a primary performance driver. Acknowledge sparsity upfront.

---

### 3. **DeepSeek LLM: Top-K Semantic Verifier** (Optional Component)

**Role**: Post-hoc semantic verification for top-ranked candidates

**Function**:
- Analyzes top-k candidates flagged by ranker
- Provides semantic reasoning about vulnerability presence
- Generates verdicts (vulnerable/benign/uncertain) with confidence scores
- Acts as a verification layer, not a classifier

**Coverage**:
- Top-50 candidates per dataset (5% of test set)
- Cost-effective: $0.0008 per verification
- 100% success rate in experiments

**Performance**:
- Improves top-k precision on BigVul (+0.28 to +0.48) and DiverseVul (+0.14 to +0.20)
- Mixed results on Devign (dataset-dependent)
- Minimal whole-corpus impact due to limited coverage

**Positioning in paper**:
> "For top-ranked candidates, we employ DeepSeek LLM as an optional semantic verifier, providing human-interpretable reasoning about vulnerability likelihood. This verification is cost-effective ($0.0008 per candidate) and improves precision on imbalanced datasets."

**Key message**: LLM is a top-k verification tool, not the main classifier. Emphasize cost-effectiveness and optional nature.

---

### 4. **Fusion: Evidence Aggregation Framework** (Analysis Component)

**Role**: Sensitivity analysis of evidence combination strategies

**Function**:
- Explores multiple policies for combining ranker scores with LLM verdicts
- Grid search over hyperparameters (alpha, beta, gamma, k)
- Compares ranker-only baseline vs. LLM-adjusted approaches

**Performance**:
- Minimal whole-corpus gains: average F1 +0.002, MCC +0.0025
- Policy A (incremental adjustment) selected across all datasets
- Limited by sparse LLM coverage (5% of test set)

**Positioning in paper**:
> "We explore calibrated fusion strategies for evidence aggregation, finding that incremental score adjustment (Policy A) is most effective. However, whole-corpus gains are minimal (+0.002 F1) due to limited LLM coverage, positioning fusion as a sensitivity analysis rather than the primary performance contribution."

**Key message**: Fusion is an analysis/ablation study, not a claim that fusion beats ranker-only.

---

## System Workflow

```
Input: Code sample
   ↓
1. CodeQL Static Analysis (optional, sparse coverage)
   ↓
2. Feature Extraction (static + semantic)
   ↓
3. ML Ranker (gradient boosting)
   ↓
   Ranked list of all samples
   ↓
4. Top-K Selection (e.g., top-50)
   ↓
5. LLM Semantic Verification (optional, cost-effective)
   ↓
6. Final Report: Ranked candidates + semantic reasoning
```

**Key architectural decision**: Modular design allows each component to be deployed independently or together.

---

## Positioning Relative to Baselines

### vs. Static Analysis Only (CodeQL)
**Advantage**: Ranker provides comprehensive coverage (100% vs. 0.5-1.3%)
**Limitation**: CodeQL alerts are high-precision when available

**Claim**: "SemVulGuard's ranker complements sparse static analysis with comprehensive ML-based ranking."

---

### vs. ML-Only (No LLM)
**Advantage**: LLM adds semantic verification for top candidates
**Limitation**: LLM adds cost and latency

**Claim**: "LLM verification is optional, providing semantic reasoning for high-priority cases while the ranker delivers baseline performance."

---

### vs. LLM-Only
**Advantage**: Ranker is cost-effective and provides whole-corpus coverage
**Limitation**: LLM may capture semantic patterns ranker misses

**Claim**: "Ranker-driven prioritization enables cost-effective whole-corpus analysis, with LLM verification applied selectively to top candidates."

---

## Value Proposition

### Primary Value: Effective Candidate Prioritization
- Ranker reduces manual review burden by ranking all samples
- Top-k precision demonstrates successful candidate discovery
- Cost-effective baseline requiring no API calls

### Secondary Value: Optional Semantic Verification
- LLM adds interpretable reasoning for top candidates
- Low cost per verification ($0.0008)
- Improves precision on imbalanced datasets

### Tertiary Value: Modular and Flexible
- Components can be deployed independently
- Users can choose ranker-only, ranker+static, or full pipeline
- Cost-performance tradeoff adjustable via k parameter

---

## What SemVulGuard Is NOT

❌ **Not a whole-corpus classifier that beats all baselines**
- Ranker is the primary whole-corpus performer
- Fusion provides minimal improvement

❌ **Not an LLM-first system**
- LLM is supplementary, not primary
- System works effectively without LLM

❌ **Not a comprehensive static analyzer**
- CodeQL coverage is sparse (function-level limitation)
- Static evidence is supplementary

❌ **Not a production-ready security tool**
- Research prototype demonstrating feasibility
- Requires further engineering for deployment

---

## Recommended Paper Structure

### Abstract
1. Problem: Vulnerability detection needs effective prioritization
2. Approach: Ranker-driven framework with optional LLM verification
3. Results: Ranker achieves X ROC-AUC, LLM improves top-k precision on Y datasets, total cost $0.125
4. Conclusion: Effective candidate discovery with cost-efficient semantic verification

### Introduction
1. Motivation: Manual review burden, need for prioritization
2. Gap: Existing methods lack modular, cost-effective verification
3. Contribution: Ranker-driven framework + optional LLM verification
4. Key result: Effective prioritization + cost-efficient verification

### Method (Section 3)
1. Architecture overview (Figure 1: modular pipeline)
2. Ranker design (primary component)
3. CodeQL integration (sparse evidence layer)
4. LLM verification (optional top-k semantic reasoning)
5. Fusion strategies (evidence aggregation)

### Experiments (Section 4)
1. **4.3 Whole-Corpus Detection Performance** (Ranker as baseline)
2. **4.4 Ranker Effectiveness** (Top-k precision, ROC-AUC)
3. **4.5 Static Evidence Coverage** (CodeQL sparsity)
4. **4.6 LLM Top-K Verification** (Precision gains, cost analysis)
5. **4.7 Calibrated Fusion** (Sensitivity analysis, minimal gains)

### Discussion
1. Why ranker-only is competitive
2. When LLM helps (dataset characteristics)
3. Limitations (CodeQL sparse, LLM limited coverage)
4. Future work (project-level analysis, full-corpus LLM)

---

## Key Messages for Reviewers

1. **Honest about what works**: Ranker is the main contributor, LLM helps in specific scenarios
2. **Transparent about limitations**: CodeQL sparse, LLM limited coverage, fusion gains minimal
3. **Clear value proposition**: Cost-effective candidate discovery with optional verification
4. **Modular design**: Flexible deployment, not monolithic "best system" claim
5. **Scientifically rigorous**: No test-set tuning, honest negative results reported

---

## Elevator Pitch

> "SemVulGuard is a ranker-driven vulnerability candidate discovery framework that effectively prioritizes code samples for manual review. For top candidates, optional LLM-based semantic verification provides interpretable reasoning at low cost ($0.0008 per sample). Unlike monolithic approaches, our modular design allows flexible deployment while maintaining cost-effectiveness."

**Focus**: Prioritization + optional verification, not "best classifier."
