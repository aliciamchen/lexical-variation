"""
Visualize pilot data from one or all conditions.

Auto-discovers conditions and game IDs from games.csv in the data directory.

Usage:
    uv run python analysis/visualize_pilot.py                                  # all conditions
    uv run python analysis/visualize_pilot.py --condition social_mixed         # single condition
    uv run python analysis/visualize_pilot.py --data-dir analysis/20260222_132407/data/
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

PHASE_BOUNDARY = 5.5  # vertical line between block 5 (end P1) and block 6 (start P2)
PHASE2_OFFSET = 6  # Phase 2 blockNum 0 -> 6 on the continuous axis
GROUP_PALETTE = {"A": "steelblue", "B": "coral", "C": "forestgreen"}


def discover_conditions(data_dir: Path) -> dict[str, list[str]]:
    """Read games.csv and return {condition: [gameId, ...]}."""
    games = pd.read_csv(data_dir / "games.csv")
    games = games[games["condition"].notna()]
    return games.groupby("condition")["gameId"].apply(list).to_dict()


def add_phase_line(ax):
    """Add a vertical dashed line at the Phase 1/2 boundary and despine."""
    ax.axvline(PHASE_BOUNDARY, color="gray", linestyle=":", alpha=0.6)
    ax.set_xticks(range(12))
    ax.set_xlim(-0.3, 11.3)
    sns.despine(ax=ax)


def continuous_block(df):
    """Return a copy with blockNum shifted so Phase 2 starts at 6."""
    df = df.copy()
    df["block"] = df["blockNum"] + (df["phaseNum"] == 2).astype(int) * PHASE2_OFFSET
    return df


def load_data(data_dir: Path, game_ids: list[str]):
    trials = pd.read_csv(data_dir / "trials.csv")
    utterances = pd.read_csv(data_dir / "speaker_utterances.csv")
    adjacent = pd.read_csv(data_dir / "adjacent_similarities.csv")
    umap_df = pd.read_csv(data_dir / "umap_projections.csv")
    players = pd.read_csv(data_dir / "players.csv")
    games = pd.read_csv(data_dir / "games.csv")

    # Filter to the specified game(s)
    trials = trials[trials["gameId"].isin(game_ids)]
    utterances = utterances[utterances["gameId"].isin(game_ids)]
    adjacent = adjacent[adjacent["gameId"].isin(game_ids)]
    umap_df = umap_df[umap_df["gameId"].isin(game_ids)]
    players = players[players["gameId"].isin(game_ids)]

    # Social guesses (only exist for social_mixed)
    social_path = data_dir / "social_guesses.csv"
    if social_path.exists():
        social = pd.read_csv(social_path)
        social = social[social["gameId"].isin(game_ids)]
    else:
        social = pd.DataFrame()

    # Phase change similarities
    phase_change_path = data_dir / "phase_change_similarities.csv"
    if phase_change_path.exists():
        phase_change = pd.read_csv(phase_change_path)
        phase_change = phase_change[phase_change["gameId"].isin(game_ids)]
    else:
        phase_change = pd.DataFrame()

    return trials, utterances, social, adjacent, umap_df, players, games, phase_change


def condition_label(condition):
    """Format condition name for display in titles."""
    return condition.replace("_", " ")


def panel_accuracy(ax, trials, condition=""):
    """A. Listener accuracy by block, per original group."""
    listeners = continuous_block(trials[trials["role"] == "listener"])
    listeners["correct"] = listeners["clickedCorrect"].astype(float)

    sns.lineplot(
        data=listeners,
        x="block",
        y="correct",
        hue="originalGroup",
        hue_order=["A", "B", "C"],
        palette=GROUP_PALETTE,
        marker="o",
        markersize=5,
        errorbar=None,
        ax=ax,
    )

    ax.set_xlabel("Block")
    ax.set_ylabel("Accuracy")
    ax.set_title(f"Referential accuracy ({condition_label(condition)})")
    ax.set_ylim(0, 1.05)
    ax.axhline(1 / 6, color="gray", linestyle="--", alpha=0.5, label="Chance (1/6)")
    add_phase_line(ax)
    ax.legend(title="Original group", fontsize=9, title_fontsize=9)


def panel_description_length(ax, utterances, condition=""):
    """B. Description length by block, per original group."""
    df = continuous_block(utterances)

    sns.lineplot(
        data=df,
        x="block",
        y="uttLength",
        hue="originalGroup",
        hue_order=["A", "B", "C"],
        palette=GROUP_PALETTE,
        marker="o",
        markersize=5,
        errorbar=None,
        ax=ax,
    )

    ax.set_xlabel("Block")
    ax.set_ylabel("Word count")
    ax.set_title(f"Description length ({condition_label(condition)})")
    add_phase_line(ax)
    ax.legend(title="Original group", fontsize=9, title_fontsize=9)


def panel_social_guessing(ax, social, condition=""):
    """C. Social guessing accuracy by Phase 2 block, per original group."""
    social = social.copy()
    social["correct"] = social["socialGuessCorrect"].astype(float)
    social["block"] = social["blockNum"] + PHASE2_OFFSET

    sns.lineplot(
        data=social,
        x="block",
        y="correct",
        hue="originalGroup",
        hue_order=["A", "B", "C"],
        palette=GROUP_PALETTE,
        marker="o",
        markersize=5,
        errorbar=None,
        ax=ax,
    )

    ax.axhline(0.5, color="gray", linestyle="--", alpha=0.5, label="Chance (50%)")
    ax.set_xlabel("Block")
    ax.set_ylabel("Accuracy")
    ax.set_title(f"Social guessing accuracy ({condition_label(condition)})")
    ax.set_ylim(0, 1.05)
    add_phase_line(ax)
    ax.legend(title="Original group", fontsize=9, title_fontsize=9)


def panel_phase_change(ax, phase_change, condition=""):
    """C (alt). Phase change similarity per original group (boxplot)."""
    sns.boxplot(
        data=phase_change,
        x="originalGroup",
        y="simPhase1Phase2",
        order=["A", "B", "C"],
        palette=GROUP_PALETTE,
        width=0.5,
        ax=ax,
    )
    sns.stripplot(
        data=phase_change,
        x="originalGroup",
        y="simPhase1Phase2",
        order=["A", "B", "C"],
        color="black",
        alpha=0.4,
        size=3,
        jitter=True,
        ax=ax,
    )

    ax.set_xlabel("Original group")
    ax.set_ylabel("Cosine similarity")
    ax.set_title(f"Phase 1->2 description stability ({condition_label(condition)})")
    ax.set_ylim(0, 1.05)
    sns.despine(ax=ax)


def panel_convention_stability(ax, adjacent, condition=""):
    """D. Convention stability (adjacent cosine similarity) by block, per original group."""
    df = continuous_block(adjacent)

    sns.lineplot(
        data=df,
        x="block",
        y="simAdjacent",
        hue="originalGroup",
        hue_order=["A", "B", "C"],
        palette=GROUP_PALETTE,
        marker="o",
        markersize=5,
        errorbar=None,
        ax=ax,
    )

    ax.set_xlabel("Block")
    ax.set_ylabel("Cosine similarity")
    ax.set_title(f"Convention stability ({condition_label(condition)})")
    ax.set_ylim(0, 1.05)
    add_phase_line(ax)
    ax.legend(title="Original group", fontsize=9, title_fontsize=9)


def panel_ingroup_outgroup(ax, trials, condition=""):
    """E. Phase 2 listener accuracy by same/different original group."""
    p2_listeners = continuous_block(
        trials[(trials["phaseNum"] == 2) & (trials["role"] == "listener")]
    )
    p2_listeners["correct"] = p2_listeners["clickedCorrect"].astype(float)
    p2_listeners["sameGroup"] = (
        p2_listeners["originalGroup"] == p2_listeners["currentGroup"]
    ).map({True: "Same", False: "Different"})

    # Dodge: shift x slightly per group to avoid overplotting
    dodge_map = {"A": -0.15, "B": 0.0, "C": 0.15}
    p2_listeners["block_dodge"] = p2_listeners["block"] + p2_listeners[
        "originalGroup"
    ].map(dodge_map)

    sns.lineplot(
        data=p2_listeners,
        x="block_dodge",
        y="correct",
        hue="originalGroup",
        style="sameGroup",
        hue_order=["A", "B", "C"],
        style_order=["Same", "Different"],
        palette=GROUP_PALETTE,
        dashes={"Same": "", "Different": (4, 2)},
        markers={"Same": "o", "Different": "o"},
        markersize=5,
        errorbar=None,
        ax=ax,
    )

    ax.set_xlabel("Block")
    ax.set_ylabel("Accuracy")
    ax.set_title(f"In-group vs out-group accuracy ({condition_label(condition)})")
    ax.set_ylim(0, 1.05)
    add_phase_line(ax)
    # Clean up legend: rename seaborn's auto-generated section titles
    handles, labels = ax.get_legend_handles_labels()
    new_labels = []
    for l in labels:
        if l == "originalGroup":
            new_labels.append("Original group")
        elif l == "sameGroup":
            new_labels.append("Speaker group")
        else:
            new_labels.append(l)
    ax.legend(handles, new_labels, fontsize=8, title_fontsize=9)


def panel_umap(ax, umap_df, condition=""):
    """F. UMAP projection colored by original group."""
    sns.scatterplot(
        data=umap_df,
        x="umap_x",
        y="umap_y",
        hue="originalGroup",
        hue_order=["A", "B", "C"],
        palette=GROUP_PALETTE,
        alpha=0.6,
        s=25,
        ax=ax,
    )

    ax.set_xlabel("UMAP 1")
    ax.set_ylabel("UMAP 2")
    ax.set_title(f"UMAP of speaker descriptions ({condition_label(condition)})")
    sns.despine(ax=ax)
    ax.legend(title="Original group", fontsize=9, title_fontsize=9)


def print_exit_survey(players):
    """Print summary table of exit survey responses."""
    survey_cols = [c for c in players.columns if c.startswith("exitSurvey_")]
    if not survey_cols:
        print("No exit survey data found.")
        return

    display_cols = ["originalName", "originalGroup", "isActive"] + survey_cols
    existing = [c for c in display_cols if c in players.columns]
    survey_df = players[existing].copy()

    # Rename for display
    rename = {c: c.replace("exitSurvey_", "") for c in survey_cols}
    survey_df = survey_df.rename(columns=rename)

    print("\n" + "=" * 80)
    print("EXIT SURVEY RESPONSES")
    print("=" * 80)
    for _, row in survey_df.iterrows():
        name = row.get("originalName", "?")
        group = row.get("originalGroup", "?")
        active = row.get("isActive", "?")
        print(f"\n--- {name} (Group {group}, active={active}) ---")
        for col in rename.values():
            val = row.get(col, "")
            if pd.notna(val) and val != "":
                print(f"  {col}: {val}")


def visualize_condition(
    condition: str, game_ids: list[str], data_dir: Path, output_dir: Path
):
    """Generate all panels for a single condition."""
    print(f"\nCondition: {condition}")
    print(f"  Game IDs: {game_ids}")

    trials, utterances, social, adjacent, umap_df, players, games, phase_change = (
        load_data(data_dir, game_ids)
    )

    print(f"  Trials: {len(trials)}, Utterances: {len(utterances)}")
    print(f"  Social guesses: {len(social)}, Adjacent sims: {len(adjacent)}")
    print(f"  Phase change sims: {len(phase_change)}, Players: {len(players)}")

    # Build panel list — swap social guessing for phase change when not available
    panels = [
        ("listener_accuracy", panel_accuracy, [trials, condition]),
        ("description_length", panel_description_length, [utterances, condition]),
    ]
    if len(social) > 0:
        panels.append(("social_guessing", panel_social_guessing, [social, condition]))
    panels.append(("phase_change", panel_phase_change, [phase_change, condition]))
    panels += [
        ("convention_stability", panel_convention_stability, [adjacent, condition]),
        ("ingroup_outgroup", panel_ingroup_outgroup, [trials, condition]),
        ("umap", panel_umap, [umap_df, condition]),
    ]

    for name, func, panel_args in panels:
        fig, ax = plt.subplots(figsize=(6, 4))
        func(ax, *panel_args)
        fig.tight_layout()
        path = output_dir / f"pilot_{condition}_{name}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved {path}")

    # Print exit survey
    print_exit_survey(players)


def main():
    parser = argparse.ArgumentParser(description="Visualize pilot data")
    parser.add_argument(
        "--condition",
        "-c",
        default=None,
        help="Which condition to visualize (default: all discovered conditions)",
    )
    parser.add_argument(
        "--data-dir",
        default="analysis/processed/",
        help="Path to directory containing preprocessed CSVs (default: analysis/processed/)",
    )
    parser.add_argument(
        "--output-dir",
        default="analysis/outputs/",
        help="Path to write output figures (default: analysis/outputs/)",
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

    # Style
    sns.set_theme(
        style="ticks",
        font_scale=1.15,
        rc={"font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"]},
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    for condition, game_ids in conditions.items():
        visualize_condition(condition, game_ids, data_dir, output_dir)

    print(f"\nAll figures saved to {output_dir}/")


if __name__ == "__main__":
    main()
