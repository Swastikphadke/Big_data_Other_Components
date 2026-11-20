"""Shared matplotlib styling for all report charts (print / light mode)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Reference categorical palette (validated order) + text/surface tokens
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
SERIES = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED]
CRITICAL, WARNING, GOOD = "#d03b3b", "#fab219", "#0ca30c"   # status colours (alerts only)
TEXT, TEXT2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#ffffff"


def apply():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "font.family": "DejaVu Sans", "font.size": 10,
        "axes.edgecolor": GRID, "axes.labelcolor": TEXT2, "axes.titlecolor": TEXT,
        "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.axisbelow": True, "xtick.color": TEXT2, "ytick.color": TEXT2,
        "legend.frameon": False, "lines.linewidth": 2,
    })


def save(fig, path, source_note=None):
    """Save figure; optional footnote naming the data source (traceability)."""
    if source_note:
        fig.text(0.01, 0.005, source_note, fontsize=7.5, color=MUTED, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.03 if source_note else 0, 1, 1))
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print("saved", path)
