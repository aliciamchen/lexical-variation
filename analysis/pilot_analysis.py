"""
Pilot data analysis and visualization.

Auto-discovers conditions from games.csv, generates per-condition panel plots,
cross-condition comparisons, and prints descriptive statistics.

Usage:
    uv run python analysis/pilot_analysis.py
    uv run python analysis/pilot_analysis.py --data-dir analysis/20260222_132407/data/
    uv run python analysis/pilot_analysis.py --condition social_mixed
    uv run python analysis/pilot_analysis.py --output-dir analysis/figures/
"""

import argparse
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
import seaborn as sns

from plot_style import (
    apply_style,
    CONDITION_COLORS,
    GROUP_COLORS,
    GROUP_ORDER,
    PHASE_BOUNDARY,
    PHASE2_OFFSET,
    add_chance_line,
    add_phase_boundary,
    continuous_block,
    format_condition,
    save_fig,
)

warnings.filterwarnings("ignore", category=FutureWarning)


# ── Data loading ──────────────────────────────────────────────

def discover_conditions(data_dir: Path) -> dict[str, list[str]]:
    """Read games.csv and return {condition: [gameId, ...]}."""
    games = pd.read_csv(data_dir / "games.csv")
    games = games[games["condition"].notna()]
    return games.groupby("condition")["gameId"].apply(list).to_dict()


def load_data(data_dir: Path, game_ids: list[str]):
    """Load and filter all CSVs to the given game IDs."""
    games = pd.read_csv(data_dir / "games.csv")
    players = pd.read_csv(data_dir / "players.csv")
    trials = pd.read_csv(data_dir / "trials.csv")
    messages = pd.read_csv(data_dir / "messages.csv")
    utterances = pd.read_csv(data_dir / "speaker_utterances.csv")
    adjacent = pd.read_csv(data_dir / "adjacent_similarities.csv")

    pairwise_path = data_dir / "pairwise_similarities.csv"
    pairwise = pd.read_csv(pairwise_path) if pairwise_path.exists() else pd.DataFrame()

    phase_change_path = data_dir / "phase_change_similarities.csv"
    phase_change = pd.read_csv(phase_change_path) if phase_change_path.exists() else pd.DataFrame()

    umap_path = data_dir / "umap_projections.csv"
    umap_df = pd.read_csv(umap_path) if umap_path.exists() else pd.DataFrame()

    social_path = data_dir / "social_guesses.csv"
    social = pd.read_csv(social_path) if social_path.exists() else pd.DataFrame()

    fp_pw_path = data_dir / "first_phrase_similarities.csv"
    first_phrase_pw = pd.read_csv(fp_pw_path) if fp_pw_path.exists() else pd.DataFrame()

    block_pw_path = data_dir / "block_pairwise_similarities.csv"
    block_pw = pd.read_csv(block_pw_path) if block_pw_path.exists() else pd.DataFrame()

    term_retention_path = data_dir / "term_retention.csv"
    term_retention = pd.read_csv(term_retention_path) if term_retention_path.exists() else pd.DataFrame()

    alt_structures_path = data_dir / "alternative_structures.csv"
    alt_structures = pd.read_csv(alt_structures_path) if alt_structures_path.exists() else pd.DataFrame()

    length_retention_path = data_dir / "length_retention.csv"
    length_retention = pd.read_csv(length_retention_path) if length_retention_path.exists() else pd.DataFrame()

    social_guess_retention_path = data_dir / "social_guess_retention.csv"
    social_guess_retention = pd.read_csv(social_guess_retention_path) if social_guess_retention_path.exists() else pd.DataFrame()

    borrowing_path = data_dir / "cross_group_borrowing.csv"
    cross_group_borrowing = pd.read_csv(borrowing_path) if borrowing_path.exists() else pd.DataFrame()

    audience_design_path = data_dir / "audience_design.csv"
    audience_design = pd.read_csv(audience_design_path) if audience_design_path.exists() else pd.DataFrame()

    term_dominance_path = data_dir / "term_dominance.csv"
    term_dominance = pd.read_csv(term_dominance_path) if term_dominance_path.exists() else pd.DataFrame()

    hedging_trajectory_path = data_dir / "hedging_trajectory.csv"
    hedging_trajectory = pd.read_csv(hedging_trajectory_path) if hedging_trajectory_path.exists() else pd.DataFrame()

    # Filter to specified games
    def _filter(df):
        if not df.empty and "gameId" in df.columns:
            return df[df["gameId"].isin(game_ids)].copy()
        return df

    return {
        "games": games[games["gameId"].isin(game_ids)].copy(),
        "players": players[players["gameId"].isin(game_ids)].copy() if "gameId" in players.columns else players,
        "trials": _filter(trials),
        "messages": _filter(messages),
        "utterances": _filter(utterances),
        "adjacent": _filter(adjacent),
        "pairwise": _filter(pairwise),
        "phase_change": _filter(phase_change),
        "umap_df": _filter(umap_df),
        "social": _filter(social),
        "first_phrase_pw": _filter(first_phrase_pw),
        "block_pw": _filter(block_pw),
        "term_retention": _filter(term_retention),
        "alt_structures": _filter(alt_structures),
        "length_retention": _filter(length_retention),
        "social_guess_retention": _filter(social_guess_retention),
        "cross_group_borrowing": _filter(cross_group_borrowing),
        "audience_design": _filter(audience_design),
        "term_dominance": _filter(term_dominance),
        "hedging_trajectory": _filter(hedging_trajectory),
    }


# ── Per-condition panel plots ─────────────────────────────────

def panel_accuracy(ax, trials, condition=""):
    """Listener accuracy by block, per original group."""
    listeners = continuous_block(trials[trials["role"] == "listener"])
    listeners["correct"] = listeners["clickedCorrect"].astype(float)

    sns.lineplot(
        data=listeners, x="block", y="correct",
        hue="originalGroup", hue_order=GROUP_ORDER,
        palette=GROUP_COLORS, marker="o", markersize=5,
        errorbar=None, ax=ax,
    )
    ax.set_xlabel("Block")
    ax.set_ylabel("Accuracy")
    ax.set_title(f"Referential accuracy ({format_condition(condition)})")
    ax.set_ylim(0, 1.05)
    add_chance_line(ax, 1 / 6, "Chance (1/6)")
    add_phase_boundary(ax)
    ax.legend(title="Original group", fontsize=9, title_fontsize=9)


def panel_description_length(ax, utterances, condition=""):
    """Description length by block, per original group."""
    df = continuous_block(utterances)

    sns.lineplot(
        data=df, x="block", y="uttLength",
        hue="originalGroup", hue_order=GROUP_ORDER,
        palette=GROUP_COLORS, marker="o", markersize=5,
        errorbar=None, ax=ax,
    )
    ax.set_xlabel("Block")
    ax.set_ylabel("Word count")
    ax.set_title(f"Description length ({format_condition(condition)})")
    add_phase_boundary(ax)
    ax.legend(title="Original group", fontsize=9, title_fontsize=9)


def panel_convention_stability(ax, adjacent, condition=""):
    """Convention stability (adjacent similarity) by block, per original group."""
    df = continuous_block(adjacent)

    sns.lineplot(
        data=df, x="block", y="simAdjacent",
        hue="originalGroup", hue_order=GROUP_ORDER,
        palette=GROUP_COLORS, marker="o", markersize=5,
        errorbar=None, ax=ax,
    )
    ax.set_xlabel("Block")
    ax.set_ylabel("Cosine similarity")
    ax.set_title(f"Convention stability ({format_condition(condition)})")
    ax.set_ylim(0, 1.05)
    add_phase_boundary(ax)
    ax.legend(title="Original group", fontsize=9, title_fontsize=9)


def panel_social_guessing(ax, social, condition=""):
    """Social guessing accuracy by block, per original group."""
    social = social.copy()
    social["correct"] = social["socialGuessCorrect"].astype(float)
    social["block"] = social["blockNum"] + PHASE2_OFFSET

    sns.lineplot(
        data=social, x="block", y="correct",
        hue="originalGroup", hue_order=GROUP_ORDER,
        palette=GROUP_COLORS, marker="o", markersize=5,
        errorbar=None, ax=ax,
    )
    add_chance_line(ax, 0.5, "Chance (50%)")
    ax.set_xlabel("Block")
    ax.set_ylabel("Accuracy")
    ax.set_title(f"Social guessing accuracy ({format_condition(condition)})")
    ax.set_ylim(0, 1.05)
    add_phase_boundary(ax)
    ax.legend(title="Original group", fontsize=9, title_fontsize=9)


def panel_phase_change(ax, phase_change, condition=""):
    """Phase change similarity per original group (boxplot + strip)."""
    sns.boxplot(
        data=phase_change, x="originalGroup", y="simPhase1Phase2",
        order=GROUP_ORDER, palette=GROUP_COLORS, width=0.5, ax=ax,
    )
    sns.stripplot(
        data=phase_change, x="originalGroup", y="simPhase1Phase2",
        order=GROUP_ORDER, color="black", alpha=0.4, size=3,
        jitter=True, ax=ax,
    )
    ax.set_xlabel("Original group")
    ax.set_ylabel("Cosine similarity")
    ax.set_title(f"Phase 1→2 description stability ({format_condition(condition)})")
    ax.set_ylim(0, 1.05)
    sns.despine(ax=ax)


def panel_ingroup_outgroup(ax, trials, condition=""):
    """Phase 2 listener accuracy by same/different original group."""
    p2_listeners = continuous_block(
        trials[(trials["phaseNum"] == 2) & (trials["role"] == "listener")]
    )
    p2_listeners["correct"] = p2_listeners["clickedCorrect"].astype(float)
    p2_listeners["sameGroup"] = (
        p2_listeners["originalGroup"] == p2_listeners["currentGroup"]
    ).map({True: "Same", False: "Different"})

    dodge_map = {"A": -0.15, "B": 0.0, "C": 0.15}
    p2_listeners["block_dodge"] = p2_listeners["block"] + p2_listeners[
        "originalGroup"
    ].map(dodge_map)

    sns.lineplot(
        data=p2_listeners, x="block_dodge", y="correct",
        hue="originalGroup", style="sameGroup",
        hue_order=GROUP_ORDER, style_order=["Same", "Different"],
        palette=GROUP_COLORS,
        dashes={"Same": "", "Different": (4, 2)},
        markers={"Same": "o", "Different": "o"},
        markersize=5, errorbar=None, ax=ax,
    )
    ax.set_xlabel("Block")
    ax.set_ylabel("Accuracy")
    ax.set_title(f"In-group vs out-group accuracy ({format_condition(condition)})")
    ax.set_ylim(0, 1.05)
    add_phase_boundary(ax)
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
    """UMAP projection colored by original group."""
    if umap_df.empty or "umap_x" not in umap_df.columns:
        ax.text(0.5, 0.5, "No UMAP data", ha="center", va="center",
                transform=ax.transAxes)
        return

    sns.scatterplot(
        data=umap_df, x="umap_x", y="umap_y",
        hue="originalGroup", hue_order=GROUP_ORDER,
        palette=GROUP_COLORS, alpha=0.6, s=25, ax=ax,
    )
    ax.set_xlabel("UMAP 1")
    ax.set_ylabel("UMAP 2")
    ax.set_title(f"UMAP of speaker descriptions ({format_condition(condition)})")
    sns.despine(ax=ax)
    ax.legend(title="Original group", fontsize=9, title_fontsize=9)


def panel_group_specificity(ax, pairwise, condition=""):
    """Within vs between group pairwise similarity (bar chart)."""
    if pairwise.empty:
        ax.text(0.5, 0.5, "No pairwise data", ha="center", va="center",
                transform=ax.transAxes)
        return

    rows = []
    for window in ["phase1_final", "phase2_final"]:
        w_data = pairwise[pairwise["window"] == window]
        within = w_data[w_data["sameGroup"] == 1]["similarity"]
        between = w_data[w_data["sameGroup"] == 0]["similarity"]
        phase_label = "Phase 1" if "phase1" in window else "Phase 2"
        rows.append({"phase": phase_label, "type": "Within-group",
                     "mean": within.mean(), "sem": within.sem()})
        rows.append({"phase": phase_label, "type": "Between-group",
                     "mean": between.mean(), "sem": between.sem()})
    bar_df = pd.DataFrame(rows)

    x = np.arange(2)
    width = 0.35
    within_data = bar_df[bar_df["type"] == "Within-group"]
    between_data = bar_df[bar_df["type"] == "Between-group"]
    ax.bar(x - width / 2, within_data["mean"], width, yerr=within_data["sem"],
           color=GROUP_COLORS["B"], alpha=0.8, capsize=5, label="Within-group")
    ax.bar(x + width / 2, between_data["mean"], width, yerr=between_data["sem"],
           color=GROUP_COLORS["A"], alpha=0.8, capsize=5, label="Between-group")
    ax.set_xticks(x)
    ax.set_xticklabels(["Phase 1\n(final 3 blocks)", "Phase 2\n(final 3 blocks)"])
    ax.set_ylabel("Mean pairwise cosine similarity")
    ax.set_title(f"Group specificity ({format_condition(condition)})")
    ax.legend(fontsize=10)
    sns.despine(ax=ax)


def panel_first_phrase_specificity(ax, first_phrase_pw, condition=""):
    """Within vs between group pairwise similarity using first-phrase embeddings."""
    if first_phrase_pw.empty:
        ax.text(0.5, 0.5, "No first-phrase data", ha="center", va="center",
                transform=ax.transAxes)
        return

    rows = []
    for window in ["phase1_final", "phase2_final"]:
        w_data = first_phrase_pw[first_phrase_pw["window"] == window]
        within = w_data[w_data["sameGroup"] == 1]["similarity"]
        between = w_data[w_data["sameGroup"] == 0]["similarity"]
        phase_label = "Phase 1" if "phase1" in window else "Phase 2"
        rows.append({"phase": phase_label, "type": "Within-group",
                     "mean": within.mean(), "sem": within.sem()})
        rows.append({"phase": phase_label, "type": "Between-group",
                     "mean": between.mean(), "sem": between.sem()})
    bar_df = pd.DataFrame(rows)

    x = np.arange(2)
    width = 0.35
    within_data = bar_df[bar_df["type"] == "Within-group"]
    between_data = bar_df[bar_df["type"] == "Between-group"]
    ax.bar(x - width / 2, within_data["mean"], width, yerr=within_data["sem"],
           color=GROUP_COLORS["B"], alpha=0.8, capsize=5, label="Within-group")
    ax.bar(x + width / 2, between_data["mean"], width, yerr=between_data["sem"],
           color=GROUP_COLORS["A"], alpha=0.8, capsize=5, label="Between-group")
    ax.set_xticks(x)
    ax.set_xticklabels(["Phase 1\n(final 3 blocks)", "Phase 2\n(final 3 blocks)"])
    ax.set_ylabel("Mean pairwise cosine similarity")
    ax.set_title(f"First-phrase group specificity ({format_condition(condition)})")
    ax.legend(fontsize=10)
    sns.despine(ax=ax)


def panel_convergence_trajectory(ax, block_pw, condition=""):
    """Between-group similarity by Phase 2 block (convergence trajectory)."""
    if block_pw.empty:
        ax.text(0.5, 0.5, "No block pairwise data", ha="center", va="center",
                transform=ax.transAxes)
        return

    between = block_pw[block_pw["sameGroup"] == 0].copy()
    within = block_pw[block_pw["sameGroup"] == 1].copy()

    for label, subset, color, ls in [
        ("Between-group", between, GROUP_COLORS["A"], "-"),
        ("Within-group", within, GROUP_COLORS["B"], "--"),
    ]:
        if subset.empty:
            continue
        means = subset.groupby("blockNum")["similarity"].mean()
        sems = subset.groupby("blockNum")["similarity"].sem()
        ax.fill_between(means.index, means - sems, means + sems, color=color, alpha=0.15)
        ax.plot(means.index, means.values, marker="o", markersize=5,
                color=color, linestyle=ls, label=label)

    ax.set_xlabel("Phase 2 block")
    ax.set_ylabel("Mean pairwise cosine similarity")
    ax.set_title(f"Convergence trajectory ({format_condition(condition)})")
    ax.legend(fontsize=10)
    sns.despine(ax=ax)


def panel_term_retention(ax, term_retention, condition=""):
    """Mean Phase 1 term retention by Phase 2 block, per original group."""
    if term_retention.empty:
        ax.text(0.5, 0.5, "No term retention data", ha="center", va="center",
                transform=ax.transAxes)
        return

    sns.lineplot(
        data=term_retention, x="blockNum", y="retention",
        hue="originalGroup", hue_order=GROUP_ORDER,
        palette=GROUP_COLORS, marker="o", markersize=5,
        errorbar=None, ax=ax,
    )
    ax.set_xlabel("Phase 2 block")
    ax.set_ylabel("Proportion retained")
    ax.set_title(f"Phase 1 term retention ({format_condition(condition)})")
    ax.set_ylim(0, 1.05)
    ax.legend(title="Original group", fontsize=9, title_fontsize=9)
    sns.despine(ax=ax)


def panel_alternative_rate(ax, alt_structures, condition=""):
    """Alternative structure rate by Phase 2 block, per original group."""
    if alt_structures.empty:
        ax.text(0.5, 0.5, "No alternative structure data", ha="center",
                va="center", transform=ax.transAxes)
        return

    sns.lineplot(
        data=alt_structures, x="blockNum", y="hasAlternatives",
        hue="originalGroup", hue_order=GROUP_ORDER,
        palette=GROUP_COLORS, marker="o", markersize=5,
        errorbar=None, ax=ax,
    )
    ax.set_xlabel("Phase 2 block")
    ax.set_ylabel("Proportion with alternatives")
    ax.set_title(f"Alternative structures ({format_condition(condition)})")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(title="Original group", fontsize=9, title_fontsize=9)
    sns.despine(ax=ax)


def panel_length_retention(ax, length_retention, condition=""):
    """Scatter of term retention vs description length with regression."""
    if length_retention.empty:
        ax.text(0.5, 0.5, "No length-retention data", ha="center",
                va="center", transform=ax.transAxes)
        return

    from scipy.stats import pearsonr

    for grp in GROUP_ORDER:
        grp_data = length_retention[length_retention["originalGroup"] == grp]
        if grp_data.empty:
            continue
        ax.scatter(grp_data["retention"], grp_data["uttLength"],
                   color=GROUP_COLORS[grp], alpha=0.4, s=20, label=grp)

    # Overall regression line + annotation
    valid = length_retention.dropna(subset=["retention", "uttLength"])
    if len(valid) > 2:
        r, p = pearsonr(valid["retention"], valid["uttLength"])
        z = np.polyfit(valid["retention"], valid["uttLength"], 1)
        xs = np.linspace(valid["retention"].min(), valid["retention"].max(), 50)
        ax.plot(xs, np.polyval(z, xs), "k--", linewidth=1, alpha=0.7)
        ax.annotate(f"r={r:.2f}, p={p:.3f}", xy=(0.05, 0.95),
                    xycoords="axes fraction", fontsize=9, va="top")

    ax.set_xlabel("Term retention")
    ax.set_ylabel("Description length (words)")
    ax.set_title(f"Length vs retention ({format_condition(condition)})")
    ax.legend(title="Original group", fontsize=9, title_fontsize=9)
    sns.despine(ax=ax)


def panel_social_retention(ax, social_guess_retention, condition=""):
    """Bar chart of social guessing accuracy binned by speaker term retention."""
    if social_guess_retention.empty:
        ax.text(0.5, 0.5, "No social guess-retention data", ha="center",
                va="center", transform=ax.transAxes)
        return

    df = social_guess_retention.dropna(subset=["speakerRetention", "socialGuessCorrect"]).copy()
    if df.empty:
        ax.text(0.5, 0.5, "No valid data", ha="center", va="center",
                transform=ax.transAxes)
        return

    # Bin retention into thirds using fixed cut points
    n_unique = df["speakerRetention"].nunique()
    if n_unique >= 3:
        try:
            df["retentionBin"] = pd.qcut(df["speakerRetention"], 3,
                                           labels=["Low", "Medium", "High"],
                                           duplicates="drop")
        except ValueError:
            # Use fixed percentile boundaries as cut points
            cuts = [df["speakerRetention"].min() - 0.001,
                    df["speakerRetention"].quantile(0.33),
                    df["speakerRetention"].quantile(0.67),
                    df["speakerRetention"].max() + 0.001]
            df["retentionBin"] = pd.cut(df["speakerRetention"], bins=cuts,
                                          labels=["Low", "Medium", "High"])
    elif n_unique == 2:
        median = df["speakerRetention"].median()
        df["retentionBin"] = df["speakerRetention"].apply(
            lambda x: "Low" if x <= median else "High"
        )
    else:
        ax.text(0.5, 0.5, "Not enough retention variance", ha="center",
                va="center", transform=ax.transAxes)
        return

    df["correct"] = df["socialGuessCorrect"].astype(float)
    bin_stats = df.groupby("retentionBin", observed=True)["correct"].agg(["mean", "sem"]).reset_index()

    ax.bar(bin_stats["retentionBin"].astype(str), bin_stats["mean"],
           yerr=bin_stats["sem"], color=GROUP_COLORS["B"], alpha=0.8, capsize=5)
    ax.set_xlabel("Speaker term retention")
    ax.set_ylabel("Social guess accuracy")
    ax.set_title(f"Social guessing by retention ({format_condition(condition)})")
    ax.set_ylim(0, 1.05)
    sns.despine(ax=ax)


def panel_borrowing_rate(ax, cross_group_borrowing, condition=""):
    """Cross-group borrowing rate by Phase 2 block, per original group."""
    if cross_group_borrowing.empty:
        ax.text(0.5, 0.5, "No borrowing data", ha="center",
                va="center", transform=ax.transAxes)
        return

    # Filter out rows where source had no unique terms
    df = cross_group_borrowing[cross_group_borrowing["nSourceTerms"] > 0].copy()
    if df.empty:
        ax.text(0.5, 0.5, "No borrowable terms found", ha="center",
                va="center", transform=ax.transAxes)
        return

    sns.lineplot(
        data=df, x="blockNum", y="borrowingRate",
        hue="originalGroup", hue_order=GROUP_ORDER,
        palette=GROUP_COLORS, marker="o", markersize=5,
        errorbar=None, ax=ax,
    )
    ax.set_xlabel("Phase 2 block")
    ax.set_ylabel("Borrowing rate")
    ax.set_title(f"Cross-group term borrowing ({format_condition(condition)})")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(title="Original group", fontsize=9, title_fontsize=9)
    sns.despine(ax=ax)


def panel_audience_design(ax, audience_design, condition=""):
    """Grouped bar chart of description length by audience type, with SEM."""
    if audience_design.empty:
        ax.text(0.5, 0.5, "No audience design data", ha="center",
                va="center", transform=ax.transAxes)
        return

    order = ["all_same", "mixed", "all_different"]
    present = [t for t in order if t in audience_design["audienceType"].values]
    if not present:
        ax.text(0.5, 0.5, "No audience type data", ha="center",
                va="center", transform=ax.transAxes)
        return

    stats = (
        audience_design.groupby("audienceType")["uttLength"]
        .agg(["mean", "sem", "count"])
        .reindex(present)
    )
    ax.bar(stats.index, stats["mean"], yerr=stats["sem"],
           color=GROUP_COLORS["B"], alpha=0.8, capsize=5)
    ax.set_xlabel("Audience composition")
    ax.set_ylabel("Mean description length")
    ax.set_title(f"Audience design ({format_condition(condition)})")
    sns.despine(ax=ax)


def panel_term_dominance(ax, term_dominance, condition=""):
    """Stacked bar: which group's terms dominate Phase 2 utterances, by block."""
    if term_dominance.empty:
        ax.text(0.5, 0.5, "No term dominance data", ha="center",
                va="center", transform=ax.transAxes)
        return

    df = term_dominance.copy()
    blocks = sorted(df["blockNum"].unique())

    # Determine group labels present
    groups = sorted(
        [g for g in df["dominantTermSource"].unique() if g not in ("tied", "none")]
    )
    categories = groups + ["tied", "none"]
    cat_colors = {}
    for g in groups:
        cat_colors[g] = GROUP_COLORS.get(g, "#888888")
    cat_colors["tied"] = "#999999"
    cat_colors["none"] = "#DDDDDD"

    # Compute proportions per block
    proportions = {cat: [] for cat in categories}
    for block in blocks:
        block_data = df[df["blockNum"] == block]
        n = len(block_data)
        for cat in categories:
            proportions[cat].append(
                (block_data["dominantTermSource"] == cat).sum() / n if n > 0 else 0
            )

    # Stacked bar
    bottoms = np.zeros(len(blocks))
    x = np.arange(len(blocks))
    for cat in categories:
        vals = proportions[cat]
        ax.bar(x, vals, bottom=bottoms, color=cat_colors[cat], label=cat, width=0.7)
        bottoms += np.array(vals)

    ax.set_xticks(x)
    ax.set_xticklabels([str(b) for b in blocks])
    ax.set_xlabel("Phase 2 block")
    ax.set_ylabel("Proportion")
    ax.set_title(f"Term dominance ({format_condition(condition)})")
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=8, title="Dominant source", title_fontsize=8)
    sns.despine(ax=ax)


def panel_hedging_trajectory(ax, hedging_trajectory, condition=""):
    """Individual speaker hedging trajectories + group means over Phase 2 blocks."""
    if hedging_trajectory.empty:
        ax.text(0.5, 0.5, "No hedging trajectory data", ha="center",
                va="center", transform=ax.transAxes)
        return

    df = hedging_trajectory.copy()

    # Thin lines per speaker, colored by group
    for grp in GROUP_ORDER:
        grp_data = df[df["originalGroup"] == grp]
        for player_id in grp_data["playerId"].unique():
            pdata = grp_data[grp_data["playerId"] == player_id].sort_values("blockNum")
            ax.plot(pdata["blockNum"], pdata["hedgingRate"],
                    color=GROUP_COLORS[grp], alpha=0.2, linewidth=0.8)

    # Thick group means
    for grp in GROUP_ORDER:
        grp_data = df[df["originalGroup"] == grp]
        if grp_data.empty:
            continue
        means = grp_data.groupby("blockNum")["hedgingRate"].mean()
        ax.plot(means.index, means.values, color=GROUP_COLORS[grp],
                linewidth=2.5, marker="o", markersize=5, label=grp)

    ax.set_xlabel("Phase 2 block")
    ax.set_ylabel("Hedging rate")
    ax.set_title(f"Hedging trajectory ({format_condition(condition)})")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(title="Original group", fontsize=9, title_fontsize=9)
    sns.despine(ax=ax)


# ── Cross-condition comparison plots ──────────────────────────

def plot_cross_condition(data, output_dir, conditions):
    """Generate cross-condition overlay plots for key metrics."""
    utterances = data["utterances"]
    trials = data["trials"]
    adjacent = data["adjacent"]

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Description length
    ax = axes[0]
    for cond in conditions:
        cond_utt = continuous_block(utterances[utterances["condition"] == cond])
        means = cond_utt.groupby("block")["uttLength"].mean()
        sems = cond_utt.groupby("block")["uttLength"].sem()
        ax.fill_between(means.index, means - sems, means + sems,
                        color=CONDITION_COLORS[cond], alpha=0.15)
        ax.plot(means.index, means.values, marker="o", markersize=4,
                color=CONDITION_COLORS[cond], linewidth=1.2,
                label=format_condition(cond))
    add_phase_boundary(ax)
    ax.set_xlabel("Block")
    ax.set_ylabel("Words")
    ax.set_title("Description length")
    ax.legend()

    # Listener accuracy
    ax = axes[1]
    listener_trials = trials[trials["role"] == "listener"].copy()
    listener_trials["clickedCorrect"] = listener_trials["clickedCorrect"].astype(float)
    for cond in conditions:
        cond_t = continuous_block(listener_trials[listener_trials["condition"] == cond])
        means = cond_t.groupby("block")["clickedCorrect"].mean()
        sems = cond_t.groupby("block")["clickedCorrect"].sem()
        ax.fill_between(means.index, means - sems, means + sems,
                        color=CONDITION_COLORS[cond], alpha=0.15)
        ax.plot(means.index, means.values, marker="o", markersize=4,
                color=CONDITION_COLORS[cond], linewidth=1.2,
                label=format_condition(cond))
    add_phase_boundary(ax)
    add_chance_line(ax, 1 / 6)
    ax.set_xlabel("Block")
    ax.set_ylabel("Accuracy")
    ax.set_ylim(0, 1.05)
    ax.set_title("Listener accuracy")
    ax.legend()

    # Convention stability
    ax = axes[2]
    adj_valid = adjacent[adjacent["simAdjacent"].notna()].copy()
    for cond in conditions:
        cond_adj = continuous_block(adj_valid[adj_valid["condition"] == cond])
        means = cond_adj.groupby("block")["simAdjacent"].mean()
        sems = cond_adj.groupby("block")["simAdjacent"].sem()
        ax.fill_between(means.index, means - sems, means + sems,
                        color=CONDITION_COLORS[cond], alpha=0.15)
        ax.plot(means.index, means.values, marker="o", markersize=4,
                color=CONDITION_COLORS[cond], linewidth=1.2,
                label=format_condition(cond))
    add_phase_boundary(ax)
    ax.set_xlabel("Block")
    ax.set_ylabel("Cosine similarity")
    ax.set_title("Convention stability")
    ax.legend()

    save_fig(fig, output_dir / "cross_condition.png")
    print(f"  Saved cross_condition.png")


def plot_phase_change_comparison(data, output_dir, conditions):
    """Phase change similarity distribution by condition."""
    phase_change = data["phase_change"]
    if phase_change.empty:
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    pc_data = phase_change[phase_change["condition"].isin(conditions)]

    if pc_data.empty:
        plt.close(fig)
        return

    sns.violinplot(
        data=pc_data, x="condition", y="simPhase1Phase2",
        order=[c for c in conditions if c in pc_data["condition"].unique()],
        palette=CONDITION_COLORS, alpha=0.3, inner=None, ax=ax,
    )
    sns.stripplot(
        data=pc_data, x="condition", y="simPhase1Phase2",
        order=[c for c in conditions if c in pc_data["condition"].unique()],
        palette=CONDITION_COLORS, alpha=0.5, size=3, jitter=True, ax=ax,
    )
    ax.set_xlabel("Condition")
    ax.set_ylabel("Cosine similarity (Phase 1 final → Phase 2 final)")
    ax.set_title("Semantic change across phases")
    ax.set_xticklabels([format_condition(c) for c in conditions
                         if c in pc_data["condition"].unique()])
    sns.despine(ax=ax)
    save_fig(fig, output_dir / "phase_change_comparison.png")
    print(f"  Saved phase_change_comparison.png")


def plot_convergence_comparison(data, output_dir, conditions):
    """Overlay between-group similarity trajectories across conditions."""
    block_pw = data["block_pw"]
    if block_pw.empty:
        return

    # Merge condition
    if "condition" not in block_pw.columns:
        block_pw = block_pw.merge(
            data["games"][["gameId", "condition"]], on="gameId", how="left"
        )

    between = block_pw[block_pw["sameGroup"] == 0].copy()
    if between.empty:
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    for cond in conditions:
        cond_data = between[between["condition"] == cond]
        if cond_data.empty:
            continue
        means = cond_data.groupby("blockNum")["similarity"].mean()
        sems = cond_data.groupby("blockNum")["similarity"].sem()
        ax.fill_between(means.index, means - sems, means + sems,
                        color=CONDITION_COLORS[cond], alpha=0.15)
        ax.plot(means.index, means.values, marker="o", markersize=4,
                color=CONDITION_COLORS[cond], linewidth=1.2,
                label=format_condition(cond))
    ax.set_xlabel("Phase 2 block")
    ax.set_ylabel("Mean between-group cosine similarity")
    ax.set_title("Between-group convergence trajectory")
    ax.legend()
    sns.despine(ax=ax)
    save_fig(fig, output_dir / "convergence_comparison.png")
    print(f"  Saved convergence_comparison.png")


def plot_first_phrase_comparison(data, output_dir, conditions):
    """Side-by-side first-phrase GS vs whole-utterance GS."""
    pairwise = data["pairwise"]
    first_phrase_pw = data["first_phrase_pw"]
    if pairwise.empty or first_phrase_pw.empty:
        return

    # Merge condition into both
    game_cond = data["games"][["gameId", "condition"]]
    for df_ref in [pairwise, first_phrase_pw]:
        if "condition" not in df_ref.columns:
            df_ref = df_ref.merge(game_cond, on="gameId", how="left")

    pw = pairwise.merge(game_cond, on="gameId", how="left") if "condition" not in pairwise.columns else pairwise
    fp = first_phrase_pw.merge(game_cond, on="gameId", how="left") if "condition" not in first_phrase_pw.columns else first_phrase_pw

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)

    for ax, (label, df) in zip(axes, [("Whole utterance", pw), ("First phrase", fp)]):
        rows = []
        for cond in conditions:
            p2 = df[(df["window"] == "phase2_final") & (df["condition"] == cond)] if "window" in df.columns else pd.DataFrame()
            if p2.empty:
                continue
            within = p2[p2["sameGroup"] == 1]["similarity"]
            between = p2[p2["sameGroup"] == 0]["similarity"]
            gs = within.mean() - between.mean() if len(within) > 0 and len(between) > 0 else float("nan")
            rows.append({"condition": format_condition(cond), "GS": gs, "cond_raw": cond})
        if not rows:
            continue
        bar_df = pd.DataFrame(rows)
        colors = [CONDITION_COLORS[r["cond_raw"]] for _, r in bar_df.iterrows()]
        ax.bar(bar_df["condition"], bar_df["GS"], color=colors, alpha=0.8)
        ax.set_ylabel("Group specificity (within − between)" if ax == axes[0] else "")
        ax.set_title(label)
        sns.despine(ax=ax)

    fig.suptitle("Phase 2 group specificity: whole utterance vs first phrase")
    save_fig(fig, output_dir / "first_phrase_comparison.png")
    print(f"  Saved first_phrase_comparison.png")


def plot_term_retention_comparison(data, output_dir, conditions):
    """Overlay Phase 1 term retention curves across conditions."""
    term_retention = data["term_retention"]
    if term_retention.empty:
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    for cond in conditions:
        cond_data = term_retention[term_retention["condition"] == cond]
        if cond_data.empty:
            continue
        means = cond_data.groupby("blockNum")["retention"].mean()
        sems = cond_data.groupby("blockNum")["retention"].sem()
        ax.fill_between(means.index, means - sems, means + sems,
                        color=CONDITION_COLORS[cond], alpha=0.15)
        ax.plot(means.index, means.values, marker="o", markersize=4,
                color=CONDITION_COLORS[cond], linewidth=1.2,
                label=format_condition(cond))
    ax.set_xlabel("Phase 2 block")
    ax.set_ylabel("Mean proportion of Phase 1 terms retained")
    ax.set_title("Phase 1 term retention across Phase 2")
    ax.set_ylim(0, 1.05)
    ax.legend()
    sns.despine(ax=ax)
    save_fig(fig, output_dir / "term_retention_comparison.png")
    print(f"  Saved term_retention_comparison.png")


def plot_alternative_comparison(data, output_dir, conditions):
    """Overlay alternative structure rate across conditions."""
    alt = data["alt_structures"]
    if alt.empty:
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    for cond in conditions:
        cond_data = alt[alt["condition"] == cond]
        if cond_data.empty:
            continue
        means = cond_data.groupby("blockNum")["hasAlternatives"].mean()
        sems = cond_data.groupby("blockNum")["hasAlternatives"].sem()
        ax.fill_between(means.index, means - sems, means + sems,
                        color=CONDITION_COLORS[cond], alpha=0.15)
        ax.plot(means.index, means.values, marker="o", markersize=4,
                color=CONDITION_COLORS[cond], linewidth=1.2,
                label=format_condition(cond))
    ax.set_xlabel("Phase 2 block")
    ax.set_ylabel("Proportion with alternatives")
    ax.set_title("Alternative structure rate across Phase 2")
    ax.set_ylim(-0.05, 1.05)
    ax.legend()
    sns.despine(ax=ax)
    save_fig(fig, output_dir / "alternative_comparison.png")
    print(f"  Saved alternative_comparison.png")


def plot_length_retention_comparison(data, output_dir, conditions):
    """Side-by-side scatter of length vs retention per condition."""
    lr = data["length_retention"]
    if lr.empty:
        return

    from scipy.stats import pearsonr

    present = [c for c in conditions if c in lr["condition"].values]
    if not present:
        return

    fig, axes = plt.subplots(1, len(present), figsize=(5 * len(present), 4.5), sharey=True)
    if len(present) == 1:
        axes = [axes]

    for ax, cond in zip(axes, present):
        cond_data = lr[lr["condition"] == cond]
        for grp in GROUP_ORDER:
            grp_data = cond_data[cond_data["originalGroup"] == grp]
            if grp_data.empty:
                continue
            ax.scatter(grp_data["retention"], grp_data["uttLength"],
                       color=GROUP_COLORS[grp], alpha=0.4, s=20, label=grp)
        valid = cond_data.dropna(subset=["retention", "uttLength"])
        if len(valid) > 2:
            r, p = pearsonr(valid["retention"], valid["uttLength"])
            z = np.polyfit(valid["retention"], valid["uttLength"], 1)
            xs = np.linspace(valid["retention"].min(), valid["retention"].max(), 50)
            ax.plot(xs, np.polyval(z, xs), "k--", linewidth=1, alpha=0.7)
            ax.annotate(f"r={r:.2f}, p={p:.3f}", xy=(0.05, 0.95),
                        xycoords="axes fraction", fontsize=9, va="top")
        ax.set_xlabel("Term retention")
        ax.set_ylabel("Description length" if ax == axes[0] else "")
        ax.set_title(format_condition(cond))
        sns.despine(ax=ax)

    axes[-1].legend(title="Group", fontsize=8, title_fontsize=8)
    fig.suptitle("Description length vs term retention")
    save_fig(fig, output_dir / "length_retention_comparison.png")
    print(f"  Saved length_retention_comparison.png")


def plot_social_retention_standalone(data, output_dir):
    """Standalone figure: social guessing accuracy by speaker retention bins (social_mixed only)."""
    sgr = data["social_guess_retention"]
    if sgr.empty:
        return

    fig, ax = plt.subplots(figsize=(6, 4))
    panel_social_retention(ax, sgr, "social_mixed")
    save_fig(fig, output_dir / "social_retention_standalone.png")
    print(f"  Saved social_retention_standalone.png")


def plot_borrowing_comparison(data, output_dir, conditions):
    """Overlay cross-group borrowing rate across conditions."""
    borrowing = data["cross_group_borrowing"]
    if borrowing.empty:
        return

    df = borrowing[borrowing["nSourceTerms"] > 0]
    if df.empty:
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    for cond in conditions:
        cond_data = df[df["condition"] == cond]
        if cond_data.empty:
            continue
        means = cond_data.groupby("blockNum")["borrowingRate"].mean()
        sems = cond_data.groupby("blockNum")["borrowingRate"].sem()
        ax.fill_between(means.index, means - sems, means + sems,
                        color=CONDITION_COLORS[cond], alpha=0.15)
        ax.plot(means.index, means.values, marker="o", markersize=4,
                color=CONDITION_COLORS[cond], linewidth=1.2,
                label=format_condition(cond))
    ax.set_xlabel("Phase 2 block")
    ax.set_ylabel("Mean borrowing rate")
    ax.set_title("Cross-group term borrowing")
    ax.set_ylim(-0.05, 1.05)
    ax.legend()
    sns.despine(ax=ax)
    save_fig(fig, output_dir / "borrowing_comparison.png")
    print(f"  Saved borrowing_comparison.png")


def plot_audience_design_comparison(data, output_dir, conditions):
    """Side-by-side audience design bar charts per condition."""
    ad = data["audience_design"]
    if ad.empty:
        return

    present = [c for c in conditions if c in ad["condition"].values]
    if not present:
        return

    fig, axes = plt.subplots(1, len(present), figsize=(5 * len(present), 4.5), sharey=True)
    if len(present) == 1:
        axes = [axes]

    order = ["all_same", "mixed", "all_different"]
    for ax, cond in zip(axes, present):
        cond_data = ad[ad["condition"] == cond]
        types_present = [t for t in order if t in cond_data["audienceType"].values]
        if not types_present:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    transform=ax.transAxes)
            continue
        stats = (
            cond_data.groupby("audienceType")["uttLength"]
            .agg(["mean", "sem", "count"])
            .reindex(types_present)
        )
        ax.bar(stats.index, stats["mean"], yerr=stats["sem"],
               color=CONDITION_COLORS[cond], alpha=0.8, capsize=5)
        ax.set_xlabel("Audience composition")
        ax.set_ylabel("Mean description length" if ax == axes[0] else "")
        ax.set_title(format_condition(cond))
        sns.despine(ax=ax)

    fig.suptitle("Audience design: description length by audience type")
    save_fig(fig, output_dir / "audience_design_comparison.png")
    print(f"  Saved audience_design_comparison.png")


def plot_term_dominance_comparison(data, output_dir, conditions):
    """Side-by-side stacked bars of term dominance per condition."""
    td = data["term_dominance"]
    if td.empty:
        return

    present = [c for c in conditions if c in td["condition"].values]
    if not present:
        return

    fig, axes = plt.subplots(1, len(present), figsize=(5 * len(present), 4.5), sharey=True)
    if len(present) == 1:
        axes = [axes]

    for ax, cond in zip(axes, present):
        panel_term_dominance(ax, td[td["condition"] == cond], cond)
        if ax != axes[0]:
            ax.set_ylabel("")

    fig.suptitle("Term dominance across Phase 2")
    save_fig(fig, output_dir / "term_dominance_comparison.png")
    print(f"  Saved term_dominance_comparison.png")


def plot_resolution_rate_comparison(data, output_dir, conditions):
    """Overlay line plot of resolution rate per condition with SEM bands."""
    td = data["term_dominance"]
    if td.empty:
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    for cond in conditions:
        cond_data = td[td["condition"] == cond]
        if cond_data.empty:
            continue
        # Resolution: exactly one group dominates (not tied/none)
        cond_data = cond_data.copy()
        cond_data["resolved"] = (
            ~cond_data["dominantTermSource"].isin(["tied", "none"])
        ).astype(float)
        means = cond_data.groupby("blockNum")["resolved"].mean()
        sems = cond_data.groupby("blockNum")["resolved"].sem()
        ax.fill_between(means.index, means - sems, means + sems,
                        color=CONDITION_COLORS[cond], alpha=0.15)
        ax.plot(means.index, means.values, marker="o", markersize=4,
                color=CONDITION_COLORS[cond], linewidth=1.2,
                label=format_condition(cond))
    ax.set_xlabel("Phase 2 block")
    ax.set_ylabel("Resolution rate")
    ax.set_title("Term dominance resolution rate")
    ax.set_ylim(-0.05, 1.05)
    ax.legend()
    sns.despine(ax=ax)
    save_fig(fig, output_dir / "resolution_rate_comparison.png")
    print(f"  Saved resolution_rate_comparison.png")


def plot_hedging_comparison(data, output_dir, conditions):
    """Overlay condition-mean hedging rate with SEM bands."""
    ht = data["hedging_trajectory"]
    if ht.empty:
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    for cond in conditions:
        cond_data = ht[ht["condition"] == cond]
        if cond_data.empty:
            continue
        means = cond_data.groupby("blockNum")["hedgingRate"].mean()
        sems = cond_data.groupby("blockNum")["hedgingRate"].sem()
        ax.fill_between(means.index, means - sems, means + sems,
                        color=CONDITION_COLORS[cond], alpha=0.15)
        ax.plot(means.index, means.values, marker="o", markersize=4,
                color=CONDITION_COLORS[cond], linewidth=1.2,
                label=format_condition(cond))
    ax.set_xlabel("Phase 2 block")
    ax.set_ylabel("Mean hedging rate")
    ax.set_title("Hedging rate across Phase 2")
    ax.set_ylim(-0.05, 1.05)
    ax.legend()
    sns.despine(ax=ax)
    save_fig(fig, output_dir / "hedging_comparison.png")
    print(f"  Saved hedging_comparison.png")


# ── Faceted by-condition plots (shared y-axis) ────────────────

def _facet_legend_right(g, title="Original group"):
    """Place a compact legend to the right of a FacetGrid without a huge gap."""
    # Remove any auto-generated legend
    if g._legend is not None:
        g._legend.remove()
    # Place legend just outside the last axis
    last_ax = g.axes.flat[-1]
    last_ax.legend(title=title, bbox_to_anchor=(1.04, 0.5), loc="center left",
                   fontsize=11, title_fontsize=11, frameon=False)


def plot_faceted_metrics(data, output_dir, conditions):
    """FacetGrid plots: columns = conditions, hue = original group, shared y-axis."""
    utterances = data["utterances"]
    trials = data["trials"]
    adjacent = data["adjacent"]

    condition_order = sorted(conditions)
    condition_labels = {c: format_condition(c) for c in condition_order}

    # --- Description length ---
    utt = continuous_block(utterances[utterances["condition"].isin(conditions)])
    utt["condition_label"] = utt["condition"].map(condition_labels)
    label_order = [condition_labels[c] for c in condition_order]

    g = sns.FacetGrid(
        utt, col="condition_label", col_order=label_order,
        hue="originalGroup", hue_order=GROUP_ORDER, palette=GROUP_COLORS,
        sharey=True, height=4, aspect=1.0,
    )
    g.map_dataframe(sns.lineplot, x="block", y="uttLength", marker="o", markersize=5, errorbar=None)
    for ax in g.axes.flat:
        add_phase_boundary(ax)
    g.set_axis_labels("Block", "Word count")
    g.set_titles("{col_name}")
    _facet_legend_right(g)
    g.figure.suptitle("Description length", y=1.02)
    g.figure.savefig(output_dir / "facet_description_length.png", dpi=150, bbox_inches="tight")
    plt.close(g.figure)
    print(f"  Saved facet_description_length.png")

    # --- Listener accuracy ---
    listener = continuous_block(
        trials[(trials["role"] == "listener") & trials["condition"].isin(conditions)]
    ).copy()
    listener["correct"] = listener["clickedCorrect"].astype(float)
    listener["condition_label"] = listener["condition"].map(condition_labels)

    g = sns.FacetGrid(
        listener, col="condition_label", col_order=label_order,
        hue="originalGroup", hue_order=GROUP_ORDER, palette=GROUP_COLORS,
        sharey=True, height=4, aspect=1.0,
    )
    g.map_dataframe(sns.lineplot, x="block", y="correct", marker="o", markersize=5, errorbar=None)
    for ax in g.axes.flat:
        add_phase_boundary(ax)
        add_chance_line(ax, 1 / 6, "Chance (1/6)")
        ax.set_ylim(0, 1.05)
    g.set_axis_labels("Block", "Accuracy")
    g.set_titles("{col_name}")
    _facet_legend_right(g)
    g.figure.suptitle("Listener accuracy", y=1.02)
    g.figure.savefig(output_dir / "facet_listener_accuracy.png", dpi=150, bbox_inches="tight")
    plt.close(g.figure)
    print(f"  Saved facet_listener_accuracy.png")

    # --- Convention stability ---
    adj = continuous_block(
        adjacent[adjacent["simAdjacent"].notna() & adjacent["condition"].isin(conditions)]
    ).copy()
    adj["condition_label"] = adj["condition"].map(condition_labels)

    g = sns.FacetGrid(
        adj, col="condition_label", col_order=label_order,
        hue="originalGroup", hue_order=GROUP_ORDER, palette=GROUP_COLORS,
        sharey=True, height=4, aspect=1.0,
    )
    g.map_dataframe(sns.lineplot, x="block", y="simAdjacent", marker="o", markersize=5, errorbar=None)
    for ax in g.axes.flat:
        add_phase_boundary(ax)
        ax.set_ylim(0, 1.05)
    g.set_axis_labels("Block", "Cosine similarity")
    g.set_titles("{col_name}")
    _facet_legend_right(g)
    g.figure.suptitle("Convention stability", y=1.02)
    g.figure.savefig(output_dir / "facet_convention_stability.png", dpi=150, bbox_inches="tight")
    plt.close(g.figure)
    print(f"  Saved facet_convention_stability.png")

    # --- Phase change similarity ---
    phase_change = data["phase_change"]
    if not phase_change.empty:
        pc = phase_change[phase_change["condition"].isin(conditions)].copy()
        pc["condition_label"] = pc["condition"].map(condition_labels)
        pc_label_order = [condition_labels[c] for c in condition_order if c in pc["condition"].unique()]

        if not pc.empty:
            g = sns.FacetGrid(
                pc, col="condition_label", col_order=pc_label_order,
                sharey=True, height=4, aspect=1.0,
            )
            g.map_dataframe(sns.boxplot, x="originalGroup", y="simPhase1Phase2",
                            order=GROUP_ORDER, palette=GROUP_COLORS, width=0.5)
            g.map_dataframe(sns.stripplot, x="originalGroup", y="simPhase1Phase2",
                            order=GROUP_ORDER, color="black", alpha=0.4, size=3, jitter=True)
            for ax in g.axes.flat:
                ax.set_ylim(0, 1.05)
                sns.despine(ax=ax)
            g.set_axis_labels("Original group", "Cosine similarity")
            g.set_titles("{col_name}")
            g.figure.suptitle("Phase 1 → 2 description stability", y=1.02)
            g.figure.savefig(output_dir / "facet_phase_change.png", dpi=150, bbox_inches="tight")
            plt.close(g.figure)
            print(f"  Saved facet_phase_change.png")


# ── Composite overview figure ─────────────────────────────────

def plot_composite(data, output_dir, conditions):
    """4-row composite: length, accuracy, stability, group specificity by condition."""
    utterances = data["utterances"]
    trials = data["trials"]
    adjacent = data["adjacent"]
    pairwise = data["pairwise"]

    n_cond = len(conditions)
    fig = plt.figure(figsize=(6 * n_cond, 20))
    gs = gridspec.GridSpec(4, n_cond, hspace=0.35, wspace=0.3)

    listener_trials = trials[trials["role"] == "listener"].copy()
    listener_trials["clickedCorrect"] = listener_trials["clickedCorrect"].astype(float)
    adj_valid = adjacent[adjacent["simAdjacent"].notna()].copy()

    for idx, cond in enumerate(conditions):
        color = CONDITION_COLORS[cond]

        # Row 1: Description length
        ax = fig.add_subplot(gs[0, idx])
        cond_utt = continuous_block(utterances[utterances["condition"] == cond])
        means = cond_utt.groupby("block")["uttLength"].mean()
        sems = cond_utt.groupby("block")["uttLength"].sem()
        ax.fill_between(means.index, means - sems, means + sems, color=color, alpha=0.15)
        ax.plot(means.index, means.values, marker="o", markersize=4, color=color, linewidth=1.2)
        add_phase_boundary(ax)
        ax.set_xlabel("Block")
        ax.set_ylabel("Words" if idx == 0 else "")
        ax.set_title(f"Description length ({format_condition(cond)})")

        # Row 2: Listener accuracy
        ax = fig.add_subplot(gs[1, idx])
        cond_t = continuous_block(listener_trials[listener_trials["condition"] == cond])
        means = cond_t.groupby("block")["clickedCorrect"].mean()
        sems = cond_t.groupby("block")["clickedCorrect"].sem()
        ax.fill_between(means.index, means - sems, means + sems, color=color, alpha=0.15)
        ax.plot(means.index, means.values, marker="o", markersize=4, color=color, linewidth=1.2)
        add_phase_boundary(ax)
        add_chance_line(ax, 1 / 6)
        ax.set_xlabel("Block")
        ax.set_ylabel("Accuracy" if idx == 0 else "")
        ax.set_ylim(0, 1.05)
        ax.set_title(f"Listener accuracy ({format_condition(cond)})")

        # Row 3: Adjacent similarity
        ax = fig.add_subplot(gs[2, idx])
        cond_adj = continuous_block(adj_valid[adj_valid["condition"] == cond])
        means = cond_adj.groupby("block")["simAdjacent"].mean()
        sems = cond_adj.groupby("block")["simAdjacent"].sem()
        ax.fill_between(means.index, means - sems, means + sems, color=color, alpha=0.15)
        ax.plot(means.index, means.values, marker="o", markersize=4, color=color, linewidth=1.2)
        add_phase_boundary(ax)
        ax.set_xlabel("Block")
        ax.set_ylabel("Cosine similarity" if idx == 0 else "")
        ax.set_title(f"Convention stability ({format_condition(cond)})")

        # Row 4: Group specificity bars
        ax = fig.add_subplot(gs[3, idx])
        cond_pw = pairwise[pairwise["condition"] == cond] if not pairwise.empty and "condition" in pairwise.columns else pd.DataFrame()
        if cond_pw.empty and not pairwise.empty:
            # Try merging condition from games
            game_cond = data["games"][["gameId", "condition"]]
            pw_merged = pairwise.merge(game_cond, on="gameId", how="left")
            cond_pw = pw_merged[pw_merged["condition"] == cond]
        panel_group_specificity(ax, cond_pw, cond)

    fig.suptitle(f"Pilot data overview (N={len(data['games'])} games)", y=0.98)
    save_fig(fig, output_dir / "composite_overview.png")
    print(f"  Saved composite_overview.png")


# ── Statistical summaries ─────────────────────────────────────

def print_summary(data, conditions):
    """Print descriptive statistics to stdout."""
    games = data["games"]
    players = data["players"]
    trials = data["trials"]
    utterances = data["utterances"]
    messages = data["messages"]
    adjacent = data["adjacent"]
    pairwise = data["pairwise"]
    phase_change = data["phase_change"]
    social = data["social"]

    print("\n" + "=" * 60)
    print("PILOT DATA SUMMARY")
    print("=" * 60)
    print(f"\nGames: {len(games)}")
    for _, g in games.iterrows():
        print(f"  {g['condition']}: gameId={g['gameId'][:20]}... "
              f"players={g['numPlayers']:.0f} p1blocks={g['phase1Blocks']:.0f} p2blocks={g['phase2Blocks']:.0f}")
    print(f"\nTotal players: {len(players)}")
    print(f"Total trials: {len(trials)}")
    print(f"Total messages: {len(messages)}")
    print(f"Total speaker utterances: {len(utterances)}")

    # Description length
    print("\n--- Description length ---")
    for cond in conditions:
        cond_utt = utterances[utterances["condition"] == cond]
        p1 = cond_utt[cond_utt["phaseNum"] == 1]
        p2 = cond_utt[cond_utt["phaseNum"] == 2]
        print(f"  {cond}:")
        print(f"    Phase 1: {p1['uttLength'].mean():.1f} words (SD={p1['uttLength'].std():.1f})")
        print(f"    Phase 2: {p2['uttLength'].mean():.1f} words (SD={p2['uttLength'].std():.1f})")

    # Listener accuracy
    print("\n--- Listener accuracy ---")
    listener = trials[(trials["role"] == "listener") & trials["clickedCorrect"].notna()].copy()
    listener["clickedCorrect"] = listener["clickedCorrect"].astype(float)
    for cond in conditions:
        ct = listener[listener["condition"] == cond]
        p1 = ct[ct["phaseNum"] == 1]
        p2 = ct[ct["phaseNum"] == 2]
        print(f"  {cond}:")
        print(f"    Phase 1: {p1['clickedCorrect'].mean():.3f}")
        print(f"    Phase 2: {p2['clickedCorrect'].mean():.3f}")

    # Adjacent similarity
    print("\n--- Convention stability (adjacent similarity) ---")
    adj_valid = adjacent[adjacent["simAdjacent"].notna()]
    for cond in conditions:
        ca = adj_valid[adj_valid["condition"] == cond]
        p1 = ca[ca["phaseNum"] == 1]
        p2 = ca[ca["phaseNum"] == 2]
        print(f"  {cond}:")
        print(f"    Phase 1: {p1['simAdjacent'].mean():.3f}")
        print(f"    Phase 2: {p2['simAdjacent'].mean():.3f}")

    # Pairwise / group specificity
    if not pairwise.empty:
        print("\n--- Group specificity (pairwise similarity) ---")
        pw = pairwise.copy()
        if "condition" not in pw.columns:
            pw = pw.merge(games[["gameId", "condition"]], on="gameId", how="left")
        for cond in conditions:
            cpw = pw[pw["condition"] == cond]
            for window in ["phase1_final", "phase2_final"]:
                wd = cpw[cpw["window"] == window]
                within = wd[wd["sameGroup"] == 1]["similarity"]
                between = wd[wd["sameGroup"] == 0]["similarity"]
                gs = within.mean() - between.mean() if len(within) > 0 and len(between) > 0 else float("nan")
                print(f"  {cond} {window}: within={within.mean():.3f} between={between.mean():.3f} GS={gs:.3f}")

    # First-phrase group specificity
    first_phrase_pw = data.get("first_phrase_pw", pd.DataFrame())
    if not first_phrase_pw.empty:
        print("\n--- First-phrase group specificity ---")
        fp = first_phrase_pw.copy()
        if "condition" not in fp.columns:
            fp = fp.merge(games[["gameId", "condition"]], on="gameId", how="left")
        for cond in conditions:
            cfp = fp[fp["condition"] == cond]
            for window in ["phase1_final", "phase2_final"]:
                wd = cfp[cfp["window"] == window]
                within = wd[wd["sameGroup"] == 1]["similarity"]
                between = wd[wd["sameGroup"] == 0]["similarity"]
                gs = within.mean() - between.mean() if len(within) > 0 and len(between) > 0 else float("nan")
                print(f"  {cond} {window}: within={within.mean():.3f} between={between.mean():.3f} GS={gs:.3f}")

    # Block-by-block convergence
    block_pw = data.get("block_pw", pd.DataFrame())
    if not block_pw.empty:
        print("\n--- Block-by-block convergence (Phase 2 between-group sim) ---")
        bp = block_pw.copy()
        if "condition" not in bp.columns:
            bp = bp.merge(games[["gameId", "condition"]], on="gameId", how="left")
        between = bp[bp["sameGroup"] == 0]
        for cond in conditions:
            cond_between = between[between["condition"] == cond]
            if cond_between.empty:
                continue
            block_means = cond_between.groupby("blockNum")["similarity"].mean()
            vals = " ".join(f"b{int(b)}={v:.3f}" for b, v in block_means.items())
            print(f"  {cond}: {vals}")

    # Term retention
    term_retention = data.get("term_retention", pd.DataFrame())
    if not term_retention.empty:
        print("\n--- Phase 1 term retention ---")
        for cond in conditions:
            cond_tr = term_retention[term_retention["condition"] == cond]
            if cond_tr.empty:
                continue
            block_means = cond_tr.groupby("blockNum")["retention"].mean()
            vals = " ".join(f"b{int(b)}={v:.3f}" for b, v in block_means.items())
            overall = cond_tr["retention"].mean()
            print(f"  {cond}: overall={overall:.3f} | {vals}")

    # Alternative structures
    alt_structures = data.get("alt_structures", pd.DataFrame())
    if not alt_structures.empty:
        print("\n--- Alternative structures (Phase 2) ---")
        for cond in conditions:
            cond_alt = alt_structures[alt_structures["condition"] == cond]
            if cond_alt.empty:
                continue
            rate = cond_alt["hasAlternatives"].mean()
            n_with = cond_alt["hasAlternatives"].sum()
            print(f"  {cond}: {rate:.3f} ({n_with}/{len(cond_alt)} utterances)")

    # Length × retention
    length_retention = data.get("length_retention", pd.DataFrame())
    if not length_retention.empty:
        from scipy.stats import pearsonr
        print("\n--- Length × retention correlation ---")
        for cond in conditions:
            cond_lr = length_retention[length_retention["condition"] == cond].dropna(
                subset=["retention", "uttLength"]
            )
            if len(cond_lr) > 2:
                r, p = pearsonr(cond_lr["retention"], cond_lr["uttLength"])
                print(f"  {cond}: r={r:.3f} p={p:.4f} N={len(cond_lr)}")

    # Social guess × retention
    social_guess_retention = data.get("social_guess_retention", pd.DataFrame())
    if not social_guess_retention.empty:
        print("\n--- Social guess × speaker retention ---")
        sgr = social_guess_retention.dropna(subset=["speakerRetention", "socialGuessCorrect"])
        if not sgr.empty:
            print(f"  N={len(sgr)} observations")
            high = sgr[sgr["speakerRetention"] >= sgr["speakerRetention"].quantile(0.67)]
            low = sgr[sgr["speakerRetention"] <= sgr["speakerRetention"].quantile(0.33)]
            if not high.empty:
                print(f"  High retention: accuracy={high['socialGuessCorrect'].astype(float).mean():.3f}")
            if not low.empty:
                print(f"  Low retention: accuracy={low['socialGuessCorrect'].astype(float).mean():.3f}")

    # Cross-group borrowing
    cross_group_borrowing = data.get("cross_group_borrowing", pd.DataFrame())
    if not cross_group_borrowing.empty:
        print("\n--- Cross-group borrowing ---")
        df_b = cross_group_borrowing[cross_group_borrowing["nSourceTerms"] > 0]
        for cond in conditions:
            cond_b = df_b[df_b["condition"] == cond]
            if cond_b.empty:
                continue
            block_means = cond_b.groupby("blockNum")["borrowingRate"].mean()
            vals = " ".join(f"b{int(b)}={v:.3f}" for b, v in block_means.items())
            overall = cond_b["borrowingRate"].mean()
            print(f"  {cond}: overall={overall:.3f} | {vals}")

    # Audience design
    audience_design = data.get("audience_design", pd.DataFrame())
    if not audience_design.empty:
        print("\n--- Audience design ---")
        for cond in conditions:
            cond_ad = audience_design[audience_design["condition"] == cond]
            if cond_ad.empty:
                continue
            type_stats = cond_ad.groupby("audienceType")["uttLength"].agg(["mean", "count"])
            parts = [f"{t}: len={row['mean']:.1f} (n={row['count']:.0f})"
                     for t, row in type_stats.iterrows()]
            print(f"  {cond}: {' | '.join(parts)}")

    # Term dominance
    term_dominance = data.get("term_dominance", pd.DataFrame())
    if not term_dominance.empty:
        print("\n--- Term dominance ---")
        for cond in conditions:
            cond_td = term_dominance[term_dominance["condition"] == cond]
            if cond_td.empty:
                continue
            # Distribution of dominant sources
            dist = cond_td["dominantTermSource"].value_counts()
            total = len(cond_td)
            parts = [f"{src}: {cnt} ({cnt/total:.1%})" for src, cnt in dist.items()]
            print(f"  {cond}: {' | '.join(parts)}")
            # Resolution rate by block
            cond_td = cond_td.copy()
            cond_td["resolved"] = (~cond_td["dominantTermSource"].isin(["tied", "none"])).astype(float)
            block_res = cond_td.groupby("blockNum")["resolved"].mean()
            vals = " ".join(f"b{int(b)}={v:.3f}" for b, v in block_res.items())
            print(f"    resolution rate: {vals}")

    # Hedging trajectory
    hedging_trajectory = data.get("hedging_trajectory", pd.DataFrame())
    if not hedging_trajectory.empty:
        print("\n--- Hedging trajectory ---")
        for cond in conditions:
            cond_ht = hedging_trajectory[hedging_trajectory["condition"] == cond]
            if cond_ht.empty:
                continue
            block_means = cond_ht.groupby("blockNum")["hedgingRate"].mean()
            vals = " ".join(f"b{int(b)}={v:.3f}" for b, v in block_means.items())
            # Proportion of speakers who ever hedged
            final_block = cond_ht["blockNum"].max()
            final = cond_ht[cond_ht["blockNum"] == final_block]
            ever_hedged = final["hasEverHedged"].mean() if not final.empty else 0
            print(f"  {cond}: hedgingRate {vals} | everHedged={ever_hedged:.1%}")

    # Phase change
    if not phase_change.empty:
        print("\n--- Phase change similarity ---")
        for cond in conditions:
            cpc = phase_change[phase_change["condition"] == cond]
            vals = cpc["simPhase1Phase2"].dropna()
            if len(vals) > 0:
                print(f"  {cond}: mean={vals.mean():.3f} SD={vals.std():.3f} N={len(vals)}")

    # Social guessing
    if not social.empty:
        print("\n--- Social guessing ---")
        sg = social.copy()
        sg["correct"] = sg["socialGuessCorrect"].astype(float)
        print(f"  Overall accuracy: {sg['correct'].mean():.3f}")
        print(f"  Chance: 0.333 (1/3)")
        print(f"  N guesses: {len(sg)}")

    # Player summaries
    print("\n--- Player summaries ---")
    active = players[players["isActive"] == True] if "isActive" in players.columns else players
    print(f"  Active: {len(active)} / {len(players)}")
    if "score" in players.columns:
        print(f"  Mean score: {active['score'].mean():.1f} (SD={active['score'].std():.1f})")
    if "bonus" in players.columns:
        print(f"  Mean bonus: ${active['bonus'].mean():.2f} (range ${active['bonus'].min():.2f}–${active['bonus'].max():.2f})")
    if "idleRounds" in players.columns:
        idle = players["idleRounds"].fillna(0)
        n_idle = (idle > 0).sum()
        if n_idle > 0:
            print(f"  Players with idle rounds: {n_idle} (counts: {idle[idle > 0].tolist()})")

    # Exit survey
    exit_cols = [c for c in players.columns if c.startswith("exitSurvey_")]
    if exit_cols:
        print("\n--- Exit survey ---")
        for col in exit_cols:
            field = col.replace("exitSurvey_", "")
            vals = players[col].dropna()
            if len(vals) == 0:
                continue
            try:
                numeric_vals = pd.to_numeric(vals, errors="raise")
                print(f"  {field}: mean={numeric_vals.mean():.1f}, SD={numeric_vals.std():.1f}")
            except (ValueError, TypeError):
                print(f"  {field}: {dict(vals.value_counts())}")


# ── Per-condition visualization ───────────────────────────────

def visualize_condition(condition, game_ids, data_dir, output_dir):
    """Generate all panel plots for a single condition."""
    print(f"\nCondition: {condition} ({len(game_ids)} games)")

    d = load_data(data_dir, game_ids)

    panels = [
        ("listener_accuracy", panel_accuracy, [d["trials"], condition]),
        ("description_length", panel_description_length, [d["utterances"], condition]),
        ("convention_stability", panel_convention_stability, [d["adjacent"], condition]),
    ]
    if not d["social"].empty:
        panels.append(("social_guessing", panel_social_guessing, [d["social"], condition]))
    if not d["phase_change"].empty:
        panels.append(("phase_change", panel_phase_change, [d["phase_change"], condition]))
    if not d["pairwise"].empty:
        pairwise_with_cond = d["pairwise"].copy()
        if "condition" not in pairwise_with_cond.columns:
            pairwise_with_cond = pairwise_with_cond.merge(
                d["games"][["gameId", "condition"]], on="gameId", how="left"
            )
        panels.append(("group_specificity", panel_group_specificity, [pairwise_with_cond, condition]))
    if not d["first_phrase_pw"].empty:
        panels.append(("first_phrase_specificity", panel_first_phrase_specificity, [d["first_phrase_pw"], condition]))
    if not d["block_pw"].empty:
        panels.append(("convergence_trajectory", panel_convergence_trajectory, [d["block_pw"], condition]))
    if not d["term_retention"].empty:
        panels.append(("term_retention", panel_term_retention, [d["term_retention"], condition]))
    if not d["alt_structures"].empty:
        panels.append(("alternative_rate", panel_alternative_rate, [d["alt_structures"], condition]))
    if not d["length_retention"].empty:
        panels.append(("length_retention", panel_length_retention, [d["length_retention"], condition]))
    if not d["social_guess_retention"].empty:
        panels.append(("social_retention", panel_social_retention, [d["social_guess_retention"], condition]))
    if not d["cross_group_borrowing"].empty:
        panels.append(("borrowing_rate", panel_borrowing_rate, [d["cross_group_borrowing"], condition]))
    if not d["audience_design"].empty:
        panels.append(("audience_design", panel_audience_design, [d["audience_design"], condition]))
    if not d["term_dominance"].empty:
        panels.append(("term_dominance", panel_term_dominance, [d["term_dominance"], condition]))
    if not d["hedging_trajectory"].empty:
        panels.append(("hedging_trajectory", panel_hedging_trajectory, [d["hedging_trajectory"], condition]))
    panels += [
        ("ingroup_outgroup", panel_ingroup_outgroup, [d["trials"], condition]),
        ("umap", panel_umap, [d["umap_df"], condition]),
    ]

    for name, func, panel_args in panels:
        fig, ax = plt.subplots(figsize=(6, 4))
        func(ax, *panel_args)
        path = output_dir / f"pilot_{condition}_{name}.png"
        save_fig(fig, path)
        print(f"  Saved {name}")


# ── Main ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Pilot data analysis and visualization")
    parser.add_argument(
        "--data-dir", default="analysis/processed_data/",
        help="Path to preprocessed CSVs (default: analysis/processed_data/)",
    )
    parser.add_argument(
        "--output-dir", default=None,
        help="Path to write output figures (default: {data-dir}/../outputs/)",
    )
    parser.add_argument(
        "--condition", "-c", default=None,
        help="Single condition to visualize (default: all discovered conditions)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        # Default: sibling outputs/pilot_summary/ next to data/
        output_dir = data_dir.parent / "outputs"

    if not (data_dir / "games.csv").exists():
        print(f"games.csv not found in {data_dir}")
        return

    apply_style()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Discover conditions
    all_conditions = discover_conditions(data_dir)
    print(f"Discovered conditions: {list(all_conditions.keys())}")

    if args.condition:
        if args.condition not in all_conditions:
            print(f"Condition '{args.condition}' not found. Available: {list(all_conditions.keys())}")
            return
        all_conditions = {args.condition: all_conditions[args.condition]}

    # Collect all game IDs
    all_game_ids = []
    for ids in all_conditions.values():
        all_game_ids.extend(ids)
    conditions_list = list(all_conditions.keys())

    # Load all data for cross-condition plots and summaries
    all_data = load_data(data_dir, all_game_ids)

    # Merge condition info into dataframes that need it
    game_condition = all_data["games"][["gameId", "condition"]].copy()
    for key in ["utterances", "trials", "adjacent"]:
        if "condition" not in all_data[key].columns:
            all_data[key] = all_data[key].merge(game_condition, on="gameId", how="left")

    # Per-condition panel plots
    for condition, game_ids in all_conditions.items():
        visualize_condition(condition, game_ids, data_dir, output_dir)

    # Cross-condition comparison plots (only if 2+ conditions)
    if len(conditions_list) >= 2:
        print("\nCross-condition comparison plots:")
        plot_cross_condition(all_data, output_dir, conditions_list)
        plot_phase_change_comparison(all_data, output_dir, conditions_list)
        plot_convergence_comparison(all_data, output_dir, conditions_list)
        plot_first_phrase_comparison(all_data, output_dir, conditions_list)
        plot_term_retention_comparison(all_data, output_dir, conditions_list)
        plot_alternative_comparison(all_data, output_dir, conditions_list)
        plot_length_retention_comparison(all_data, output_dir, conditions_list)
        plot_borrowing_comparison(all_data, output_dir, conditions_list)
        plot_audience_design_comparison(all_data, output_dir, conditions_list)
        plot_term_dominance_comparison(all_data, output_dir, conditions_list)
        plot_resolution_rate_comparison(all_data, output_dir, conditions_list)
        plot_hedging_comparison(all_data, output_dir, conditions_list)

    # Social retention standalone (social_mixed only, doesn't need 2+ conditions)
    print("\nStandalone plots:")
    plot_social_retention_standalone(all_data, output_dir)

    # Faceted by-condition plots (shared y-axis)
    if len(conditions_list) >= 2:
        print("\nFaceted by-condition plots:")
        plot_faceted_metrics(all_data, output_dir, conditions_list)

    # Composite overview
    print("\nComposite overview:")
    plot_composite(all_data, output_dir, conditions_list)

    # Print statistical summaries
    print_summary(all_data, conditions_list)

    print(f"\nAll figures saved to {output_dir}/")


if __name__ == "__main__":
    main()
