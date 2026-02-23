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

    # Filter to specified games
    for df_name in ["trials", "messages", "utterances", "adjacent",
                     "pairwise", "phase_change", "umap_df", "social", "players"]:
        df = locals()[df_name]
        if not df.empty and "gameId" in df.columns:
            locals()[df_name] = df[df["gameId"].isin(game_ids)].copy()

    return {
        "games": games[games["gameId"].isin(game_ids)].copy(),
        "players": players[players["gameId"].isin(game_ids)].copy() if "gameId" in players.columns else players,
        "trials": trials[trials["gameId"].isin(game_ids)].copy(),
        "messages": messages[messages["gameId"].isin(game_ids)].copy(),
        "utterances": utterances[utterances["gameId"].isin(game_ids)].copy(),
        "adjacent": adjacent[adjacent["gameId"].isin(game_ids)].copy(),
        "pairwise": pairwise[pairwise["gameId"].isin(game_ids)].copy() if not pairwise.empty else pairwise,
        "phase_change": phase_change[phase_change["gameId"].isin(game_ids)].copy() if not phase_change.empty else phase_change,
        "umap_df": umap_df[umap_df["gameId"].isin(game_ids)].copy() if not umap_df.empty else umap_df,
        "social": social[social["gameId"].isin(game_ids)].copy() if not social.empty else social,
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

    # Composite overview
    print("\nComposite overview:")
    plot_composite(all_data, output_dir, conditions_list)

    # Print statistical summaries
    print_summary(all_data, conditions_list)

    print(f"\nAll figures saved to {output_dir}/")


if __name__ == "__main__":
    main()
