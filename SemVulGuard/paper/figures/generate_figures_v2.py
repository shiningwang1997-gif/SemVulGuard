#!/usr/bin/env python3
"""
SemVulGuard Paper Figures Generator
Generates publication-ready figures from verified CSV data files.

Color Palette (Yellow-Green-Blue):
- Blue (#4C78A8): Ranker / baseline / core performance
- Green (#59A14F): LLM-enhanced / positive gain / improved
- Yellow (#F2CF5B): Static analysis / CodeQL / cautionary
- Teal (#76B7B2): Uncertain / mixed / neutral
- Dark Blue (#2F5D8A): Secondary blue for comparisons

Generated: 2026-06-15
Status: Post-audit, using corrected data
"""

import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path

# ============================================================================
# UNIFIED COLOR PALETTE (Yellow-Green-Blue Theme)
# ============================================================================

COLORS = {
    'blue': '#4C78A8',           # Primary blue - ranker/baseline
    'green': '#59A14F',          # Primary green - LLM/improved
    'yellow': '#F2CF5B',         # Primary yellow - static/caution
    'teal': '#76B7B2',           # Teal - uncertain/neutral
    'dark_blue': '#2F5D8A',      # Dark blue - secondary
    'gray': '#7F7F7F',           # Gray - auxiliary
    'light_gray': '#CCCCCC',     # Light gray - background
}

# Semantic color mappings (consistent across figures)
SEMANTIC_COLORS = {
    # Performance metrics
    'ranker': COLORS['blue'],
    'llm': COLORS['green'],
    'static': COLORS['yellow'],
    'fusion': COLORS['teal'],

    # Verdicts
    'vulnerable': COLORS['green'],  # Positive finding
    'benign': COLORS['blue'],       # Negative finding
    'uncertain': COLORS['yellow'],  # Uncertain/caution

    # Metrics
    'roc_auc': COLORS['blue'],
    'pr_auc': COLORS['green'],
    'f1': COLORS['blue'],
    'mcc': COLORS['green'],

    # Gains
    'positive_gain': COLORS['green'],
    'negative_gain': COLORS['blue'],
    'neutral': COLORS['yellow'],
}

# Dataset colors (for multi-dataset plots)
DATASET_COLORS = {
    'devign': COLORS['blue'],
    'bigvul': COLORS['green'],
    'diversevul': COLORS['yellow'],
}

# ============================================================================
# CONFIGURATION
# ============================================================================

# Figure settings
DPI = 300
FIGURE_FORMATS = ['png', 'pdf', 'svg']
FIGURE_SIZE_SINGLE = (8, 6)
FIGURE_SIZE_DOUBLE = (10, 6)
FIGURE_SIZE_WIDE = (12, 5)

# Font settings
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans', 'Helvetica']
plt.rcParams['font.size'] = 11
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 10
plt.rcParams['figure.titlesize'] = 14

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def ensure_dir(path):
    """Create directory if it doesn't exist."""
    Path(path).mkdir(parents=True, exist_ok=True)

def save_figure(fig, output_dir, filename_base):
    """Save figure in multiple formats."""
    ensure_dir(output_dir)
    paths = []
    for fmt in FIGURE_FORMATS:
        filepath = os.path.join(output_dir, f"{filename_base}.{fmt}")
        fig.savefig(filepath, format=fmt, dpi=DPI, bbox_inches='tight')
        paths.append(filepath)
        print(f"  ✓ Saved: {os.path.basename(filepath)}")
    return paths

def format_dataset_name(name):
    """Format dataset name for display."""
    name_map = {
        'devign': 'Devign',
        'bigvul': 'BigVul',
        'diversevul': 'DiverseVul'
    }
    return name_map.get(name.lower(), name)

# ============================================================================
# FIGURE 1: RANKER ROC-AUC AND PR-AUC PERFORMANCE
# ============================================================================

def generate_ranker_performance(data_dir, output_dir):
    """Generate ranker performance comparison figure."""
    print("\n[Figure 1] Generating ranker performance...")

    # Read data
    df = pd.read_csv(os.path.join(data_dir, 'ranker_roc_pr_auc.csv'))
    df['dataset_display'] = df['dataset'].apply(format_dataset_name)

    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=FIGURE_SIZE_DOUBLE)

    datasets = df['dataset_display'].tolist()
    x = np.arange(len(datasets))
    width = 0.35

    # Left subplot: ROC-AUC and PR-AUC
    ax1 = axes[0]
    bars1 = ax1.bar(x - width/2, df['roc_auc'], width,
                    label='ROC-AUC', color=SEMANTIC_COLORS['roc_auc'],
                    edgecolor='black', linewidth=0.5)
    bars2 = ax1.bar(x + width/2, df['pr_auc'], width,
                    label='PR-AUC', color=SEMANTIC_COLORS['pr_auc'],
                    edgecolor='black', linewidth=0.5)

    ax1.set_xlabel('Dataset', fontweight='bold')
    ax1.set_ylabel('AUC Score', fontweight='bold')
    ax1.set_title('Ranker AUC Performance', fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(datasets)
    ax1.set_ylim(0, 1.0)
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3, linestyle='--')

    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.3f}', ha='center', va='bottom', fontsize=9)

    # Right subplot: F1 and MCC
    ax2 = axes[1]
    bars3 = ax2.bar(x - width/2, df['f1'], width,
                    label='F1', color=SEMANTIC_COLORS['f1'],
                    edgecolor='black', linewidth=0.5)
    bars4 = ax2.bar(x + width/2, df['mcc'], width,
                    label='MCC', color=SEMANTIC_COLORS['mcc'],
                    edgecolor='black', linewidth=0.5)

    ax2.set_xlabel('Dataset', fontweight='bold')
    ax2.set_ylabel('Score', fontweight='bold')
    ax2.set_title('Ranker F1 and MCC', fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(datasets)
    ax2.set_ylim(0, 0.8)
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3, linestyle='--')

    # Add value labels
    for bars in [bars3, bars4]:
        for bar in bars:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.3f}', ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    return save_figure(fig, output_dir, 'fig1_ranker_performance')

# ============================================================================
# FIGURE 2: CODEQL STATIC ANALYSIS COVERAGE
# ============================================================================

def generate_codeql_coverage(data_dir, output_dir):
    """Generate CodeQL coverage figure."""
    print("\n[Figure 2] Generating CodeQL coverage...")

    # Read data
    df = pd.read_csv(os.path.join(data_dir, 'codeql_coverage.csv'))
    df['dataset_display'] = df['dataset'].apply(format_dataset_name)

    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=FIGURE_SIZE_DOUBLE)

    datasets = df['dataset_display'].tolist()
    x = np.arange(len(datasets))

    # Left subplot: Coverage percentage
    ax1 = axes[0]
    bars = ax1.bar(x, df['coverage_percent'], color=SEMANTIC_COLORS['static'],
                   edgecolor='black', linewidth=0.5)

    ax1.set_xlabel('Dataset', fontweight='bold')
    ax1.set_ylabel('Coverage (%)', fontweight='bold')
    ax1.set_title('CodeQL Test Set Coverage', fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(datasets)
    ax1.set_ylim(0, 2.0)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')

    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%', ha='center', va='bottom', fontsize=9)

    # Right subplot: Alert counts
    ax2 = axes[1]
    width = 0.35
    bars1 = ax2.bar(x - width/2, df['alerts_parsed'], width,
                    label='Total Alerts', color=COLORS['blue'],
                    edgecolor='black', linewidth=0.5)
    bars2 = ax2.bar(x + width/2, df['samples_with_alerts'], width,
                    label='Samples with Alerts', color=COLORS['yellow'],
                    edgecolor='black', linewidth=0.5)

    ax2.set_xlabel('Dataset', fontweight='bold')
    ax2.set_ylabel('Count', fontweight='bold')
    ax2.set_title('CodeQL Alert Distribution', fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(datasets)
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3, linestyle='--')

    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}', ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    return save_figure(fig, output_dir, 'fig2_codeql_coverage')

# ============================================================================
# FIGURE 3: COST ANALYSIS
# ============================================================================

def generate_cost_analysis(data_dir, output_dir):
    """Generate cost analysis figure."""
    print("\n[Figure 3] Generating cost analysis...")

    # Read data
    df = pd.read_csv(os.path.join(data_dir, 'cost_analysis.csv'))

    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=FIGURE_SIZE_DOUBLE)

    # Left subplot: Cost breakdown
    ax1 = axes[1]
    components = df['component'].tolist()
    costs = df['total_cost_usd'].tolist()

    # Pie chart for cost (only LLM has cost)
    llm_row = df[df['component'] == 'llm_deepseek']
    if len(llm_row) > 0:
        ax1.text(0.5, 0.5, f"LLM (DeepSeek)\n$0.125\n(100% of cost)",
                ha='center', va='center', fontsize=12, transform=ax1.transAxes,
                bbox=dict(boxstyle='round', facecolor=COLORS['green'], alpha=0.3))
        ax1.set_title('Monetary Cost Distribution', fontweight='bold')
        ax1.axis('off')

    # Right subplot: Time breakdown
    ax2 = axes[0]
    components_display = [c.replace('_', ' ').replace('llm deepseek', 'LLM DeepSeek').title()
                         for c in components if c != 'total']
    times = df[df['component'] != 'total']['time_minutes'].tolist()
    colors_list = [COLORS['yellow'], COLORS['blue'], COLORS['green']]

    bars = ax2.barh(components_display, times, color=colors_list[:len(times)],
                   edgecolor='black', linewidth=0.5)

    ax2.set_xlabel('Time (minutes)', fontweight='bold')
    ax2.set_ylabel('Component', fontweight='bold')
    ax2.set_title('Execution Time Breakdown', fontweight='bold')
    ax2.grid(axis='x', alpha=0.3, linestyle='--')

    # Add value labels
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax2.text(width, bar.get_y() + bar.get_height()/2.,
                f' {int(width)} min', ha='left', va='center', fontsize=9)

    plt.tight_layout()
    return save_figure(fig, output_dir, 'fig3_cost_analysis')

# ============================================================================
# FIGURE 4: LLM VERDICT DISTRIBUTION (CORRECTED VALUES)
# ============================================================================

def generate_verdict_distribution(data_dir, output_dir):
    """Generate LLM verdict distribution figure with corrected values."""
    print("\n[Figure 4] Generating LLM verdict distribution (CORRECTED)...")

    # Read data (using corrected CSV)
    df = pd.read_csv(os.path.join(data_dir, 'llm_verdict_distribution.csv'))

    # Verify corrected values
    print("  Verifying corrected verdict values:")
    for dataset in ['devign', 'bigvul', 'diversevul']:
        dataset_data = df[df['dataset'] == dataset]
        vuln = dataset_data[dataset_data['verdict_type'] == 'vulnerable']['count'].values[0]
        benign = dataset_data[dataset_data['verdict_type'] == 'benign']['count'].values[0]
        uncertain = dataset_data[dataset_data['verdict_type'] == 'uncertain']['count'].values[0]
        print(f"    {dataset}: vulnerable={vuln}, benign={benign}, uncertain={uncertain}")

    # Pivot for stacked bar chart
    pivot_df = df.pivot(index='dataset', columns='verdict_type', values='count')
    pivot_df = pivot_df[['vulnerable', 'benign', 'uncertain']]  # Order columns
    pivot_df['dataset_display'] = pivot_df.index.map(format_dataset_name)

    # Create figure
    fig, ax = plt.subplots(figsize=FIGURE_SIZE_SINGLE)

    datasets = pivot_df['dataset_display'].tolist()
    x = np.arange(len(datasets))
    width = 0.6

    # Stacked bars
    bottom = np.zeros(len(datasets))
    colors = [SEMANTIC_COLORS['vulnerable'], SEMANTIC_COLORS['benign'],
              SEMANTIC_COLORS['uncertain']]
    labels = ['Vulnerable', 'Benign', 'Uncertain']

    for verdict, color, label in zip(['vulnerable', 'benign', 'uncertain'], colors, labels):
        values = pivot_df[verdict].tolist()
        bars = ax.bar(x, values, width, bottom=bottom, label=label,
                     color=color, edgecolor='black', linewidth=0.5)

        # Add value labels
        for i, bar in enumerate(bars):
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., bottom[i] + height/2.,
                       f'{int(height)}', ha='center', va='center', fontsize=9,
                       fontweight='bold', color='white' if height > 5 else 'black')

        bottom += values

    ax.set_xlabel('Dataset', fontweight='bold')
    ax.set_ylabel('Number of Verdicts', fontweight='bold')
    ax.set_title('LLM Verdict Distribution (Top-50 per Dataset)', fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(datasets)
    ax.set_ylim(0, 55)
    ax.legend(loc='upper right')
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    # Add total line at y=50
    ax.axhline(y=50, color='gray', linestyle='--', linewidth=1, alpha=0.5)
    ax.text(len(datasets)-0.5, 50, ' n=50', va='center', fontsize=8, color='gray')

    plt.tight_layout()
    return save_figure(fig, output_dir, 'fig4_verdict_distribution')

# ============================================================================
# FIGURE 5: TOP-K PRECISION GAIN
# ============================================================================

def generate_topk_precision_gain(data_dir, output_dir):
    """Generate top-k precision gain figure."""
    print("\n[Figure 5] Generating top-k precision gain...")

    # Read data
    df = pd.read_csv(os.path.join(data_dir, 'topk_precision_gain.csv'))
    df['dataset_display'] = df['dataset'].apply(format_dataset_name)

    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=FIGURE_SIZE_DOUBLE)

    # Left subplot: Precision comparison
    ax1 = axes[0]
    for dataset in df['dataset'].unique():
        dataset_data = df[df['dataset'] == dataset].sort_values('k')
        dataset_display = format_dataset_name(dataset)
        color = DATASET_COLORS.get(dataset, COLORS['blue'])

        # Ranker precision
        ax1.plot(dataset_data['k'], dataset_data['ranker_precision'],
                marker='o', linestyle='--', linewidth=2, markersize=8,
                color=color, alpha=0.5, label=f'{dataset_display} (Ranker)')

        # LLM filtered precision
        ax1.plot(dataset_data['k'], dataset_data['llm_filtered_precision'],
                marker='s', linestyle='-', linewidth=2, markersize=8,
                color=color, label=f'{dataset_display} (LLM)')

    ax1.set_xlabel('Top-K', fontweight='bold')
    ax1.set_ylabel('Precision', fontweight='bold')
    ax1.set_title('Ranker vs LLM-Filtered Precision', fontweight='bold')
    ax1.set_xticks([10, 30, 50])
    ax1.set_ylim(0, 1.0)
    ax1.legend(fontsize=8, ncol=2)
    ax1.grid(True, alpha=0.3, linestyle='--')

    # Right subplot: Precision gain
    ax2 = axes[1]
    x = np.arange(3)  # k=10, 30, 50
    width = 0.25

    for i, dataset in enumerate(df['dataset'].unique()):
        dataset_data = df[df['dataset'] == dataset].sort_values('k')
        dataset_display = format_dataset_name(dataset)
        color = DATASET_COLORS.get(dataset, COLORS['blue'])

        offset = (i - 1) * width
        bars = ax2.bar(x + offset, dataset_data['precision_gain'], width,
                      label=dataset_display, color=color,
                      edgecolor='black', linewidth=0.5)

        # Add value labels
        for j, bar in enumerate(bars):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}', ha='center',
                    va='bottom' if height >= 0 else 'top', fontsize=8)

    ax2.set_xlabel('Top-K', fontweight='bold')
    ax2.set_ylabel('Precision Gain', fontweight='bold')
    ax2.set_title('LLM Precision Gain over Ranker', fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(['10', '30', '50'])
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3, linestyle='--')

    plt.tight_layout()
    return save_figure(fig, output_dir, 'fig5_topk_precision_gain')

# ============================================================================
# FIGURE 6: CALIBRATED FUSION DELTA
# ============================================================================

def generate_fusion_delta(data_dir, output_dir):
    """Generate calibrated fusion delta figure."""
    print("\n[Figure 6] Generating calibrated fusion delta...")

    # Read data
    df = pd.read_csv(os.path.join(data_dir, 'calibrated_fusion_delta.csv'))

    # Pivot for grouped bars
    pivot_df = df.pivot(index='dataset', columns='metric', values='delta')
    pivot_df['dataset_display'] = pivot_df.index.map(format_dataset_name)

    # Create figure
    fig, ax = plt.subplots(figsize=FIGURE_SIZE_SINGLE)

    datasets = pivot_df['dataset_display'].tolist()
    x = np.arange(len(datasets))
    width = 0.35

    # F1 and MCC deltas
    f1_deltas = pivot_df['F1'].tolist()
    mcc_deltas = pivot_df['MCC'].tolist()

    bars1 = ax.bar(x - width/2, f1_deltas, width, label='F1 Δ',
                   color=SEMANTIC_COLORS['f1'], edgecolor='black', linewidth=0.5)
    bars2 = ax.bar(x + width/2, mcc_deltas, width, label='MCC Δ',
                   color=SEMANTIC_COLORS['mcc'], edgecolor='black', linewidth=0.5)

    ax.set_xlabel('Dataset', fontweight='bold')
    ax.set_ylabel('Metric Improvement (Δ)', fontweight='bold')
    ax.set_title('Calibrated Fusion vs Ranker-Only (Whole Corpus)', fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(datasets)
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    ax.legend()
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.4f}', ha='center',
                   va='bottom' if height >= 0 else 'top', fontsize=8)

    # Add average annotation
    avg_f1 = np.mean(f1_deltas)
    avg_mcc = np.mean(mcc_deltas)
    ax.text(0.98, 0.98, f'Average:\nF1: {avg_f1:+.4f}\nMCC: {avg_mcc:+.4f}',
           transform=ax.transAxes, ha='right', va='top',
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3),
           fontsize=9)

    plt.tight_layout()
    return save_figure(fig, output_dir, 'fig6_fusion_delta')

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main figure generation function."""
    print("=" * 80)
    print("SemVulGuard Paper Figures Generator")
    print("=" * 80)
    print(f"Color Palette: Yellow-Green-Blue")
    print(f"  Blue:   {COLORS['blue']} (Ranker/Baseline)")
    print(f"  Green:  {COLORS['green']} (LLM/Improved)")
    print(f"  Yellow: {COLORS['yellow']} (Static/Caution)")
    print(f"  Teal:   {COLORS['teal']} (Uncertain/Neutral)")
    print("=" * 80)

    # Determine paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(os.path.dirname(script_dir), 'paper_figures_data')
    output_dir = script_dir

    print(f"\nData directory: {data_dir}")
    print(f"Output directory: {output_dir}")

    # Verify data directory exists
    if not os.path.exists(data_dir):
        print(f"\n❌ ERROR: Data directory not found: {data_dir}")
        sys.exit(1)

    # Generate all figures
    all_paths = []

    try:
        all_paths.extend(generate_ranker_performance(data_dir, output_dir))
        all_paths.extend(generate_codeql_coverage(data_dir, output_dir))
        all_paths.extend(generate_cost_analysis(data_dir, output_dir))
        all_paths.extend(generate_verdict_distribution(data_dir, output_dir))
        all_paths.extend(generate_topk_precision_gain(data_dir, output_dir))
        all_paths.extend(generate_fusion_delta(data_dir, output_dir))

        print("\n" + "=" * 80)
        print("✅ ALL FIGURES GENERATED SUCCESSFULLY")
        print("=" * 80)
        print(f"\nTotal files generated: {len(all_paths)}")
        print(f"Formats: {', '.join(FIGURE_FORMATS)}")
        print(f"Resolution: {DPI} DPI")
        print(f"\nOutput directory: {output_dir}")

        # List all generated files
        print("\nGenerated files:")
        for path in sorted(all_paths):
            print(f"  • {os.path.basename(path)}")

        return 0

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
