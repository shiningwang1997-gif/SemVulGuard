#!/usr/bin/env python3
"""
SemVulGuard Paper Release Data Verification Script

Verifies the integrity and correctness of the paper release data package.
"""

import os
import csv
import sys
import re

RELEASE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def check_file_exists(filepath, desc):
    """Check if a file exists."""
    if os.path.exists(filepath):
        print(f"  ✓ {desc}")
        return True
    else:
        print(f"  ✗ MISSING: {desc}")
        return False

def check_csv_rows(filepath, expected_min_rows, desc):
    """Check if CSV has minimum number of rows."""
    try:
        with open(filepath, 'r') as f:
            row_count = sum(1 for line in f) - 1  # Exclude header
        if row_count >= expected_min_rows:
            print(f"  ✓ {desc}: {row_count} rows")
            return True
        else:
            print(f"  ✗ {desc}: Expected >= {expected_min_rows}, got {row_count}")
            return False
    except Exception as e:
        print(f"  ✗ Error reading {desc}: {e}")
        return False

def verify_verdict_distribution():
    """Verify corrected LLM verdict distribution."""
    print("\n[Verification] LLM Verdict Distribution (Critical)")
    filepath = os.path.join(RELEASE_ROOT, "metrics/llm_verdict_distribution.csv")

    expected = {
        'devign': {'vulnerable': 14, 'benign': 23, 'uncertain': 13},
        'bigvul': {'vulnerable': 8, 'benign': 33, 'uncertain': 9},
        'diversevul': {'vulnerable': 7, 'benign': 31, 'uncertain': 12},
    }

    try:
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                dataset = row['Dataset'].lower()
                if dataset in expected:
                    vuln = int(row['Vulnerable'])
                    benign = int(row['Benign'])
                    uncertain = int(row['Uncertain'])

                    exp = expected[dataset]
                    if vuln == exp['vulnerable'] and benign == exp['benign'] and uncertain == exp['uncertain']:
                        print(f"  ✓ {dataset}: {vuln}/{benign}/{uncertain} (CORRECT)")
                    else:
                        print(f"  ✗ {dataset}: Expected {exp['vulnerable']}/{exp['benign']}/{exp['uncertain']}, got {vuln}/{benign}/{uncertain}")
                        return False
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def verify_policy_count():
    """Verify corrected policy count."""
    print("\n[Verification] Policy Evaluation Count")
    filepath = os.path.join(RELEASE_ROOT, "tables/table7_policy_comparison_summary.csv")

    try:
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['Policy'] == 'Total':
                    count = int(row['Grid_Size'])
                    if count == 1533:
                        print(f"  ✓ Policy count: 1533 (CORRECT)")
                        return True
                    else:
                        print(f"  ✗ Policy count: Expected 1533, got {count}")
                        return False
        print(f"  ✗ Total row not found")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def check_for_secrets():
    """Check for potential secrets or API keys."""
    print("\n[Security] Checking for potential secrets...")

    patterns = [
        (r'sk-[a-zA-Z0-9]{20,}', 'OpenAI API key'),
        (r'AKIA[0-9A-Z]{16}', 'AWS Access Key'),
        (r'ghp_[a-zA-Z0-9]{36}', 'GitHub Token'),
        (r'password\s*=\s*["\'][^"\']+["\']', 'Password in config'),
    ]

    issues = []
    for root, dirs, files in os.walk(RELEASE_ROOT):
        for file in files:
            if file.endswith(('.csv', '.md', '.py', '.json')):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        for pattern, desc in patterns:
                            if re.search(pattern, content, re.IGNORECASE):
                                issues.append(f"{file}: Potential {desc}")
                except:
                    pass

    if issues:
        print(f"  ⚠ Potential secrets found:")
        for issue in issues:
            print(f"    - {issue}")
        return False
    else:
        print(f"  ✓ No obvious secrets detected")
        return True

def main():
    print("=" * 80)
    print("SemVulGuard Paper Release Data Verification")
    print("=" * 80)

    all_passed = True

    # Check required directories
    print("\n[Structure] Checking directory structure...")
    dirs = ['tables', 'figures_data', 'metrics', 'per_dataset', 'llm_verification', 'calibrated_fusion', 'scripts']
    for d in dirs:
        path = os.path.join(RELEASE_ROOT, d)
        if os.path.isdir(path):
            print(f"  ✓ {d}/")
        else:
            print(f"  ✗ MISSING: {d}/")
            all_passed = False

    # Check required files
    print("\n[Files] Checking required files...")
    required_files = [
        ('README.md', 'README'),
        ('DATA_DICTIONARY.md', 'Data Dictionary'),
        ('REPRODUCIBILITY.md', 'Reproducibility Guide'),
        ('LICENSE_NOTE.md', 'License Note'),
    ]
    for filename, desc in required_files:
        all_passed &= check_file_exists(os.path.join(RELEASE_ROOT, filename), desc)

    # Check table CSVs
    print("\n[Tables] Checking table CSVs...")
    tables = [
        ('table1_dataset_statistics.csv', 3),
        ('table2_ranker_performance.csv', 3),
        ('table3_codeql_coverage.csv', 3),
        ('table4_deepseek_verdict_distribution.csv', 3),
        ('table6_calibrated_fusion_vs_ranker.csv', 3),
        ('table7_policy_comparison_summary.csv', 4),
        ('table8_cost_analysis.csv', 3),
    ]
    for filename, min_rows in tables:
        path = os.path.join(RELEASE_ROOT, 'tables', filename)
        all_passed &= check_csv_rows(path, min_rows, filename)

    # Check figure data CSVs
    print("\n[Figures] Checking figure data CSVs...")
    fig_csvs = [
        'ranker_roc_pr_auc.csv',
        'codeql_coverage.csv',
        'cost_analysis.csv',
        'calibrated_fusion_delta.csv',
        'topk_precision_gain.csv',
        'llm_verdict_distribution.csv',
    ]
    for filename in fig_csvs:
        path = os.path.join(RELEASE_ROOT, 'figures_data', filename)
        all_passed &= check_file_exists(path, filename)

    # Verify corrected values
    all_passed &= verify_verdict_distribution()
    all_passed &= verify_policy_count()

    # Security check
    all_passed &= check_for_secrets()

    # Summary
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ VERIFICATION PASSED")
        print("=" * 80)
        print("\nThe release package is ready for reviewer sharing.")
        return 0
    else:
        print("❌ VERIFICATION FAILED")
        print("=" * 80)
        print("\nPlease fix the issues above before sharing.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
