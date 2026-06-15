#!/usr/bin/env python3
"""
Generate all paper-ready figures for SemVulGuard.

This script reads CSV data from paper_figures_data/ and generates
publication-ready figures in PNG (300 DPI), PDF, and SVG formats.
"""

import os
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

# Publication-ready matplotlib settings
plt.rcParams['font.size'] = 11
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['axes.titlesize'] = 13
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 10
plt.rcParams['figure.titlesize'] = 14
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans', 'Helvetica']

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "paper_figures_data"
OUTPUT_DIR = BASE_DIR / "paper_figures"

# Create output directory
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def load_csv(filename):
    """Load CSV file and return list of dictionaries"""
    filepath = DATA_DIR / filename
    with open(filepath, 'r') as f:
        return list(csv.DictReader(f))

def save_figure(fig, filename_base):
    """Save figure in PNG (300 DPI), PDF, and SVG formats"""
    for ext in ['png', 'pdf', 'svg']:
        filepath = OUTPUT_DIR / f"{filename_base}.{ext}"
        if ext == 'png':
            fig.savefig(filepath, dpi=300, bbox_inches='tight')
        else:
            fig.savefig(filepath, bbox_inches='tight')
    plt.close(fig)

def figure3_ranker_performance():
    """Figure 3: Ranker Held-Out Performance (ROC-AUC and PR-AUC)"""
    data = load_csv("ranker_roc_pr_auc.csv")

    datasets = [row['dataset'] for row in data]
    roc_auc = [float(row['roc_auc']) for row in data]
    pr_auc = [float(row['pr_auc']) for row in data]

    x = np.arange(len(datasets))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    bars1 = ax.bar(x - width/2, roc_auc, width, label='ROC-AUC', color='#2196F3', edgecolor='black', linewidth=0.8)
    bars2 = ax.bar(x + width/2, pr_auc, width, label='PR-AUC', color='#FF9800', edgecolor='black', linewidth=0.8)

    ax.set_xlabel('Dataset')
    ax.set_ylabel('AUC Score')
    ax.set_title('Ranker Performance on Held-Out Test Sets')
    ax.set_xticks(x)
    ax.set_xticklabels([d.capitalize() for d in datasets])
    ax.legend()
    ax.set_ylim(0, 1.0)
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.3f}',
                   ha='center', va='bottom', fontsize=9)

    save_figure(fig, "fig3_ranker_roc_pr_auc")
    print("✓ Figure 3: Ranker ROC-AUC and PR-AUC")

def figure4_topk_precision_gain():
    """Figure 4: LLM Top-K Precision Gain"""
    data = load_csv("topk_precision_gain.csv")

    # Group by dataset
    datasets = {}
    for row in data:
        ds = row['dataset']
        if ds not in datasets:
            datasets[ds] = {'k': [], 'gain': []}
        datasets[ds]['k'].append(int(row['k']))
        datasets[ds]['gain'].append(float(row['precision_gain']))

    fig, ax = plt.subplots(figsize=(10, 6))

    colors = {'devign': '#4CAF50', 'bigvul': '#2196F3', 'diversevul': '#FF9800'}
    markers = {'devign': 'o', 'bigvul': 's', 'diversevul': '^'}

    for ds_name, ds_data in datasets.items():
        ax.plot(ds_data['k'], ds_data['gain'],
               marker=markers[ds_name],
               linewidth=2,
               markersize=8,
               label=ds_name.capitalize(),
               color=colors[ds_name])

    ax.axhline(y=0, color='red', linestyle='--', linewidth=1, alpha=0.5, label='No improvement')
    ax.set_xlabel('Top-K')
    ax.set_ylabel('Precision Gain over Ranker')
    ax.set_title('LLM Top-K Candidate Precision Improvement')
    ax.legend()
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_xticks([10, 30, 50])

    save_figure(fig, "fig4_topk_precision_gain")
    print("✓ Figure 4: Top-K Precision Gain")

def figure5_llm_verdict_distribution():
    """Figure 5: DeepSeek Verdict Distribution"""
    data = load_csv("llm_verdict_distribution.csv")

    # Group by dataset
    datasets = {}
    for row in data:
        ds = row['dataset']
        if ds not in datasets:
            datasets[ds] = {'vulnerable': 0, 'benign': 0, 'uncertain': 0}
        datasets[ds][row['verdict_type']] = int(row['count'])

    dataset_names = list(datasets.keys())
    vulnerable = [datasets[ds]['vulnerable'] for ds in dataset_names]
    benign = [datasets[ds]['benign'] for ds in dataset_names]
    uncertain = [datasets[ds]['uncertain'] for ds in dataset_names]

    x = np.arange(len(dataset_names))
    width = 0.25

    fig, ax = plt.subplots(figsize=(10, 6))
    bars1 = ax.bar(x - width, vulnerable, width, label='Vulnerable', color='#F44336', edgecolor='black', linewidth=0.8)
    bars2 = ax.bar(x, benign, width, label='Benign', color='#4CAF50', edgecolor='black', linewidth=0.8)
    bars3 = ax.bar(x + width, uncertain, width, label='Uncertain', color='#FFC107', edgecolor='black', linewidth=0.8)

    ax.set_xlabel('Dataset')
    ax.set_ylabel('Count (out of 50)')
    ax.set_title('DeepSeek LLM Verdict Distribution (Top-50 Candidates)')
    ax.set_xticks(x)
    ax.set_xticklabels([d.capitalize() for d in dataset_names])
    ax.legend()
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    # Add value labels
    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height)}',
                   ha='center', va='bottom', fontsize=9)

    save_figure(fig, "fig5_llm_verdict_distribution")
    print("✓ Figure 5: LLM Verdict Distribution")

def figure6_codeql_coverage():
    """Figure 6: CodeQL Static Evidence Coverage"""
    data = load_csv("codeql_coverage.csv")

    datasets = [row['dataset'] for row in data]
    coverage = [float(row['coverage_percent']) for row in data]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(datasets, coverage, color='#9C27B0', edgecolor='black', linewidth=0.8)

    ax.set_xlabel('Dataset')
    ax.set_ylabel('Coverage (%)')
    ax.set_title('CodeQL Static Analysis Coverage (Function-Level Evaluation)')
    ax.set_xticklabels([d.capitalize() for d in datasets])
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_ylim(0, max(coverage) * 1.3)

    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{height:.1f}%',
               ha='center', va='bottom', fontsize=10)

    save_figure(fig, "fig6_codeql_coverage")
    print("✓ Figure 6: CodeQL Coverage")

def figure7_cost_analysis():
    """Figure 7: Real API Cost Analysis"""
    data = load_csv("cost_analysis.csv")

    components = [row['component'] for row in data]
    costs = [float(row['total_cost_usd']) for row in data]

    # Color by component type
    colors_map = {
        'codeql': '#9C27B0',
        'ranker': '#4CAF50',
        'llm_deepseek': '#2196F3',
        'total': '#FF5722'
    }
    colors = [colors_map.get(c, '#607D8B') for c in components]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(components, costs, color=colors, edgecolor='black', linewidth=0.8)

    ax.set_xlabel('Component')
    ax.set_ylabel('Total Cost (USD)')
    ax.set_title('Real API Cost Analysis (3,000 Test Samples)')
    ax.set_xticklabels(['CodeQL', 'Ranker', 'LLM\nDeepSeek', 'Total'])
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    # Add value labels
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'${height:.3f}',
                   ha='center', va='bottom', fontsize=10)
        else:
            ax.text(bar.get_x() + bar.get_width()/2., 0.001,
                   '$0.00',
                   ha='center', va='bottom', fontsize=10)

    save_figure(fig, "fig7_cost_analysis")
    print("✓ Figure 7: Cost Analysis")

def figure8_calibrated_fusion_delta():
    """Figure 8: Calibrated Fusion Delta (Minimal Gains)"""
    data = load_csv("calibrated_fusion_delta.csv")

    # Group by dataset and metric
    datasets = {}
    for row in data:
        ds = row['dataset']
        if ds not in datasets:
            datasets[ds] = {}
        datasets[ds][row['metric']] = float(row['delta'])

    dataset_names = list(datasets.keys())
    f1_deltas = [datasets[ds]['f1'] for ds in dataset_names]
    mcc_deltas = [datasets[ds]['mcc'] for ds in dataset_names]

    x = np.arange(len(dataset_names))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    bars1 = ax.bar(x - width/2, f1_deltas, width, label='F1 Δ', color='#2196F3', edgecolor='black', linewidth=0.8)
    bars2 = ax.bar(x + width/2, mcc_deltas, width, label='MCC Δ', color='#FF9800', edgecolor='black', linewidth=0.8)

    ax.axhline(y=0, color='red', linestyle='--', linewidth=1, alpha=0.5)
    ax.set_xlabel('Dataset')
    ax.set_ylabel('Metric Improvement (Δ)')
    ax.set_title('Calibrated Fusion: Minimal Whole-Corpus Gains')
    ax.set_xticks(x)
    ax.set_xticklabels([d.capitalize() for d in dataset_names])
    ax.legend()
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:+.4f}',
                   ha='center', va='bottom' if height >= 0 else 'top', fontsize=9)

    save_figure(fig, "fig8_calibrated_fusion_delta")
    print("✓ Figure 8: Calibrated Fusion Delta")

def main():
    """Generate all figures"""
    print("Generating SemVulGuard Paper Figures...")
    print("=" * 50)

    # Check data directory exists
    if not DATA_DIR.exists():
        print(f"Error: Data directory not found: {DATA_DIR}")
        return

    # Generate all figures
    figure3_ranker_performance()
    figure4_topk_precision_gain()
    figure5_llm_verdict_distribution()
    figure6_codeql_coverage()
    figure7_cost_analysis()
    figure8_calibrated_fusion_delta()

    print("=" * 50)
    print(f"✓ All figures generated successfully!")
    print(f"✓ Output directory: {OUTPUT_DIR}")
    print(f"✓ Formats: PNG (300 DPI), PDF, SVG")
    print(f"✓ Total files: {len(list(OUTPUT_DIR.glob('fig*.png')))} figures × 3 formats")

if __name__ == '__main__':
    main()
