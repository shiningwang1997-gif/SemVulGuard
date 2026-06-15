# Data Availability

This document describes the data sources, availability, and access instructions for SemVulGuard.

## Raw Datasets

SemVulGuard uses three public vulnerability datasets. Due to licensing and redistribution constraints, **raw datasets are NOT included in this repository**. Users must download them separately from official sources.

### 1. Devign Dataset

**Source:** Zhou et al., "Devign: Effective Vulnerability Identification by Learning Comprehensive Program Semantics via Graph Neural Networks" (NeurIPS 2019)

**Official Repository:** https://github.com/epicosy/devign

**Download Instructions:**
1. Clone the Devign repository
2. Follow their instructions to obtain the dataset
3. Place the downloaded data in `experiment/devign/` (create this directory if it doesn't exist)

**Expected Format:** JSON files containing function-level code and vulnerability labels

### 2. BigVul Dataset

**Source:** Fan et al., "AC/C++Eval: A Large-Scale Benchmark for Precise Code-LLM Assessment" (ACM CCS 2021)

**Official Repository:** https://github.com/ZeoVan/MSR_20_Code_vulnerability_CSV_Dataset

**Download Instructions:**
1. Download the BigVul dataset from the official repository or MSR Data Showcase
2. Place the downloaded data in `experiment/bigvul/` (create this directory if it doesn't exist)

**Expected Format:** CSV files with commit-level vulnerability information

### 3. DiverseVul Dataset

**Source:** Chen et al., "DiverseVul: A New Vulnerable Source Code Dataset for Deep Learning Based Vulnerability Detection" (RAID 2023)

**Official Repository:** https://github.com/DiverseVul/DiverseVul

**Download Instructions:**
1. Clone or download the DiverseVul repository
2. Follow their data preparation instructions
3. Place the processed data in `experiment/diversevul/` (create this directory if it doesn't exist)

**Expected Format:** JSON or CSV files with function-level vulnerability annotations

## Directory Structure for Raw Datasets

After downloading, your experiment directory should look like:

```
experiment/
├── devign/
│   └── [Devign dataset files]
├── bigvul/
│   └── [BigVul dataset files]
└── diversevul/
    └── [DiverseVul dataset files]
```

## Processed Experimental Results

This repository **DOES include** sanitized experimental results and analysis data for reproducibility and peer review:

### artifacts/paper_release_data/

Contains processed results, metrics, and sanitized data tables:

- `per_dataset/` - Per-dataset performance metrics
- `metrics/` - Aggregated evaluation metrics
- `calibrated_fusion/` - Calibrated fusion results
- `llm_verification/` - LLM verdict statistics
- `tables/` - Paper-ready tables (CSV format)
- `figures_data/` - Data underlying paper figures
- `scripts/` - Analysis scripts for generating tables and figures
- `README.md` - Detailed description of included data
- `DATA_DICTIONARY.md` - Schema and column descriptions
- `REPRODUCIBILITY.md` - How to reproduce these results

**These files are safe to share** because they:
1. Contain only aggregated statistics, not raw source code
2. Have been sanitized to remove any sensitive information
3. Are intended for peer review and reproducibility verification
4. Are under 50MB total

## External Dependencies Not Included

### CodeQL CLI

**What:** Static analysis engine for C/C++ vulnerability detection

**Why not included:** Binary is ~500MB and redistributable under separate license

**Download:** https://github.com/github/codeql-cli-binaries/releases

**Installation:**
```bash
cd /path/to/SemVulGuard
wget https://github.com/github/codeql-cli-binaries/releases/download/v2.15.0/codeql-linux64.zip
unzip codeql-linux64.zip
export PATH="$PATH:$(pwd)/codeql-linux64/codeql"
```

See `REPRODUCING_EXPERIMENTS.md` for detailed setup instructions.

### Joern

**What:** Code analysis platform for extracting code property graphs

**Why not included:** External tool with its own installation process

**Download:** https://github.com/joernio/joern

**Installation:** Follow the official Joern installation guide

## API Keys and Secrets

**DeepSeek API Key:** Required for LLM-based vulnerability verification

SemVulGuard uses the DeepSeek API for LLM verification. You must obtain your own API key:

1. Register at https://platform.deepseek.com/
2. Generate an API key
3. Set the environment variable:
   ```bash
   export DEEPSEEK_API_KEY="your-api-key-here"
   ```

**⚠️ NEVER commit API keys to the repository.** Always use environment variables.

## Data Privacy and Ethics

- All datasets used are public and have been published in peer-reviewed venues
- No proprietary or confidential code is included
- Vulnerability information comes from publicly disclosed CVEs
- We follow responsible disclosure practices
- No personal information is collected or stored

## Licensing and Attribution

- **SemVulGuard code:** See LICENSE file in repository root
- **Raw datasets:** Subject to their original licenses (see official repositories)
- **Paper release data:** Same license as SemVulGuard code

When using SemVulGuard or the paper release data, please cite:

```
[Citation information to be added upon publication]
```

When using the raw datasets, please also cite the original papers:
- Devign: Zhou et al., NeurIPS 2019
- BigVul: Fan et al., ACM CCS 2021  
- DiverseVul: Chen et al., RAID 2023

## Questions or Issues

If you have questions about data availability or encounter issues accessing datasets:

1. Check the official repositories first
2. Refer to `REPRODUCING_EXPERIMENTS.md` for detailed setup
3. Open an issue on our GitHub repository
4. Contact the authors (see README.md for contact information)
