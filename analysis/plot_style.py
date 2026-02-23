"""
Shared plot style for analysis figures.

Style: seaborn ticks with despine, larger fonts, no bold titles,
matplotlib default font.

Usage:
    from plot_style import apply_style, CONDITION_COLORS, GROUP_COLORS
    apply_style()
"""

import matplotlib.pyplot as plt
import seaborn as sns


# ── Color palettes ────────────────────────────────────────────

CONDITION_COLORS = {
    "refer_separated": "#F8766D",
    "refer_mixed": "#00BA38",
    "social_mixed": "#619CFF",
}

GROUP_COLORS = {"A": "#F8766D", "B": "#00BA38", "C": "#619CFF"}
GROUP_ORDER = ["A", "B", "C"]

PHASE_BOUNDARY = 5.5  # x position between Phase 1 (blocks 0-5) and Phase 2 (blocks 6-11)
PHASE2_OFFSET = 6


# ── Apply global style ───────────────────────────────────────

def apply_style():
    """Set seaborn ticks theme with despine, larger fonts, no bold titles."""
    sns.set_theme(style="ticks", font_scale=1.3)
    plt.rcParams.update({
        "axes.titleweight": "normal",
        "figure.titleweight": "normal",
    })


# ── Helper functions ─────────────────────────────────────────

def continuous_block(df):
    """Return a copy with a `block` column: Phase 2 blockNum shifted by +6."""
    df = df.copy()
    df["block"] = df["blockNum"] + (df["phaseNum"] == 2).astype(int) * PHASE2_OFFSET
    return df


def add_phase_boundary(ax):
    """Add dashed vertical line at Phase 1/2 boundary and set x-axis."""
    ax.axvline(PHASE_BOUNDARY, color="gray", linestyle=":", alpha=0.6)
    ax.set_xticks(range(12))
    ax.set_xlim(-0.3, 11.3)
    sns.despine(ax=ax)


def add_chance_line(ax, y, label="Chance"):
    """Add a dashed horizontal reference line."""
    ax.axhline(y=y, color="gray", linestyle="--", alpha=0.5, label=label)


def save_fig(fig, path, dpi=150):
    """Tight layout, save, and close."""
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def format_condition(name):
    """Format condition name for display: 'refer_mixed' → 'refer mixed'."""
    return name.replace("_", " ")
