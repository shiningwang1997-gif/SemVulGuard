# GitHub Upload Checklist

This document provides a safety checklist before uploading SemVulGuard to GitHub.

## ✅ Safe to Upload

The following directories and files are safe and ready for GitHub:

- `semvulguard/` - Core source code
- `scripts/` - Utility and experiment scripts
- `configs/` - Configuration files
- `tests/` - Test suite
- `reports/` - Report templates (empty directory with .gitkeep)
- `paper/` - Paper-facing tables, figures, and documentation
- `artifacts/paper_release_data/` - Sanitized experimental results for reviewers
- `pyproject.toml` - Project metadata
- `requirements.txt` - Core dependencies
- `requirements-dev.txt` - Development dependencies
- `requirements-eval.txt` - Evaluation dependencies
- `requirements-models.txt` - Model-specific dependencies
- `README.md` - Project documentation
- `GITHUB_UPLOAD_CHECKLIST.md` (this file)
- `DATA_AVAILABILITY.md` - Dataset availability notes
- `REPRODUCING_EXPERIMENTS.md` - Experiment reproduction guide
- `.gitignore` - Git ignore rules

## ❌ Must NOT Upload

The following directories contain raw data, binaries, or machine-specific artifacts and should **never** be uploaded:

- `codeql-linux64/` - CodeQL binary (users must download separately)
- `experiment/` - Raw third-party datasets (Devign, BigVul, DiverseVul)
- `artifacts/experiments/` - Large experimental artifacts (generated locally)
- `artifacts/joern/` - Joern analysis outputs (generated locally)
- `artifacts/real_llm/` - LLM verification artifacts (generated locally)
- `artifacts/codeql_*/` - CodeQL database files (generated locally)
- `__pycache__/` - Python bytecode cache
- `.pytest_cache/` - Pytest cache
- `.mypy_cache/` - MyPy type checking cache
- `.ruff_cache/` - Ruff linter cache
- `.venv/`, `venv/`, `env/` - Virtual environments
- `.env` - Environment variables and API keys
- `*.pyc` - Compiled Python files
- `*.db`, `*.sqlite` - Database files
- `*.sarif` - CodeQL analysis results
- `*.zip`, `*.tar.gz` - Compressed archives
- `*.log` - Log files
- Model checkpoints (`*.pt`, `*.pth`, `*.ckpt`)

## 🔍 Pre-Upload Verification

Run these checks before uploading:

### 1. Check for Python cache files
```bash
find . -name "__pycache__" -type d
find . -name "*.pyc"
```
Result: Should return nothing or only files already in .gitignore.

### 2. Check for secrets and API keys
```bash
grep -r "DEEPSEEK_API_KEY" . --exclude-dir=.git --exclude-dir=.venv
grep -r "API_KEY" . --exclude-dir=.git --exclude-dir=.venv
grep -r "SECRET" . --exclude-dir=.git --exclude-dir=.venv
```
Result: Should only find references in documentation, not actual key values.

### 3. Check for old project names
```bash
grep -r "LLM-VulMiner" . --exclude-dir=.git --exclude-dir=.venv
grep -r "llmvulminer" . --exclude-dir=.git --exclude-dir=.venv
grep -r "llm_vulminer" . --exclude-dir=.git --exclude-dir=.venv
```
Result: Should return no results (all references should be updated to SemVulGuard).

### 4. Check file sizes
```bash
find . -type f -size +50M ! -path "./.git/*" ! -path "./.venv/*" ! -path "./codeql-linux64/*" ! -path "./experiment/*" ! -path "./artifacts/experiments/*"
```
Result: Large files should be either excluded by .gitignore or explicitly intended for release.

### 5. Verify .gitignore coverage
```bash
git status --ignored
```
Result: Ensure all excluded directories are properly ignored.

### 6. Verify artifacts/paper_release_data
```bash
du -sh artifacts/paper_release_data/
ls -lh artifacts/paper_release_data/
```
Result: Should be under 50MB total and contain only sanitized CSVs and documentation.

## 🔐 Secrets Verification

Before uploading, verify that:

1. ✅ No `.env` files are present
2. ✅ No API keys are hardcoded in source code
3. ✅ No private keys or credentials are included
4. ✅ No absolute paths specific to your machine (e.g., `/home/wangxiaoning/`)
5. ✅ Configuration files use environment variables or placeholders for secrets

## 📋 Final Checklist

Before running `git push`:

- [ ] Reviewed `git status` and confirmed no excluded files are staged
- [ ] Ran all verification commands above
- [ ] Confirmed no secrets in commit history
- [ ] Verified README.md is up to date
- [ ] Confirmed all paper release data is sanitized
- [ ] Tested that .gitignore properly excludes large artifacts
- [ ] Removed any TODO comments with sensitive information
- [ ] Checked that experiments can be reproduced from instructions

## 🚀 Upload Command Sequence

```bash
cd /path/to/SemVulGuard/SemVulGuard  # Enter the GitHub root
git init
git add .
git status  # Review what will be committed
git commit -m "Initial commit: SemVulGuard"
git remote add origin <your-github-repo-url>
git push -u origin main
```

## ⚠️ If You Find Issues

If any verification step fails:

1. **DO NOT push** to GitHub yet
2. Fix the issue (add to .gitignore, remove files, sanitize data)
3. Re-run all verification steps
4. Only push when all checks pass
