"""
The one description of how the article's figures look.

Every figure module in report/figures/ imports its palette, labels, markers,
sizes and matplotlib settings from here and defines none of its own, so a
change here changes every figure. The R model scripts draw nothing.

Usage:
    from report.plot_style import CONDITION_COLORS, SINGLE_COLUMN, apply_style
    apply_style()
    fig, ax = plt.subplots(figsize=SINGLE_COLUMN)
    ...
    # report.figures saves the figure beside the table it plots
"""

from __future__ import annotations

import glob
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager


# ── Conditions and groups ────────────────────────────────────

CONDITION_ORDER = ["refer_separated", "refer_mixed", "social_mixed", "social_first"]

# The two conditions with a social-identification task (H3, H4)
SOCIAL_CONDITIONS = ["social_mixed", "social_first"]

# The conditions that share the same Phase 1 procedure (H1, H2); in
# social_first the manipulation precedes Phase 1
H12_CONDITIONS = ["refer_separated", "refer_mixed", "social_mixed"]

CONDITION_LABELS = {
    "refer_separated": "Refer separated",
    "refer_mixed": "Refer mixed",
    "social_mixed": "Social mixed",
    "social_first": "Social-first",
}

# Blues for the referential conditions and oranges for the social ones, the
# darker member for the condition with less contact between groups. Chosen in
# OKLCH so that every pair of the four passes the colorblind separation,
# lightness, chroma and 3:1 contrast checks of the dataviz palette validator
# (worst pair 20 OKLab units apart under protan, deutan and tritan vision).
CONDITION_COLORS = {
    "refer_separated": "#085491",
    "refer_mixed": "#5194D5",
    "social_mixed": "#CF7347",
    "social_first": "#8A3400",
}

# A marker per condition, so identity never rests on color alone
CONDITION_MARKERS = {
    "refer_separated": "o",
    "refer_mixed": "s",
    "social_mixed": "^",
    "social_first": "D",
}

GROUP_ORDER = ["A", "B", "C"]
GROUP_COLORS = {"A": "#F8766D", "B": "#00BA38", "C": "#619CFF"}

# Within-group versus between-group pairs of descriptions
GROUP_TYPE_COLORS = {"within": "#233029", "between": "#98A29D"}
GROUP_TYPE_LABELS = {"within": "Within group", "between": "Between group"}

# The analysis windows on the pairwise similarities
WINDOW_LABELS = {
    "phase1_final": "Phase 1 final",
    "phase2_early": "Phase 2 early",
    "phase2_final": "Phase 2 final",
}

# ── Blocks ───────────────────────────────────────────────────
# Blocks are 1-indexed in every figure, as in the paper and in the `block` and
# `gameBlock` columns of the processed tables: Phase 1 is blocks 1 to 6 and
# Phase 2 is 7 to 12 on the game-block axis. Nothing here re-indexes.

PHASE1_BLOCKS = 6
PHASE2_BLOCKS = 6
GAME_BLOCKS = PHASE1_BLOCKS + PHASE2_BLOCKS
PHASE_BOUNDARY = PHASE1_BLOCKS + 0.5

# ── Marks ────────────────────────────────────────────────────

INK = "#2A3531"
MUTED = "#6B7571"
GAME_LINE = dict(color="#B6BDB9", alpha=0.6, linewidth=0.6)  # one game behind the mean
MEAN_LINE = dict(linewidth=1.8)
MARKER_SIZE = 4.5
CI_ALPHA = 0.18
REFERENCE_LINE = dict(color=MUTED, linestyle="--", linewidth=0.8)  # chance, zero

# ── Sizes, in inches ─────────────────────────────────────────

SINGLE_COLUMN = (3.5, 2.7)
DOUBLE_COLUMN = (7.2, 3.0)
DOUBLE_COLUMN_TALL = (7.2, 5.4)

FONT_FAMILY = ["Arial Nova", "Helvetica Neue", "Arial", "DejaVu Sans"]


def _register_local_fonts() -> None:
    """Make the fonts in the user's font directory known to matplotlib."""
    for pattern in ("~/Library/Fonts/ArialNova*.ttf", "~/Library/Fonts/Arial Nova*.ttf"):
        for path in glob.glob(str(Path(pattern).expanduser())):
            font_manager.fontManager.addfont(path)


def apply_style() -> None:
    """Set the matplotlib defaults every figure shares."""
    _register_local_fonts()
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": FONT_FAMILY,
            "font.size": 8,
            "axes.titlesize": 9,
            "axes.titleweight": "normal",
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "legend.frameon": False,
            "legend.title_fontsize": 7,
            "axes.grid": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": MUTED,
            "axes.labelcolor": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelcolor": INK,
            "ytick.labelcolor": INK,
            "text.color": INK,
            "axes.linewidth": 0.8,
            "lines.linewidth": MEAN_LINE["linewidth"],
            "lines.markersize": MARKER_SIZE,
            "figure.dpi": 110,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.facecolor": "white",
            "pdf.fonttype": 42,  # editable text in the PDF
            "ps.fonttype": 42,
            "axes.unicode_minus": False,
        }
    )


def format_condition(name: str) -> str:
    """The display label of a condition: 'refer_mixed' -> 'Refer mixed'."""
    return CONDITION_LABELS.get(name, name.replace("_", " ").capitalize())


def add_phase_boundary(ax, blocks: int = GAME_BLOCKS) -> None:
    """Mark the Phase 1 to Phase 2 boundary on a game-block axis and tick every block."""
    ax.axvline(PHASE_BOUNDARY, color=MUTED, linestyle=":", linewidth=0.8)
    ax.set_xticks(range(1, blocks + 1))
    ax.set_xlim(0.6, blocks + 0.4)


def add_reference_line(ax, y: float, label: str | None = None) -> None:
    """A dashed horizontal reference such as chance or zero, labeled at the right edge."""
    ax.axhline(y, **REFERENCE_LINE)
    if label:
        ax.annotate(
            label,
            xy=(1.0, y),
            xycoords=("axes fraction", "data"),
            xytext=(-2, 2),
            textcoords="offset points",
            ha="right",
            va="bottom",
            fontsize=plt.rcParams["legend.fontsize"],
            color=MUTED,
        )


__all__ = [
    "CONDITION_ORDER",
    "SOCIAL_CONDITIONS",
    "H12_CONDITIONS",
    "CONDITION_LABELS",
    "CONDITION_COLORS",
    "CONDITION_MARKERS",
    "GROUP_ORDER",
    "GROUP_COLORS",
    "GROUP_TYPE_COLORS",
    "GROUP_TYPE_LABELS",
    "WINDOW_LABELS",
    "PHASE1_BLOCKS",
    "PHASE2_BLOCKS",
    "GAME_BLOCKS",
    "PHASE_BOUNDARY",
    "INK",
    "MUTED",
    "GAME_LINE",
    "MEAN_LINE",
    "MARKER_SIZE",
    "CI_ALPHA",
    "REFERENCE_LINE",
    "SINGLE_COLUMN",
    "DOUBLE_COLUMN",
    "DOUBLE_COLUMN_TALL",
    "apply_style",
    "format_condition",
    "add_phase_boundary",
    "add_reference_line",
]

matplotlib.use(matplotlib.get_backend())  # keep the caller's backend
