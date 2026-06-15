# License and Attribution Note

**Package**: SemVulGuard Paper Release Data  
**Version**: 1.0  
**Date**: 2026-06-15

---

## Dataset Licensing

This package contains **derived experimental results** from publicly available vulnerability detection datasets. **Raw dataset files are NOT included** in this package.

### Original Datasets

1. **Devign**
   - Authors: Zhou et al.
   - Paper: "Devign: Effective Vulnerability Identification by Learning Comprehensive Program Semantics via Graph Neural Networks"
   - Source: https://sites.google.com/view/devign
   - License: Check original repository for license terms
   - **Note**: Users must download Devign from the official source

2. **BigVul**
   - Authors: Fan et al.
   - Paper: "A C/C++ Code Vulnerability Dataset with Code Changes and CVE Summaries"
   - Source: https://github.com/ZeoVan/MSR_20_Code_vulnerability_CSV_Dataset
   - License: Check original repository for license terms
   - **Note**: Users must download BigVul from the official source

3. **DiverseVul**
   - Authors: Chen et al.
   - Paper: "DiverseVul: A New Vulnerable Source Code Dataset for Deep Learning Based Vulnerability Detection"
   - Source: https://github.com/wagner-group/diversevul
   - License: Check original repository for license terms
   - **Note**: Users must download DiverseVul from the official source

**Important**: If you use any of these datasets in your research, you MUST cite the original papers and respect their licensing terms.

---

## This Package License

The **derived data** (metrics, rankings, LLM verdicts, analysis results) and **scripts** in this package are provided for:

- **Paper review and evaluation**
- **Research reproducibility**
- **Educational purposes**

### What You Can Do

✅ Use the data to review the SemVulGuard paper  
✅ Reproduce the reported results  
✅ Compare with your own methods  
✅ Cite the SemVulGuard paper if you use this data  
✅ Download original datasets from their official sources

### What You Cannot Do

❌ Redistribute raw dataset code (not included anyway)  
❌ Claim this data as your own  
❌ Use for commercial purposes without permission  
❌ Violate original dataset licenses

---

## Data Sanitization

To respect dataset licenses and privacy, this package has been sanitized:

**Excluded**:
- Raw function code from original datasets
- Full LLM evidence text (may contain code snippets)
- API keys and credentials
- Local file system paths

**Included**:
- Sample IDs and labels
- Derived metrics (precision, recall, F1, MCC, AUC)
- Rank scores and rankings
- LLM verdict metadata (verdict, confidence, predicted CWE)
- Static alert counts and CWE/query IDs
- Cost logs and execution times

---

## Third-Party Tools

This work uses the following tools:

1. **CodeQL**
   - Provider: GitHub
   - License: Check CodeQL license terms
   - Used for static analysis

2. **DeepSeek API**
   - Provider: DeepSeek AI
   - Used for LLM verification
   - API costs reported in this package

3. **scikit-learn**
   - License: BSD 3-Clause
   - Used for ML ranker

---

## Citations

### If you use this data package, please cite:

```bibtex
@article{semvulguard2026,
  title={SemVulGuard: Static-Analysis-Grounded Vulnerability Detection with Code Representation Learning and LLM-Based Semantic Verification},
  author={[Authors]},
  journal={[Venue]},
  year={2026}
}
```

### You MUST also cite the original datasets you use:

**Devign**:
```bibtex
@inproceedings{zhou2019devign,
  title={Devign: Effective vulnerability identification by learning comprehensive program semantics via graph neural networks},
  author={Zhou, Yaqin and Liu, Shangqing and Siow, Jingkai and Du, Xiaoning and Liu, Yang},
  booktitle={NeurIPS},
  year={2019}
}
```

**BigVul**:
```bibtex
@inproceedings{fan2020msr,
  title={A C/C++ Code Vulnerability Dataset with Code Changes and CVE Summaries},
  author={Fan, Jiahao and Li, Yi and Wang, Shaohua and Nguyen, Tien N},
  booktitle={MSR},
  year={2020}
}
```

**DiverseVul**:
```bibtex
@article{chen2023diversevul,
  title={DiverseVul: A New Vulnerable Source Code Dataset for Deep Learning Based Vulnerability Detection},
  author={Chen, Yizheng and Ahmadi, Zhoujun and Tsang, Rui and Wagner, David},
  journal={arXiv preprint arXiv:2304.00409},
  year={2023}
}
```

---

## Disclaimer

This data package is provided "as is" without warranty of any kind. The authors are not responsible for any consequences arising from the use of this data.

**Experimental Results**: All results are from controlled experiments and may vary if reproduced with different settings or newer tool versions.

**Dataset Licenses**: Users are responsible for complying with the original dataset licenses when downloading and using the source datasets.

**No Secrets Included**: This package has been checked for API keys and credentials. No secrets should be present. If you find any, please report immediately.

---

## Contact

For licensing questions:
- Check original dataset repositories for their specific terms
- Contact SemVulGuard authors for questions about derived data in this package

For data questions:
- See `README.md` for package structure
- See `DATA_DICTIONARY.md` for column definitions
- See `REPRODUCIBILITY.md` for methodology

---

## Acknowledgments

We thank the authors of Devign, BigVul, and DiverseVul for making their datasets publicly available, which enabled this research.

---

**License Status**: Derived data provided for research review  
**Original Datasets**: Users must download from official sources  
**Sanitization**: Raw code excluded, metrics included  
**Attribution**: Cite SemVulGuard paper + original dataset papers

