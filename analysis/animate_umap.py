"""
Animate UMAP utterance evolution over blocks.

Auto-discovers conditions and game IDs from games.csv in the data directory.

Produces two videos per condition:
  1. umap_tangram_grid_{condition}.mp4 — 2x3 grid, one subplot per tangram
  2. umap_all_tangrams_{condition}.mp4 — single plot, all tangrams with different markers

Usage:
    uv run python analysis/animate_umap.py                                     # all conditions
    uv run python analysis/animate_umap.py --condition social_mixed            # single condition
    uv run python analysis/animate_umap.py --data-dir analysis/20260222_132407/data/
"""

import argparse
from io import BytesIO
from pathlib import Path

import cairosvg
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.animation import FuncAnimation
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnnotationBbox, OffsetImage

SVG_DIR = Path("experiment/client/public")

# ---------------------------------------------------------------------------
# Style constants (match visualize_pilot.py)
# ---------------------------------------------------------------------------
GROUP_PALETTE = {"A": "steelblue", "B": "coral", "C": "forestgreen"}
GROUP_ORDER = ["A", "B", "C"]

TANGRAM_MARKERS = {
    "page1-128": "o",
    "page3-136": "s",
    "page3-85": "^",
    "page5-64": "D",
    "page9-27": "v",
    "page9-46": "P",
}
TANGRAM_ORDER = sorted(TANGRAM_MARKERS.keys())

N_BLOCKS = 12  # 6 Phase 1 + 6 Phase 2
FPS = 2


def discover_conditions(data_dir: Path) -> dict[str, list[str]]:
    """Read games.csv and return {condition: [gameId, ...]}."""
    games = pd.read_csv(data_dir / "games.csv")
    games = games[games["condition"].notna()]
    return games.groupby("condition")["gameId"].apply(list).to_dict()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def condition_label(condition):
    """Format condition name for display in titles."""
    return condition.replace("_", " ")


def load_data(data_dir: Path, game_ids: list[str]):
    df = pd.read_csv(data_dir / "umap_projections.csv")
    df = df[df["gameId"].isin(game_ids)].copy()
    # Continuous block 0-11
    df["block"] = df["blockNum"].astype(int) + (df["phaseNum"] == 2).astype(int) * 6
    return df


def load_tangram_image(target, size_px=80):
    """Convert tangram SVG to a matplotlib-readable image array."""
    svg_path = SVG_DIR / f"tangram_{target}.svg"
    png_bytes = cairosvg.svg2png(
        url=str(svg_path), output_width=size_px, output_height=size_px
    )
    return mpimg.imread(BytesIO(png_bytes), format="png")


def fade_alpha(point_block, current_block):
    """Alpha that fades older points: newest=1.0, oldest~0.15."""
    return 0.15 + 0.85 * (point_block / current_block) if current_block > 0 else 1.0


def block_label(block_idx):
    """Human-readable label: 'Phase 1 Block 3' etc."""
    if block_idx < 6:
        return f"Phase 1 — Block {block_idx + 1}"
    return f"Phase 2 — Block {block_idx - 5}"


def compute_centroids(df):
    """Per-(originalGroup, target, block) centroid of UMAP coordinates.

    Returns dict: (group, target) -> DataFrame with columns [block, cx, cy],
    sorted by block.
    """
    grouped = (
        df.groupby(["originalGroup", "target", "block"])[["umap_x", "umap_y"]]
        .mean()
        .reset_index()
        .rename(columns={"umap_x": "cx", "umap_y": "cy"})
    )
    result = {}
    for (g, t), sub in grouped.groupby(["originalGroup", "target"]):
        result[(g, t)] = sub.sort_values("block").reset_index(drop=True)
    return result


def build_trajectory_segments(centroid_df, current_block, color):
    """Return a LineCollection of segments up to *current_block* with fading alpha."""
    visible = centroid_df[centroid_df["block"] <= current_block]
    if len(visible) < 2:
        return None
    pts = visible[["cx", "cy"]].values
    blocks = visible["block"].values
    # Each segment connects consecutive centroids
    segments = [[pts[i], pts[i + 1]] for i in range(len(pts) - 1)]
    # Segment alpha = alpha of the *later* endpoint
    base_rgba = plt.matplotlib.colors.to_rgba(color)
    colors = []
    for i in range(len(segments)):
        a = fade_alpha(blocks[i + 1], current_block)
        colors.append((*base_rgba[:3], a * 0.6))  # slightly more transparent than dots
    lc = LineCollection(segments, colors=colors, linewidths=1.5)
    return lc


# ---------------------------------------------------------------------------
# Video 1: 2x3 tangram grid
# ---------------------------------------------------------------------------
def make_tangram_grid_video(df, condition="", output_dir=None):
    sns.set_theme(
        style="ticks",
        font_scale=1.3,
        rc={"font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"]},
    )

    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    axes_flat = axes.flatten()

    # Fixed axis limits (with padding)
    pad = 0.5
    x_min, x_max = df["umap_x"].min() - pad, df["umap_x"].max() + pad
    y_min, y_max = df["umap_y"].min() - pad, df["umap_y"].max() + pad

    # Load tangram images
    tangram_imgs = {t: load_tangram_image(t, size_px=60) for t in TANGRAM_ORDER}

    # Precompute centroids for trajectory lines
    centroids = compute_centroids(df)

    # Pre-create scatter artists (empty) per subplot per group
    scatters = {}  # (tangram_idx, group) -> PathCollection
    # Track line collections so we can remove/replace each frame
    line_collections = {}  # (tangram_idx, group) -> LineCollection or None
    for i, target in enumerate(TANGRAM_ORDER):
        ax = axes_flat[i]
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)
        ax.set_xlabel("UMAP 1")
        ax.set_ylabel("UMAP 2")
        ax.set_title(target)
        sns.despine(ax=ax)

        # Tangram inset (top-right corner)
        im = OffsetImage(tangram_imgs[target], zoom=0.5)
        ab = AnnotationBbox(
            im,
            (1, 1),
            xycoords="axes fraction",
            box_alignment=(1.1, 1.1),
            frameon=False,
        )
        ax.add_artist(ab)

        for g in GROUP_ORDER:
            sc = ax.scatter(
                [], [], c=GROUP_PALETTE[g], s=60, edgecolors="none", label=g
            )
            scatters[(i, g)] = sc
            line_collections[(i, g)] = None

    # Shared legend on first subplot
    axes_flat[0].legend(title="Group", loc="lower left")

    # Title text
    suptitle = fig.suptitle("", fontsize=16, y=0.98)

    fig.tight_layout(rect=[0, 0, 1, 0.94])

    def update(frame):
        current_block = frame
        suptitle.set_text(
            f"{condition_label(condition)} pilot — {block_label(current_block)}"
        )

        for i, target in enumerate(TANGRAM_ORDER):
            ax = axes_flat[i]
            sub = df[df["target"] == target]

            for g in GROUP_ORDER:
                # --- Scatter points ---
                mask = (sub["originalGroup"] == g) & (sub["block"] <= current_block)
                pts = sub[mask]

                if len(pts) == 0:
                    scatters[(i, g)].set_offsets(np.empty((0, 2)))
                else:
                    offsets = pts[["umap_x", "umap_y"]].values
                    alphas = np.array(
                        [fade_alpha(b, current_block) for b in pts["block"]]
                    )
                    scatters[(i, g)].set_offsets(offsets)
                    scatters[(i, g)].set_alpha(None)
                    base_color = plt.matplotlib.colors.to_rgba(GROUP_PALETTE[g])
                    rgba = np.tile(base_color, (len(pts), 1))
                    rgba[:, 3] = alphas
                    scatters[(i, g)].set_facecolors(rgba)

                # --- Trajectory lines ---
                old_lc = line_collections[(i, g)]
                if old_lc is not None:
                    old_lc.remove()
                    line_collections[(i, g)] = None

                ckey = (g, target)
                if ckey in centroids:
                    lc = build_trajectory_segments(
                        centroids[ckey], current_block, GROUP_PALETTE[g]
                    )
                    if lc is not None:
                        ax.add_collection(lc)
                        line_collections[(i, g)] = lc

        return []

    anim = FuncAnimation(fig, update, frames=N_BLOCKS, interval=1000 // FPS, blit=False)

    out_path = output_dir / f"umap_tangram_grid_{condition}.mp4"
    anim.save(str(out_path), writer="ffmpeg", fps=FPS, dpi=150)
    plt.close(fig)
    print(f"  Saved {out_path}")


# ---------------------------------------------------------------------------
# Video 2: Single plot, all tangrams
# ---------------------------------------------------------------------------
def make_all_tangrams_video(df, condition="", output_dir=None):
    sns.set_theme(
        style="ticks",
        font_scale=1.4,
        rc={"font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"]},
    )

    fig, ax = plt.subplots(figsize=(10, 8))

    pad = 0.5
    x_min, x_max = df["umap_x"].min() - pad, df["umap_x"].max() + pad
    y_min, y_max = df["umap_y"].min() - pad, df["umap_y"].max() + pad
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_xlabel("UMAP 1")
    ax.set_ylabel("UMAP 2")
    sns.despine(ax=ax)

    # Precompute centroids for trajectory lines
    centroids = compute_centroids(df)

    # One scatter per (group, tangram)
    scatters = {}
    line_collections = {}
    for g in GROUP_ORDER:
        for target in TANGRAM_ORDER:
            marker = TANGRAM_MARKERS[target]
            sc = ax.scatter(
                [], [], c=GROUP_PALETTE[g], s=70, marker=marker, edgecolors="none"
            )
            scatters[(g, target)] = sc
            line_collections[(g, target)] = None

    # Two separate legends
    group_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor=GROUP_PALETTE[g],
            markersize=10,
            label=g,
        )
        for g in GROUP_ORDER
    ]
    leg1 = ax.legend(
        handles=group_handles,
        title="Group",
        loc="lower right",
        bbox_to_anchor=(0.78, 0),
    )
    ax.add_artist(leg1)

    tangram_handles = [
        Line2D(
            [0],
            [0],
            marker=TANGRAM_MARKERS[t],
            color="w",
            markerfacecolor="gray",
            markersize=10,
            label=t,
        )
        for t in TANGRAM_ORDER
    ]
    leg2 = ax.legend(handles=tangram_handles, title="Tangram", loc="lower right")

    title = ax.set_title("", fontsize=16)

    fig.tight_layout()

    def update(frame):
        current_block = frame

        title.set_text(
            f"{condition_label(condition)} pilot — {block_label(current_block)}"
        )

        for g in GROUP_ORDER:
            for target in TANGRAM_ORDER:
                # --- Scatter points ---
                mask = (
                    (df["originalGroup"] == g)
                    & (df["target"] == target)
                    & (df["block"] <= current_block)
                )
                pts = df[mask]

                if len(pts) == 0:
                    scatters[(g, target)].set_offsets(np.empty((0, 2)))
                else:
                    offsets = pts[["umap_x", "umap_y"]].values
                    alphas = np.array(
                        [fade_alpha(b, current_block) for b in pts["block"]]
                    )
                    scatters[(g, target)].set_offsets(offsets)
                    base_color = plt.matplotlib.colors.to_rgba(GROUP_PALETTE[g])
                    rgba = np.tile(base_color, (len(pts), 1))
                    rgba[:, 3] = alphas
                    scatters[(g, target)].set_facecolors(rgba)

                # --- Trajectory lines ---
                old_lc = line_collections[(g, target)]
                if old_lc is not None:
                    old_lc.remove()
                    line_collections[(g, target)] = None

                ckey = (g, target)
                if ckey in centroids:
                    lc = build_trajectory_segments(
                        centroids[ckey], current_block, GROUP_PALETTE[g]
                    )
                    if lc is not None:
                        ax.add_collection(lc)
                        line_collections[(g, target)] = lc

        return []

    anim = FuncAnimation(fig, update, frames=N_BLOCKS, interval=1000 // FPS, blit=False)

    out_path = output_dir / f"umap_all_tangrams_{condition}.mp4"
    anim.save(str(out_path), writer="ffmpeg", fps=FPS, dpi=150)
    plt.close(fig)
    print(f"  Saved {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Animate UMAP projections")
    parser.add_argument(
        "--condition",
        "-c",
        default=None,
        help="Which condition to animate (default: all discovered conditions)",
    )
    parser.add_argument(
        "--data-dir",
        default="analysis/processed/",
        help="Path to directory containing preprocessed CSVs (default: analysis/processed/)",
    )
    parser.add_argument(
        "--output-dir",
        default="analysis/outputs/",
        help="Path to write output videos (default: analysis/outputs/)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)

    if not (data_dir / "games.csv").exists():
        print(f"games.csv not found in {data_dir}")
        return

    conditions = discover_conditions(data_dir)
    print(f"Discovered conditions: {list(conditions.keys())}")

    if args.condition:
        if args.condition not in conditions:
            print(
                f"Condition '{args.condition}' not found. Available: {list(conditions.keys())}"
            )
            return
        conditions = {args.condition: conditions[args.condition]}

    output_dir.mkdir(parents=True, exist_ok=True)

    for condition, game_ids in conditions.items():
        df = load_data(data_dir, game_ids)
        print(f"\nCondition: {condition}")
        print(f"  Loaded {len(df)} utterances, blocks 0-{df['block'].max()}")

        # Check for umap columns
        if "umap_x" not in df.columns or "umap_y" not in df.columns:
            print(f"  Skipping {condition}: no UMAP projections (run embeddings first)")
            continue

        print("  Rendering tangram grid video...")
        make_tangram_grid_video(df, condition, output_dir)

        print("  Rendering all-tangrams video...")
        make_all_tangrams_video(df, condition, output_dir)

    print("\nDone.")


if __name__ == "__main__":
    main()
