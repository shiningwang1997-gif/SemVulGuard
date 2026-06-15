# Reproducing Experiments

This guide provides step-by-step instructions for reproducing the experiments reported in the SemVulGuard paper.

## Overview

SemVulGuard's evaluation pipeline consists of:
1. **Data preparation:** Processing raw vulnerability datasets
2. **CodeQL analysis:** Static analysis for candidate selection
3. **Ranker training:** Learning to rank vulnerabilities by severity
4. **LLM verification:** DeepSeek-based verification of candidates
5. **Calibrated fusion:** Combining ranker and LLM outputs
6. **Evaluation:** Computing metrics and generating figures

## Prerequisites

### System Requirements

- **OS:** Linux (tested on Ubuntu 20.04+)
- **Python:** 3.9 or higher
- **Memory:** 16GB RAM minimum (32GB recommended)
- **Disk:** 50GB free space for datasets and artifacts
- **CPU:** Multi-core processor (8+ cores recommended for parallel processing)

### Required Software

1. **Python 3.9+**
2. **Git**
3. **CodeQL CLI** (for static analysis)
4. **Joern** (for code property graph extraction, optional)

## Step 1: Environment Setup

### Clone the Repository

```bash
git clone https://github.com/your-username/SemVulGuard.git
cd SemVulGuard
```

### Create Python Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Install Dependencies

```bash
# Core dependencies
pip install -r requirements.txt

# Development dependencies (for running tests)
pip install -r requirements-dev.txt

# Evaluation dependencies (for metrics and visualization)
pip install -r requirements-eval.txt

# Model dependencies (for ML components)
pip install -r requirements-models.txt
```

### Verify Installation

```bash
# Run tests to verify setup
pytest tests/

# Check that the package is importable
python -c "import semvulguard; print(semvulguard.__version__)"
```

## Step 2: Install External Tools

### CodeQL CLI

CodeQL is required for static analysis and candidate selection.

```bash
# Download CodeQL CLI (version 2.15.0 or later)
wget https://github.com/github/codeql-cli-binaries/releases/download/v2.15.0/codeql-linux64.zip

# Extract to the parent directory
unzip codeql-linux64.zip -d ../

# Add CodeQL to PATH
export PATH="$PATH:$(realpath ../codeql-linux64/codeql)"

# Verify installation
codeql --version
```

**Permanent PATH setup:** Add to your `~/.bashrc` or `~/.zshrc`:
```bash
export PATH="$PATH:/path/to/codeql-linux64/codeql"
```

### Joern (Optional)

Joern is used for advanced code property graph analysis. It's optional but recommended for full reproducibility.

```bash
# Download and install Joern
wget https://github.com/joernio/joern/releases/latest/download/joern-install.sh
chmod +x joern-install.sh
./joern-install.sh --install-dir=../joern

# Add Joern to PATH
export PATH="$PATH:$(realpath ../joern)"
```

## Step 3: Download Raw Datasets

Raw vulnerability datasets must be downloaded separately. See `DATA_AVAILABILITY.md` for detailed instructions.

### Create Experiment Directory

```bash
mkdir -p ../experiment/devign
mkdir -p ../experiment/bigvul
mkdir -p ../experiment/diversevul
```

### Devign Dataset

```bash
cd ../experiment/devign
git clone https://github.com/epicosy/devign.git
# Follow the repository's instructions to obtain the dataset
cd ../../SemVulGuard
```

### BigVul Dataset

```bash
cd ../experiment/bigvul
# Download from https://github.com/ZeoVan/MSR_20_Code_vulnerability_CSV_Dataset
# Or use the official MSR Data Showcase link
cd ../../SemVulGuard
```

### DiverseVul Dataset

```bash
cd ../experiment/diversevul
git clone https://github.com/DiverseVul/DiverseVul.git
# Follow their data preparation instructions
cd ../../SemVulGuard
```

After downloading, verify the directory structure:
```bash
tree ../experiment -L 2
```

## Step 4: Configure API Access

### DeepSeek API Key

SemVulGuard uses DeepSeek for LLM-based verification.

```bash
# Set the API key as an environment variable
export DEEPSEEK_API_KEY="your-api-key-here"

# For permanent setup, add to ~/.bashrc:
echo 'export DEEPSEEK_API_KEY="your-api-key-here"' >> ~/.bashrc
```

**Get an API key:** Register at https://platform.deepseek.com/

**Cost estimate:** Running the full evaluation on all three datasets costs approximately $50-100 in API credits, depending on the number of samples and verification rounds.

## Step 5: Data Preprocessing

Process the raw datasets into a format suitable for analysis:

```bash
# Preprocess Devign
python scripts/preprocess_devign.py \
    --input ../experiment/devign/ \
    --output artifacts/processed/devign/

# Preprocess BigVul
python scripts/preprocess_bigvul.py \
    --input ../experiment/bigvul/ \
    --output artifacts/processed/bigvul/

# Preprocess DiverseVul
python scripts/preprocess_diversevul.py \
    --input ../experiment/diversevul/ \
    --output artifacts/processed/diversevul/
```

## Step 6: Run CodeQL Analysis

Extract candidates using CodeQL static analysis:

```bash
# Run CodeQL on all datasets
python scripts/run_codeql_analysis.py \
    --datasets devign bigvul diversevul \
    --output artifacts/codeql_results/

# This step may take several hours depending on dataset size
```

## Step 7: Train the Ranker

Train the vulnerability severity ranker:

```bash
# Train on the combined dataset
python scripts/train_ranker.py \
    --train-data artifacts/processed/ \
    --output models/ranker/ \
    --config configs/ranker_config.yaml

# Evaluate the ranker
python scripts/evaluate_ranker.py \
    --model models/ranker/ \
    --test-data artifacts/processed/ \
    --output artifacts/ranker_results/
```

## Step 8: Run LLM Verification

Run DeepSeek-based verification on ranked candidates:

```bash
# Verify top candidates
python scripts/run_llm_verification.py \
    --candidates artifacts/ranker_results/top_candidates.json \
    --output artifacts/llm_verification/ \
    --api-key $DEEPSEEK_API_KEY \
    --model deepseek-coder

# This step will take time and consume API credits
```

## Step 9: Calibrated Fusion

Combine ranker and LLM outputs using calibrated fusion:

```bash
python scripts/run_calibrated_fusion.py \
    --ranker-scores artifacts/ranker_results/ \
    --llm-verdicts artifacts/llm_verification/ \
    --output artifacts/calibrated_fusion/ \
    --config configs/fusion_config.yaml
```

## Step 10: Evaluate and Generate Results

Compute metrics and generate paper figures:

```bash
# Compute all metrics
python scripts/compute_metrics.py \
    --results artifacts/calibrated_fusion/ \
    --output artifacts/metrics/

# Generate paper tables
python scripts/generate_tables.py \
    --metrics artifacts/metrics/ \
    --output paper/tables/

# Generate paper figures
python scripts/generate_figures.py \
    --data artifacts/metrics/ \
    --output paper/figures/
```

## Step 11: Verify Against Paper Release Data

Compare your results with the provided paper release data:

```bash
python scripts/compare_with_release.py \
    --your-results artifacts/metrics/ \
    --release-data artifacts/paper_release_data/ \
    --output artifacts/verification_report.md
```

Expected differences:
- Minor numerical variations due to floating-point precision
- Small differences if dataset versions have been updated
- Random seed effects in model training

## Troubleshooting

### Common Issues

**Issue: CodeQL not found**
```bash
# Solution: Ensure CodeQL is in PATH
export PATH="$PATH:/path/to/codeql-linux64/codeql"
codeql --version
```

**Issue: DEEPSEEK_API_KEY not set**
```bash
# Solution: Export the environment variable
export DEEPSEEK_API_KEY="your-key"
# Verify:
echo $DEEPSEEK_API_KEY
```

**Issue: Out of memory during processing**
```bash
# Solution: Process datasets in smaller batches
python scripts/run_llm_verification.py \
    --batch-size 10 \
    --max-workers 2
```

**Issue: Dataset not found**
```bash
# Solution: Verify dataset paths
ls -la ../experiment/devign/
# Ensure preprocessing completed successfully
ls -la artifacts/processed/
```

**Issue: Model training fails**
```bash
# Solution: Check CUDA availability if using GPU
python -c "import torch; print(torch.cuda.is_available())"
# Or force CPU mode:
export CUDA_VISIBLE_DEVICES=""
```

### Testing Individual Components

Test each component independently before running the full pipeline:

```bash
# Test CodeQL integration
pytest tests/test_codeql.py -v

# Test ranker
pytest tests/test_ranker.py -v

# Test LLM integration (requires API key)
pytest tests/test_llm_verification.py -v

# Test fusion
pytest tests/test_calibrated_fusion.py -v
```

## Reproducing Specific Paper Claims

### Table 1: Overall Performance Metrics

```bash
python scripts/generate_table1.py \
    --results artifacts/metrics/ \
    --output paper/table1_performance.csv
```

### Figure 3: ROC and PR Curves

```bash
python scripts/generate_figure3.py \
    --results artifacts/ranker_results/ \
    --output paper/figures/fig3_ranker_roc_pr_auc.pdf
```

### Ablation Studies

```bash
# Run ablation: without ranker
python scripts/run_ablation.py --mode no_ranker

# Run ablation: without LLM
python scripts/run_ablation.py --mode no_llm

# Run ablation: without fusion
python scripts/run_ablation.py --mode no_fusion
```

## Time and Cost Estimates

**Total time for full pipeline:** 12-24 hours (depending on hardware)

Breakdown:
- Data preprocessing: 1-2 hours
- CodeQL analysis: 4-8 hours
- Ranker training: 2-4 hours
- LLM verification: 3-6 hours (depends on API rate limits)
- Evaluation: 1-2 hours

**Computational cost:**
- DeepSeek API: $50-100
- GPU recommended for ranker training (or ~2x longer on CPU)

## Quick Start (Smoke Test)

To verify the pipeline works before running the full evaluation:

```bash
# Run on a small subset
python scripts/run_smoke_test.py \
    --samples 100 \
    --output artifacts/smoke_test/

# This should complete in ~30 minutes
```

## Getting Help

If you encounter issues:

1. Check this guide and `DATA_AVAILABILITY.md`
2. Review the test suite: `pytest tests/ -v`
3. Check existing GitHub issues
4. Open a new issue with:
   - Error message and full traceback
   - System information (`python --version`, `codeql --version`)
   - Steps to reproduce

## Citation

If you use SemVulGuard or this reproduction guide, please cite:

```
[Citation information to be added upon publication]
```
