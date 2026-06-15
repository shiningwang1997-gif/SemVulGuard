# SemVulGuard Paper Figures - Complete Package

**Generated**: 2026-06-15
**Status**: ✅ All figures generated successfully
**Formats**: PNG (300 DPI), PDF, SVG
**Total Files**: 24 files

---

## Quick Start

### For LaTeX Papers
Use PDF files (vector graphics, scalable):
```latex
\begin{figure}
  \centering
  \includegraphics[width=0.8\textwidth]{fig3_ranker_roc_pr_auc.pdf}
  \caption{Ranker Performance on Held-Out Test Sets}
  \label{fig:ranker_performance}
\end{figure}
```

### For Word Documents
Use PNG files (300 DPI, high quality):
- Drag and drop PNG files into document
- All images are 300 DPI for publication quality

### For Web/Presentations
Use SVG files (vector graphics, web-optimized):
- Scalable to any size without quality loss
- Editable in vector graphics software

### For Mermaid Diagrams (Figures 1-2)
- Use `.mmd` files in Mermaid-compatible tools
- View `.md` files for rendered previews with descriptions
- Tools: Mermaid Live Editor, GitHub, VS Code (with plugin)

---

## File Inventory

### Conceptual Diagrams (4 files)

**Figure 1: SemVulGuard Architecture**
- `fig1_semvulguard_architecture.mmd` - Mermaid source
- `fig1_semvulguard_architecture.md` - Markdown preview

**Figure 2: Experimental Workflow**
- `fig2_experimental_workflow.mmd` - Mermaid source
- `fig2_experimental_workflow.md` - Markdown preview

### Quantitative Charts (18 files = 6 figures × 3 formats)

**Figure 3: Ranker Held-Out Performance**
- `fig3_ranker_roc_pr_auc.png` (102 KB, 300 DPI)
- `fig3_ranker_roc_pr_auc.pdf` (16 KB, vector)
- `fig3_ranker_roc_pr_auc.svg` (37 KB, vector)

**Figure 4: LLM Top-K Precision Gain**
- `fig4_topk_precision_gain.png` (200 KB, 300 DPI)
- `fig4_topk_precision_gain.pdf` (16 KB, vector)
- `fig4_topk_precision_gain.svg` (39 KB, vector)

**Figure 5: DeepSeek Verdict Distribution**
- `fig5_llm_verdict_distribution.png` (118 KB, 300 DPI)
- `fig5_llm_verdict_distribution.pdf` (15 KB, vector)
- `fig5_llm_verdict_distribution.svg` (38 KB, vector)

**Figure 6: CodeQL Coverage**
- `fig6_codeql_coverage.png` (104 KB, 300 DPI)
- `fig6_codeql_coverage.pdf` (16 KB, vector)
- `fig6_codeql_coverage.svg` (36 KB, vector)

**Figure 7: Cost Analysis**
- `fig7_cost_analysis.png` (110 KB, 300 DPI)
- `fig7_cost_analysis.pdf` (16 KB, vector)
- `fig7_cost_analysis.svg` (36 KB, vector)

**Figure 8: Calibrated Fusion Delta**
- `fig8_calibrated_fusion_delta.png` (130 KB, 300 DPI)
- `fig8_calibrated_fusion_delta.pdf` (17 KB, vector)
- `fig8_calibrated_fusion_delta.svg` (41 KB, vector)

### Documentation (2 files)

- `figure_index.md` - Detailed figure descriptions and claim boundaries
- `generate_figures.py` - Reusable Python script to regenerate all figures
- `README.md` - This file

---

## Figure-to-Section Mapping

| Figure | Title | Section | Key Message |
|--------|-------|---------|-------------|
| 1 | Architecture | 3 (Method) | Ranker-driven, LLM optional |
| 2 | Workflow | 4.2 (Setup) | Test-only, no leakage |
| 3 | Ranker Performance | 4.3 (Baseline) | ROC-AUC 0.62-0.74 |
| 4 | Top-K Precision | 4.6 (LLM) | Dataset-dependent gains |
| 5 | LLM Verdicts | 4.6.1 (API) | Diverse verdict mix |
| 6 | CodeQL Coverage | 4.5 (Static) | Sparse (0.5-1.3%) |
| 7 | Cost Analysis | 4.8 (Cost) | $0.125 total |
| 8 | Fusion Delta | 4.7 (Fusion) | Minimal gains (+0.002) |

---

## Regenerating Figures

If you need to regenerate figures (e.g., after updating data):

```bash
# From project root
python3 paper_figures/generate_figures.py

# Or with virtual environment
.venv/bin/python paper_figures/generate_figures.py
```

**Requirements**:
- Python 3.7+
- matplotlib (install: `pip install matplotlib`)

**Data source**: `../paper_figures_data/*.csv`

**Safe to rerun**: Yes, script overwrites existing figures

---

## Quality Specifications

### PNG Files
- **Resolution**: 300 DPI
- **Use for**: Word documents, presentations, web
- **Size**: 100-200 KB per figure
- **Color**: RGB, suitable for print and screen

### PDF Files
- **Format**: Vector graphics (scalable)
- **Use for**: LaTeX papers, professional publications
- **Size**: 15-17 KB per figure
- **Embedding**: Fonts embedded, no external dependencies

### SVG Files
- **Format**: Vector graphics (web standard)
- **Use for**: Web presentations, further editing
- **Size**: 36-41 KB per figure
- **Compatibility**: Most modern browsers and vector editors

---

## Scientific Integrity Features

This figure package enforces honest reporting:

### ✅ Negative Results Shown
- **Figure 4**: Devign top-30 (-0.20) and top-50 (-0.07) negative gains displayed
- Red baseline at y=0 shows where improvements turn negative
- No cherry-picking of positive results only

### ✅ Minimal Gains Acknowledged
- **Figure 8**: Shows +0.0000 to +0.0058 improvements (very small)
- Y-axis scale not exaggerated
- Title explicitly states "Minimal Whole-Corpus Gains"

### ✅ Sparse Coverage Reported
- **Figure 6**: Shows 0.5-1.3% CodeQL coverage upfront
- Title mentions "Function-Level Evaluation" limitation
- No hiding of sparsity

### ✅ Dataset-Dependent Effectiveness
- **Figure 4**: Clearly shows BigVul/DiverseVul positive, Devign mixed
- Different colors per dataset for easy comparison
- No aggregation that would hide dataset differences

### ✅ Balanced Visual Design
- No misleading axis scaling (all start from appropriate baselines)
- Grid lines for easy value reading
- Value labels on bars for precision
- Consistent color schemes across figures

---

## Common Use Cases

### 1. Writing Section 4 (Experiments)
- Start with **Figure 2** (workflow) to establish protocol
- Use **Figure 3** (ranker) for baseline performance
- Use **Figures 4-5** (LLM) for top-k verification results
- Use **Figure 8** (fusion) for sensitivity analysis
- Use **Figure 7** (cost) for practical deployment discussion

### 2. Creating Presentation Slides
- **Figure 1**: System overview (1 slide)
- **Figure 3**: Main results (ranker performance)
- **Figure 4**: LLM contribution (highlight BigVul/DiverseVul)
- **Figure 7**: Cost-effectiveness (practical appeal)
- Skip Figure 8 in short talks (sensitivity analysis detail)

### 3. Responding to Reviewers
- **Figure 6**: "Why is CodeQL coverage sparse?" → Function-level limitation
- **Figure 8**: "How much does fusion help?" → Minimal (+0.002 F1)
- **Figure 4**: "Does LLM always help?" → Dataset-dependent, Devign shows mixed results
- **Figure 2**: "Was evaluation rigorous?" → Test-only, no leakage

### 4. Comparison with Prior Work
- Use **Figure 3** (ranker ROC-AUC) for fair comparison
- Note: Top-k precision (Figure 4) is task-specific, not directly comparable
- Cost analysis (Figure 7) supports practical deployment claims

---

## Claim Boundary Reminders

### ✅ SAFE Claims (Figures Support)

1. **"Ranker achieves ROC-AUC 0.62-0.74"** (Figure 3)
2. **"LLM improves top-k precision on BigVul (+0.10 to +0.48)"** (Figure 4)
3. **"Total experimental cost: $0.125"** (Figure 7)
4. **"CodeQL coverage is sparse (0.5-1.3%)"** (Figure 6)
5. **"Fusion yields minimal gains (+0.002 F1)"** (Figure 8)

### ❌ AVOID Claims (Figures Contradict)

1. ❌ **"LLM universally improves precision"** - Figure 4 shows Devign negative
2. ❌ **"Fusion significantly outperforms ranker-only"** - Figure 8 shows +0.002
3. ❌ **"CodeQL provides comprehensive evidence"** - Figure 6 shows 0.5-1.3%
4. ❌ **"LLM is the main classifier"** - Figure 1 shows ranker as primary
5. ❌ **"System has zero cost"** - Figure 7 shows $0.125 (though small)

---

## Tips for Effective Figure Use

### In Text References
```latex
% Good
Figure~\ref{fig:ranker_performance} shows that the ranker achieves 
ROC-AUC scores between 0.62 and 0.74 across three datasets.

% Avoid
As we can see from the figure, the system works really well.
```

### Caption Writing
- Start with what: "Ranker performance..."
- Add key finding: "...achieving ROC-AUC 0.62-0.74"
- Note method: "...on held-out test sets"
- Keep under 2-3 sentences

### Figure Placement
- Place near first text reference
- Avoid orphaning (figure alone on page)
- Group related figures (e.g., 4-5 together for LLM analysis)

---

## Troubleshooting

### Figure Won't Embed in LaTeX
- Use PDF, not PNG (better for LaTeX)
- Check path is correct relative to .tex file
- Try `\includegraphics{./paper_figures/fig3_ranker_roc_pr_auc.pdf}`

### Figure Looks Blurry in Word
- Use PNG at 300 DPI (provided)
- Don't resize too large (keep near original size)
- Export Word to PDF for final submission

### Mermaid Diagram Won't Render
- Copy `.mmd` content to Mermaid Live Editor (https://mermaid.live)
- Export as PNG/SVG from there if needed
- Or view `.md` files for rendered preview

### Need to Modify Figures
- Edit `generate_figures.py` to change appearance
- Rerun script to regenerate all figures
- Or edit SVG files in Inkscape/Illustrator (vector graphics)

---

## Contact and Maintenance

**Script**: `generate_figures.py`
**Data source**: `../paper_figures_data/*.csv`
**Last generated**: 2026-06-15

To update figures:
1. Update CSV files in `paper_figures_data/` if data changes
2. Run `python3 generate_figures.py`
3. All figures regenerated in seconds
4. Safe to commit to version control (reproducible)

---

## Summary

✅ **8 figures** (2 diagrams + 6 charts)
✅ **3 formats** (PNG 300 DPI + PDF + SVG)
✅ **24 total files** ready for publication
✅ **Scientific honesty** (negative results, minimal gains shown)
✅ **Publication quality** (consistent fonts, readable, clean)
✅ **Reusable script** (regenerate anytime)
✅ **Complete documentation** (figure_index.md + this README)

**Ready for paper submission** ✓
