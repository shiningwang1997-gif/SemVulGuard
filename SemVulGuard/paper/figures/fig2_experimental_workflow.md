```mermaid
flowchart TD
    A[Three Datasets<br/>Devign, BigVul, DiverseVul] --> B[Stratified Split<br/>70% Train / 10% Valid / 20% Test]
    B --> C[Train Ranker<br/>on Train Split]
    C --> D[Test-Only Evaluation<br/>Held-Out Test Set]
    D --> E[Ranker Baseline<br/>Whole-Corpus Metrics]
    D --> F[Top-50 Selection<br/>per Dataset]
    F --> G[Real DeepSeek API<br/>Verification]
    G --> H[Top-K Candidate<br/>Precision Analysis]
    H --> I[Calibrated Fusion<br/>Sensitivity Analysis]
    E --> J[Final Results]
    I --> J
    
    style D fill:#ffebee,stroke:#c62828,stroke-width:3px
    style G fill:#e1f5ff,stroke:#0066cc,stroke-width:2px
    style I fill:#fff9c4,stroke:#f9a825,stroke-width:2px
```

**Figure 2: Experimental Workflow**

**Key Stages**:
- **Stratified Split (70/10/20)**: Ensures balanced train/valid/test distribution
- **Test-Only Evaluation (Red)**: Strict held-out testing with no hyperparameter tuning on test data
- **Real API Verification (Blue)**: 150 DeepSeek API calls (50 per dataset), 100% success rate
- **Calibrated Fusion (Yellow)**: Sensitivity analysis, not primary performance claim

**Evaluation Protocol**:
1. Train ranker on 70% training data (3,500 samples per dataset)
2. Evaluate on 20% held-out test data (1,000 samples per dataset)
3. Select top-50 ranked candidates per dataset
4. Verify with real DeepSeek API (total cost: $0.125)
5. Analyze top-k precision improvements
6. Explore fusion strategies (751 configs per dataset)

**Scientific Rigor**:
- No test-set tuning (fixed threshold 0.5)
- No cross-contamination between splits
- Real API calls (not simulated)
- Honest reporting of all results (including negative)
