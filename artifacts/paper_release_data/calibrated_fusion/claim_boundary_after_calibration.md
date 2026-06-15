# Claim Boundary After Calibration

## Evidence-Based Claims (SUPPORTED)

### 1. Ranker Performance
✅ **Claim**: SemVulGuard's ranker effectively prioritizes vulnerability candidates
- Evidence: Ranker achieves meaningful precision on top-k candidates across datasets
- Example: Devign top-10 ranker precision = 0.80, BigVul top-30 = 0.27

✅ **Claim**: Ranker provides baseline whole-corpus classification
- Evidence: Ranker-only baseline achieves reasonable F1/MCC across datasets

### 2. LLM Verification Module
✅ **Claim**: LLM can be integrated as an optional verification layer
- Evidence: Policy A (ranker-preserving LLM adjustment) selected as best across datasets
- Evidence: Modular architecture supports LLM integration

✅ **Claim**: LLM verdicts provide additional information for top candidates
- Evidence: LLM generates verdicts (vulnerable/benign/uncertain) with confidence scores

### 3. System Architecture
✅ **Claim**: SemVulGuard combines static analysis, ML ranking, and optional LLM verification
- Evidence: Pipeline successfully processes CodeQL alerts → feature extraction → ranking → LLM verification

✅ **Claim**: Modular design allows flexible deployment
- Evidence: Each component (CodeQL, ranker, LLM) can run independently

## Weak/Unsupported Claims (AVOID)

### 1. Whole-Corpus Performance
❌ **DO NOT claim**: LLM fusion significantly improves whole-corpus F1
- Evidence: Average F1 improvement = +0.0020 (minimal)

❌ **DO NOT claim**: Fusion method beats ranker-only baseline convincingly
- Evidence: Improvements are small and inconsistent

❌ **DO NOT claim**: Universal false-positive reduction
- Evidence: Top-k precision improvements are inconsistent (some positive, some negative)

### 2. LLM Necessity
❌ **DO NOT claim**: LLM is essential for good vulnerability detection
- Evidence: Ranker-only baseline achieves comparable performance

❌ **DO NOT claim**: LLM always improves precision
- Evidence: Mixed results in top-k precision improvements

### 3. Coverage Claims
❌ **DO NOT claim**: Full test set receives LLM verification
- Evidence: Only top-50 candidates (5% of test set) received LLM verdicts

## Recommended Paper Positioning

### Title/Abstract Focus
**Emphasize**: "Ranker-driven vulnerability discovery with optional LLM verification"
**Avoid**: "LLM-enhanced vulnerability detection" (implies LLM is primary)

### Contributions
1. **Primary**: Effective ML ranker for vulnerability candidate prioritization
2. **Secondary**: Modular architecture integrating static analysis, ML, and LLM
3. **Tertiary**: Empirical study of LLM verification for top candidates

### Results Section Structure
1. **Ranker performance** (main results)
   - Whole-corpus metrics
   - Top-k precision
   - Comparison with baselines

2. **LLM verification study** (supplementary/ablation)
   - Top-50 candidate verification
   - Policy comparison
   - Sensitivity analysis

### Honest Limitations
1. LLM verification only applied to top-50 candidates per dataset
2. No validation set available for threshold calibration
3. LLM fusion shows modest or mixed improvements
4. Cost considerations limit LLM applicability to full corpus

## Final Recommendation

**Position SemVulGuard as**: A practical, ranker-driven vulnerability discovery framework that effectively prioritizes candidates for manual review, with optional LLM verification for high-priority cases.

**Value proposition**: Reduces manual review burden by learning to rank vulnerability candidates, not by claiming to be the best classifier.

## Summary Statistics

- Average F1 improvement: +0.0020
- Average MCC improvement: +0.0025
- Best policy: {'policy_a': 3}
- Datasets tested: 3
- LLM coverage: 50 samples per dataset (top-50 candidates)
