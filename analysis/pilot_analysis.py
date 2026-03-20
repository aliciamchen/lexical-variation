"""
Pilot data analysis and visualization.

Auto-discovers conditions from games.csv, generates 3-panel comparison plots
(one panel per condition, shared y-axis) and prints descriptive statistics.

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
import numpy as np
import pandas as pd
import seaborn as sns

from plot_style import (
    apply_style,
    CONDITION_COLORS,
    CONDITION_ORDER,
    GROUP_COLORS,
    GROUP_ORDER,
    QUALITATIVE_COLORS,
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
    adjacent_path = data_dir / "adjacent_similarities.csv"
    adjacent = pd.read_csv(adjacent_path) if adjacent_path.exists() else pd.DataFrame()

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


def panel_phase_change_early(ax, phase_change, condition=""):
    """End-of-Phase-1 vs start-of-Phase-2 similarity (boxplot + strip)."""
    col = "simP1FinalP2Early"
    if col not in phase_change.columns:
        ax.text(0.5, 0.5, "No early phase-change data\n(re-run embeddings)",
                ha="center", va="center", transform=ax.transAxes)
        return
    sns.boxplot(
        data=phase_change, x="originalGroup", y=col,
        order=GROUP_ORDER, palette=GROUP_COLORS, width=0.5, ax=ax,
    )
    sns.stripplot(
        data=phase_change, x="originalGroup", y=col,
        order=GROUP_ORDER, color="black", alpha=0.4, size=3,
        jitter=True, ax=ax,
    )
    ax.set_xlabel("Original group")
    ax.set_ylabel("Cosine similarity")
    ax.set_title(f"Phase 1 end → 2 start stability ({format_condition(condition)})")
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

    dodge_map = {"A": -0.08, "B": 0.0, "C": 0.08}
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


def panel_listener_accommodation(ax, trials, condition=""):
    """Listener accommodation: accuracy gap (same-group − cross-group) by Phase 2 block."""
    p2 = continuous_block(
        trials[(trials["phaseNum"] == 2) & (trials["role"] == "listener")]
    )
    p2["correct"] = p2["clickedCorrect"].astype(float)
    p2["matchType"] = (p2["originalGroup"] == p2["currentGroup"]).map(
        {True: "same", False: "cross"}
    )
    # Compute per-block mean accuracy for each match type
    block_acc = p2.groupby(["block", "matchType"])["correct"].mean().unstack("matchType")
    if "same" not in block_acc.columns or "cross" not in block_acc.columns:
        ax.text(0.5, 0.5, "Insufficient data", ha="center", va="center",
                transform=ax.transAxes)
        return
    gap = block_acc["same"] - block_acc["cross"]

    # Per-target accuracy gap as individual points
    tgt_acc = p2.groupby(["block", "target", "matchType"])["correct"].mean().unstack("matchType")
    if "same" in tgt_acc.columns and "cross" in tgt_acc.columns:
        tgt_gap = (tgt_acc["same"] - tgt_acc["cross"]).reset_index()
        tgt_gap.columns = ["block", "target", "gap"]
        tgt_gap = tgt_gap.dropna()
        jitter = np.random.default_rng(42).uniform(-0.15, 0.15, len(tgt_gap))
        ax.scatter(tgt_gap["block"] + jitter, tgt_gap["gap"],
                   color=GROUP_COLORS["A"], alpha=0.2, s=12, zorder=1)

    ax.plot(gap.index, gap.values, marker="o", color=GROUP_COLORS["A"], zorder=3)
    ax.axhline(0, color="gray", linestyle=":", alpha=0.5)
    ax.set_xlabel("Phase 2 block")
    ax.set_ylabel("Accuracy gap (same − cross)")
    ax.set_title(f"Listener accommodation ({format_condition(condition)})")
    ax.set_ylim(-0.6, 0.8)
    sns.despine(ax=ax)


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

    windows = [
        ("phase1_final", "Phase 1\n(final 3)"),
        ("phase2_early", "Phase 2\n(first 3)"),
        ("phase2_final", "Phase 2\n(final 3)"),
    ]
    # Only include windows that have data
    windows = [(w, l) for w, l in windows if not pairwise[pairwise["window"] == w].empty]

    rows = []
    for window, label in windows:
        w_data = pairwise[pairwise["window"] == window]
        within = w_data[w_data["sameGroup"] == 1]["similarity"]
        between = w_data[w_data["sameGroup"] == 0]["similarity"]
        rows.append({"phase": label, "type": "Within-group",
                     "mean": within.mean(), "sem": within.sem()})
        rows.append({"phase": label, "type": "Between-group",
                     "mean": between.mean(), "sem": between.sem()})
    bar_df = pd.DataFrame(rows)

    n_windows = len(windows)
    x = np.arange(n_windows)
    width = 0.35
    within_data = bar_df[bar_df["type"] == "Within-group"]
    between_data = bar_df[bar_df["type"] == "Between-group"]
    ax.bar(x - width / 2, within_data["mean"], width, yerr=within_data["sem"],
           color=QUALITATIVE_COLORS[0], alpha=0.8, capsize=5, label="Within-group")
    ax.bar(x + width / 2, between_data["mean"], width, yerr=between_data["sem"],
           color=QUALITATIVE_COLORS[1], alpha=0.8, capsize=5, label="Between-group")
    ax.set_xticks(x)
    ax.set_xticklabels([l for _, l in windows])
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

    windows = [
        ("phase1_final", "Phase 1\n(final 3)"),
        ("phase2_early", "Phase 2\n(first 3)"),
        ("phase2_final", "Phase 2\n(final 3)"),
    ]
    windows = [(w, l) for w, l in windows if not first_phrase_pw[first_phrase_pw["window"] == w].empty]

    rows = []
    for window, label in windows:
        w_data = first_phrase_pw[first_phrase_pw["window"] == window]
        within = w_data[w_data["sameGroup"] == 1]["similarity"]
        between = w_data[w_data["sameGroup"] == 0]["similarity"]
        rows.append({"phase": label, "type": "Within-group",
                     "mean": within.mean(), "sem": within.sem()})
        rows.append({"phase": label, "type": "Between-group",
                     "mean": between.mean(), "sem": between.sem()})
    bar_df = pd.DataFrame(rows)

    n_windows = len(windows)
    x = np.arange(n_windows)
    width = 0.35
    within_data = bar_df[bar_df["type"] == "Within-group"]
    between_data = bar_df[bar_df["type"] == "Between-group"]
    ax.bar(x - width / 2, within_data["mean"], width, yerr=within_data["sem"],
           color=QUALITATIVE_COLORS[0], alpha=0.8, capsize=5, label="Within-group")
    ax.bar(x + width / 2, between_data["mean"], width, yerr=between_data["sem"],
           color=QUALITATIVE_COLORS[1], alpha=0.8, capsize=5, label="Between-group")
    ax.set_xticks(x)
    ax.set_xticklabels([l for _, l in windows])
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
        ("Between-group", between, QUALITATIVE_COLORS[1], "-"),
        ("Within-group", within, QUALITATIVE_COLORS[0], "--"),
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


def panel_specificity_trajectory(ax, block_pw, condition=""):
    """Group-specificity (within − between similarity) across both phases."""
    if block_pw.empty:
        ax.text(0.5, 0.5, "No block pairwise data", ha="center", va="center",
                transform=ax.transAxes)
        return

    within_data = block_pw[block_pw["sameGroup"] == 1]
    between_data = block_pw[block_pw["sameGroup"] == 0]
    if within_data.empty or between_data.empty:
        ax.text(0.5, 0.5, "Need both within- and\nbetween-group pairs",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_title(f"Specificity trajectory ({format_condition(condition)})")
        sns.despine(ax=ax)
        return

    # Use continuous block numbering (Phase 1: 0-5, Phase 2: 6-11)
    block_pw_cb = continuous_block(block_pw)
    within_cb = block_pw_cb[block_pw_cb["sameGroup"] == 1]
    between_cb = block_pw_cb[block_pw_cb["sameGroup"] == 0]

    within_means = within_cb.groupby("block")["similarity"].mean()
    between_means = between_cb.groupby("block")["similarity"].mean()
    common_blocks = sorted(set(within_means.index) & set(between_means.index))
    specificity = within_means[common_blocks] - between_means[common_blocks]

    # Per-tangram specificity for individual points
    within_by_tgt = within_cb.groupby(["block", "target"])["similarity"].mean()
    between_by_tgt = between_cb.groupby(["block", "target"])["similarity"].mean()
    common_idx = within_by_tgt.index.intersection(between_by_tgt.index)
    if not common_idx.empty:
        tgt_spec = within_by_tgt[common_idx] - between_by_tgt[common_idx]
        tgt_spec = tgt_spec.reset_index()
        tgt_spec.columns = ["block", "target", "specificity"]
        jitter = np.random.default_rng(42).uniform(-0.15, 0.15, len(tgt_spec))
        ax.scatter(tgt_spec["block"] + jitter, tgt_spec["specificity"],
                   color=GROUP_COLORS["A"], alpha=0.2, s=12, zorder=1)

    # SEM for the difference (propagated from within/between SEMs)
    sems = []
    for b in common_blocks:
        w = within_cb[within_cb["block"] == b]["similarity"]
        bw = between_cb[between_cb["block"] == b]["similarity"]
        se = (w.sem()**2 + bw.sem()**2)**0.5 if len(w) > 1 and len(bw) > 1 else 0
        sems.append(se)
    sems = pd.Series(sems, index=common_blocks)

    ax.fill_between(common_blocks, specificity.values - sems.values,
                    specificity.values + sems.values,
                    color=GROUP_COLORS["A"], alpha=0.15)
    ax.plot(common_blocks, specificity.values, marker="o", color=GROUP_COLORS["A"],
            zorder=3)
    ax.axhline(0, color="gray", linestyle=":", alpha=0.5)
    ax.set_ylabel("Group specificity\n(within − between sim)")
    ax.set_title(f"Specificity trajectory ({format_condition(condition)})")
    add_phase_boundary(ax)


def plot_specificity_overlay(all_data, conditions, output_dir):
    """Group-specificity trajectory with all conditions overlaid, dodged, condition-colored."""
    block_pw = all_data["block_pw"]
    if block_pw.empty:
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    dodge_width = 0.15  # offset per condition
    n_cond = len(conditions)

    for i, cond in enumerate(conditions):
        cond_data = block_pw[block_pw["condition"] == cond]
        if cond_data.empty:
            continue

        within_data = cond_data[cond_data["sameGroup"] == 1]
        between_data = cond_data[cond_data["sameGroup"] == 0]
        if within_data.empty or between_data.empty:
            continue

        cond_cb = continuous_block(cond_data)
        within_cb = cond_cb[cond_cb["sameGroup"] == 1]
        between_cb = cond_cb[cond_cb["sameGroup"] == 0]

        within_means = within_cb.groupby("block")["similarity"].mean()
        between_means = between_cb.groupby("block")["similarity"].mean()
        common_blocks = sorted(set(within_means.index) & set(between_means.index))
        if not common_blocks:
            continue
        specificity = within_means[common_blocks] - between_means[common_blocks]

        # SEM for the difference
        sems = []
        for b in common_blocks:
            w = within_cb[within_cb["block"] == b]["similarity"]
            bw = between_cb[between_cb["block"] == b]["similarity"]
            se = (w.sem()**2 + bw.sem()**2)**0.5 if len(w) > 1 and len(bw) > 1 else 0
            sems.append(se)
        sems = np.array(sems)

        # Dodge x positions
        offset = (i - (n_cond - 1) / 2) * dodge_width
        x = np.array(common_blocks) + offset
        color = CONDITION_COLORS.get(cond, "gray")

        # Per-tangram individual points
        within_by_tgt = within_cb.groupby(["block", "target"])["similarity"].mean()
        between_by_tgt = between_cb.groupby(["block", "target"])["similarity"].mean()
        common_idx = within_by_tgt.index.intersection(between_by_tgt.index)
        if not common_idx.empty:
            tgt_spec = within_by_tgt[common_idx] - between_by_tgt[common_idx]
            tgt_spec = tgt_spec.reset_index()
            tgt_spec.columns = ["block", "target", "specificity"]
            jitter = np.random.default_rng(42 + i).uniform(-0.08, 0.08, len(tgt_spec))
            ax.scatter(tgt_spec["block"] + offset + jitter, tgt_spec["specificity"],
                       color=color, alpha=0.15, s=10, zorder=1)

        ax.fill_between(x, specificity.values - sems, specificity.values + sems,
                        color=color, alpha=0.12)
        ax.plot(x, specificity.values, marker="o", color=color, zorder=3,
                label=format_condition(cond), markersize=5)

    ax.axhline(0, color="gray", linestyle=":", alpha=0.5)
    ax.set_xlabel("Block")
    ax.set_ylabel("Group specificity\n(within − between sim)")
    ax.set_title("Group-specificity trajectory")
    ax.legend(frameon=False)
    add_phase_boundary(ax)

    save_fig(fig, output_dir / "specificity_overlay.png")
    print(f"  Saved specificity_overlay.png")


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
            # Quantile boundaries may have duplicates; fall back to 2 bins
            median = df["speakerRetention"].median()
            df["retentionBin"] = df["speakerRetention"].apply(
                lambda x: "Low" if x <= median else "High"
            )
            if df["retentionBin"].nunique() < 2:
                ax.text(0.5, 0.5, "Not enough retention variance", ha="center",
                        va="center", transform=ax.transAxes)
                return
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
           yerr=bin_stats["sem"], color=QUALITATIVE_COLORS[0], alpha=0.8, capsize=5)
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


# ── 3-panel plotting ─────────────────────────────────────────

def panel_resolution_rate(ax, term_dominance, condition=''):
    """Resolution rate (one group's terms dominate) by Phase 2 block."""
    if term_dominance.empty:
        ax.text(0.5, 0.5, "No term dominance data", ha="center",
                va="center", transform=ax.transAxes)
        return

    df = term_dominance.copy()
    df["resolved"] = (~df["dominantTermSource"].isin(["tied", "none"])).astype(float)
    means = df.groupby("blockNum")["resolved"].mean()
    sems = df.groupby("blockNum")["resolved"].sem()
    ax.fill_between(means.index, means - sems, means + sems,
                    color="#555555", alpha=0.15)
    ax.plot(means.index, means.values, marker="o", markersize=5,
            color="#555555", linewidth=1.5)
    ax.set_xlabel("Phase 2 block")
    ax.set_ylabel("Resolution rate")
    ax.set_title(f"Term dominance resolution ({format_condition(condition)})")
    ax.set_ylim(-0.05, 1.05)
    sns.despine(ax=ax)


def plot_three_panel(panel_fn, all_data, data_key, conditions, output_dir, filename):
    """Generic 3-panel figure: one panel per condition, shared y-axis."""
    df = all_data[data_key]
    if df.empty:
        return

    n = len(conditions)
    fig, axes = plt.subplots(1, n, figsize=(5 * n, 4.5), sharey=True)
    if n == 1:
        axes = [axes]

    for ax, cond in zip(axes, conditions):
        if "condition" in df.columns:
            subset = df[df["condition"] == cond]
        else:
            subset = df
        if subset.empty:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    transform=ax.transAxes)
            ax.set_title(format_condition(cond))
            continue
        panel_fn(ax, subset, cond)
        if ax != axes[0]:
            ax.set_ylabel("")
            legend = ax.get_legend()
            if legend:
                legend.remove()

    fig.tight_layout()
    save_fig(fig, output_dir / filename)
    print(f"  Saved {filename}")


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
            for window in ["phase1_final", "phase2_early", "phase2_final"]:
                wd = cpw[cpw["window"] == window]
                if wd.empty:
                    continue
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
            for window in ["phase1_final", "phase2_early", "phase2_final"]:
                wd = cfp[cfp["window"] == window]
                if wd.empty:
                    continue
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

    # Group-specificity trajectory
    if not block_pw.empty:
        bp = block_pw.copy()
        if "condition" not in bp.columns:
            bp = bp.merge(games[["gameId", "condition"]], on="gameId", how="left")
        has_within = not bp[bp["sameGroup"] == 1].empty
        if has_within:
            print("\n--- Group-specificity trajectory (within − between sim by block) ---")
            for cond in conditions:
                cond_bp = continuous_block(bp[bp["condition"] == cond])
                within_means = cond_bp[cond_bp["sameGroup"] == 1].groupby("block")["similarity"].mean()
                between_means = cond_bp[cond_bp["sameGroup"] == 0].groupby("block")["similarity"].mean()
                common = sorted(set(within_means.index) & set(between_means.index))
                if common:
                    gs = within_means[common] - between_means[common]
                    vals = " ".join(f"b{int(b)}={v:.3f}" for b, v in gs.items())
                    print(f"  {cond}: {vals}")
        else:
            print("\n--- Group-specificity trajectory: skipped (no within-group pairs in block data) ---")

    # Listener accommodation gap
    print("\n--- Listener accommodation (same − cross accuracy by Phase 2 block) ---")
    for cond in conditions:
        cond_trials = trials[trials["condition"] == cond]
        p2 = cond_trials[(cond_trials["phaseNum"] == 2) & (cond_trials["role"] == "listener")]
        p2 = continuous_block(p2)
        p2["correct"] = p2["clickedCorrect"].astype(float)
        p2["match"] = (p2["originalGroup"] == p2["currentGroup"])
        block_acc = p2.groupby(["block", "match"])["correct"].mean().unstack("match")
        if True in block_acc.columns and False in block_acc.columns:
            gap = block_acc[True] - block_acc[False]
            vals = " ".join(f"b{int(b)}={v:.3f}" for b, v in gap.items())
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
    conditions_list = sorted(
        all_conditions.keys(),
        key=lambda c: CONDITION_ORDER.index(c) if c in CONDITION_ORDER else len(CONDITION_ORDER),
    )

    # Load all data
    all_data = load_data(data_dir, all_game_ids)

    # Ensure condition column exists in all dataframes
    game_condition = all_data["games"][["gameId", "condition"]].copy()
    for key, df in all_data.items():
        if key != "games" and not df.empty and "gameId" in df.columns and "condition" not in df.columns:
            all_data[key] = df.merge(game_condition, on="gameId", how="left")

    # Generate 3-panel plots (one panel per condition, shared y-axis)
    panels = [
        (panel_accuracy, "trials", "listener_accuracy.png"),
        (panel_description_length, "utterances", "description_length.png"),
        (panel_convention_stability, "adjacent", "convention_stability.png"),
        (panel_phase_change, "phase_change", "phase_change.png"),
        (panel_phase_change_early, "phase_change", "phase_change_early.png"),
        (panel_group_specificity, "pairwise", "group_specificity.png"),
        (panel_first_phrase_specificity, "first_phrase_pw", "first_phrase.png"),
        (panel_convergence_trajectory, "block_pw", "convergence.png"),
        (panel_specificity_trajectory, "block_pw", "specificity_trajectory.png"),
        (panel_term_retention, "term_retention", "term_retention.png"),
        (panel_alternative_rate, "alt_structures", "alternative_rate.png"),
        (panel_length_retention, "length_retention", "length_retention.png"),
        (panel_social_retention, "social_guess_retention", "social_retention.png"),
        (panel_borrowing_rate, "cross_group_borrowing", "borrowing_rate.png"),
        (panel_term_dominance, "term_dominance", "term_dominance.png"),
        (panel_resolution_rate, "term_dominance", "resolution_rate.png"),
        (panel_hedging_trajectory, "hedging_trajectory", "hedging_trajectory.png"),
        (panel_ingroup_outgroup, "trials", "ingroup_outgroup.png"),
        (panel_listener_accommodation, "trials", "listener_accommodation.png"),
        (panel_umap, "umap_df", "umap.png"),
    ]

    print("\n3-panel plots:")
    for panel_fn, data_key, filename in panels:
        plot_three_panel(panel_fn, all_data, data_key, conditions_list, output_dir, filename)

    # Overlay plots (all conditions on one axis)
    print("\nOverlay plots:")
    plot_specificity_overlay(all_data, conditions_list, output_dir)

    # Social guessing (social_mixed only, single panel)
    social = all_data["social"]
    if not social.empty:
        fig, ax = plt.subplots(figsize=(6, 4.5))
        panel_social_guessing(ax, social, "social_mixed")
        fig.tight_layout()
        save_fig(fig, output_dir / "social_guessing.png")
        print(f"  Saved social_guessing.png")

    # Print statistical summaries
    print_summary(all_data, conditions_list)

    print(f"\nAll figures saved to {output_dir}/")


if __name__ == "__main__":
    main()
