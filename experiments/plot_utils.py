"""plot_utils.py: Standardized scientific styling, publication layout, and high-DPI saving for Q-SAT experiments."""

from pathlib import Path
from typing import Optional
import matplotlib.pyplot as plt
import seaborn as sns

# Set scientific publication style
sns.set_theme(style="whitegrid", font="sans-serif")
plt.rcParams.update({
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.titlesize": 14,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight"
})

# Curated palette for aerospace & quantum optics figures
PALETTE = {
    "primary": "#0284c7",    # Sky Blue
    "secondary": "#059669",  # Emerald Green
    "accent": "#d97706",     # Amber
    "danger": "#dc2626",     # Red
    "purple": "#7c3aed",     # Violet
    "neutral": "#475569",    # Slate
    # Semantic aliases
    "skr": "#059669",
    "qber": "#dc2626",
    "loss": "#d97706",
    "power": "#0284c7",
    "elevation": "#7c3aed"
}


def create_figure(
    nrows: int = 1,
    ncols: int = 1,
    figsize: Optional[tuple] = None,
    title: Optional[str] = None,
    xlabel: Optional[str] = None,
    ylabel: Optional[str] = None
):
    """Create a standardized Matplotlib figure with subplots."""
    if figsize is None:
        figsize = (6.5 * ncols, 4.5 * nrows)
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=figsize)
    if nrows == 1 and ncols == 1:
        if title:
            axes.set_title(title, fontsize=12, pad=10, weight="bold")
        if xlabel:
            axes.set_xlabel(xlabel)
        if ylabel:
            axes.set_ylabel(ylabel)
    return fig, axes


def save_figure(fig, output_path: Path, filename: Optional[str] = None):
    """Save high-resolution publication-quality figure to disk."""
    if filename is None:
        full_path = Path(output_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        full_path = Path(output_path) / filename
        full_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(full_path)
    plt.close(fig)
    print(f"  [SAVED FIGURE] {full_path}")
    return full_path
