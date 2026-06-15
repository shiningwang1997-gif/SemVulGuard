```mermaid
flowchart TD
    A[Code Sample/Function] --> B[Static Analysis<br/>CodeQL]
    A --> C[Feature Extraction]
    B --> C
    C --> D[Code Representation<br/>Ranker<br/><b>Primary Component</b>]
    D --> E[Ranked List<br/>All Samples]
    E --> F[Top-K Selection<br/>k=50]
    E --> G[Whole-Corpus<br/>Classification]
    F --> H[LLM Semantic<br/>Verification<br/><b>Optional</b>]
    H --> I[Evidence<br/>Aggregation/<br/>Fusion]
    D --> I
    I --> J[Vulnerability Report]
    G --> J
    
    style D fill:#e1f5ff,stroke:#0066cc,stroke-width:3px
    style H fill:#fff4e1,stroke:#ff9900,stroke-width:2px
    style E fill:#e8f5e9,stroke:#4caf50,stroke-width:2px
    
    classDef primary fill:#e1f5ff,stroke:#0066cc,stroke-width:3px
    classDef optional fill:#fff4e1,stroke:#ff9900,stroke-width:2px
    classDef output fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px
```

**Figure 1: SemVulGuard Architecture**

**Key Components**:
- **Ranker (Blue)**: Primary whole-corpus detection component
- **LLM Verification (Orange)**: Optional top-k semantic verification (5% coverage)
- **Ranked List (Green)**: All samples scored, enabling both whole-corpus and top-k analysis

**Data Flow**:
1. Code samples processed through static analysis (CodeQL) and feature extraction
2. Ranker scores all samples (primary performance driver)
3. Two parallel paths:
   - Whole-corpus classification (all samples)
   - Top-k selection → LLM verification → fusion (selective enhancement)
4. Final vulnerability report combines ranking with optional semantic reasoning

**Architectural Principles**:
- **Modular**: Each component operates independently
- **Flexible**: LLM verification is optional, not required
- **Cost-effective**: LLM applied only to top-k (5%) candidates
- **Ranker-driven**: Primary detection capability from ranker, not LLM
