"""
Compare Experiment 1 vs Experiment 2 data.

Generates three overlay plots:
  1. Group-specificity trajectory (within - between similarity)
  2. Listener accuracy
  3. Abstractness metrics (geometric vocab fraction + semantic drift)

Usage:
    uv run python analysis/compare_exp1_exp2.py

Expects processed data in:
    analysis/20260301_132907/data/  (Experiment 1)
    analysis/20260301_214147/data/  (Experiment 2)
"""

import sys
sys.path.insert(0, "analysis")

import pandas as pd
import numpy as np
import re
import matplotlib.pyplot as plt
from plot_style import (
    apply_style, CONDITION_COLORS, continuous_block,
    add_phase_boundary, format_condition, save_fig, add_chance_line
)
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# ── Config ──────────────────────────────────────────────────

EXP1_DIR = "analysis/20260301_132907/data"
EXP2_DIR = "analysis/20260301_214147/data"
OUTPUT_DIR = "analysis"

CONDITION_COLORS["exp2_social_goal"] = "#D62728"

CONDITIONS = ["social_mixed", "exp2_social_goal"]
COND_LABELS = {
    "social_mixed": "exp1 social mixed",
    "exp2_social_goal": "exp2 social goal",
}
DODGE = 0.12


# ── Stopwords & geometric vocab (for abstractness metric) ──

STOP_WORDS = {
    'i', 'me', 'my', 'we', 'our', 'you', 'your', 'it', 'its', 'the', 'a', 'an',
    'is', 'are', 'was', 'were', 'be', 'been', 'am', 'do', 'did', 'does',
    'has', 'have', 'had', 'will', 'would', 'can', 'could', 'should', 'may',
    'not', 'no', 'but', 'and', 'or', 'if', 'so', 'as', 'at', 'by', 'for',
    'in', 'of', 'on', 'to', 'up', 'with', 'from', 'that', 'this', 'these',
    'those', 'then', 'than', 'just', 'also', 'very', 'too', 'here', 'there',
    'one', 'like', 'looks', 'look', 'looking', 'kind', 'sort', 'again',
    'yes', 'ok', 'same', 'before', 'says', 'said', 'called', 'call',
}

GEOMETRIC_VOCAB = {
    'triangle', 'triangles', 'square', 'squares', 'rectangle', 'rectangles',
    'rhombus', 'diamond', 'parallelogram', 'trapezoid', 'polygon',
    'left', 'right', 'top', 'bottom', 'middle', 'center', 'side', 'sides',
    'point', 'pointing', 'pointed', 'flat', 'tilted', 'askew', 'sideways',
    'shape', 'shapes', 'piece', 'pieces', 'image', 'picture',
    'horizontal', 'vertical', 'diagonal', 'angled', 'rotated', 'offset',
    'symmetrical', 'asymmetrical', 'portion', 'section',
    'small', 'large', 'big', 'long', 'short', 'thin', 'wide', 'narrow',
    'two', 'three', 'four', 'white', 'hole', 'void', 'missing',
}


def geometric_ratio(text):
    """Fraction of content words that are geometric/spatial."""
    if pd.isna(text):
        return np.nan
    words = re.findall(r'[a-z]+', text.lower())
    content_words = [w for w in words if w not in STOP_WORDS and len(w) > 1]
    if not content_words:
        return np.nan
    return sum(1 for w in content_words if w in GEOMETRIC_VOCAB) / len(content_words)


# ── Load data ───────────────────────────────────────────────

def load_data():
    exp1_trials = pd.read_csv(f"{EXP1_DIR}/trials.csv")
    exp2_trials = pd.read_csv(f"{EXP2_DIR}/trials.csv")
    exp1_utt = pd.read_csv(f"{EXP1_DIR}/speaker_utterances.csv")
    exp2_utt = pd.read_csv(f"{EXP2_DIR}/speaker_utterances.csv")
    exp1_pw = pd.read_csv(f"{EXP1_DIR}/block_pairwise_similarities.csv")
    exp2_pw = pd.read_csv(f"{EXP2_DIR}/block_pairwise_similarities.csv")
    exp1_games = pd.read_csv(f"{EXP1_DIR}/games.csv")
    exp2_games = pd.read_csv(f"{EXP2_DIR}/games.csv")

    exp1_cmap = exp1_games.set_index("gameId")["condition"].to_dict()
    exp2_cmap = exp2_games.set_index("gameId")["condition"].to_dict()

    for df in [exp1_trials, exp1_utt, exp1_pw]:
        df["condition"] = df.gameId.map(exp1_cmap)
    for df in [exp2_trials, exp2_utt, exp2_pw]:
        df["condition"] = df.gameId.map(exp2_cmap)

    return (exp1_trials, exp2_trials, exp1_utt, exp2_utt,
            exp1_pw, exp2_pw)


# ── Plot 1: Group-specificity trajectory ────────────────────

def plot_specificity(exp1_pw, exp2_pw):
    block_pw = pd.concat([exp1_pw, exp2_pw], ignore_index=True).dropna(subset=["condition"])
    n_cond = len(CONDITIONS)

    fig, ax = plt.subplots(figsize=(8, 5))

    for i, cond in enumerate(CONDITIONS):
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

        sems = []
        for b in common_blocks:
            w = within_cb[within_cb["block"] == b]["similarity"]
            bw = between_cb[between_cb["block"] == b]["similarity"]
            se = (w.sem()**2 + bw.sem()**2)**0.5 if len(w) > 1 and len(bw) > 1 else 0
            sems.append(se)
        sems = np.array(sems)

        offset = (i - (n_cond - 1) / 2) * DODGE
        x = np.array(common_blocks) + offset
        color = CONDITION_COLORS.get(cond, "gray")

        # Per-tangram points
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
                label=COND_LABELS[cond], markersize=5)

    ax.axhline(0, color="gray", linestyle=":", alpha=0.5)
    ax.set_xlabel("Block")
    ax.set_ylabel("Group specificity\n(within − between sim)")
    ax.set_title("Group-specificity trajectory")
    ax.legend(frameon=False)
    add_phase_boundary(ax)
    save_fig(fig, f"{OUTPUT_DIR}/specificity_overlay_exp1_exp2.png")
    print("Saved specificity_overlay_exp1_exp2.png")


# ── Plot 2: Listener accuracy ──────────────────────────────

def plot_listener_accuracy(exp1_trials, exp2_trials):
    all_trials = pd.concat([exp1_trials, exp2_trials], ignore_index=True)
    all_trials = all_trials.dropna(subset=["condition"])
    listeners = all_trials[all_trials.role == "listener"].copy()
    listeners["clickedCorrect"] = listeners["clickedCorrect"].astype(float)
    listeners["blockNum"] = listeners["blockNum"].astype(float)
    listeners["phaseNum"] = listeners["phaseNum"].astype(float)
    listeners = continuous_block(listeners)

    n_cond = len(CONDITIONS)
    fig, ax = plt.subplots(figsize=(8, 5))

    for i, cond in enumerate(CONDITIONS):
        cond_data = listeners[listeners["condition"] == cond]
        if cond_data.empty:
            continue
        block_acc = cond_data.groupby("block")["clickedCorrect"].agg(["mean", "sem", "count"])
        blocks = block_acc.index.values.astype(float)
        means = block_acc["mean"].values.astype(float)
        sems = block_acc["sem"].values.astype(float)

        offset = (i - (n_cond - 1) / 2) * DODGE
        x = blocks + offset
        color = CONDITION_COLORS.get(cond, "gray")

        player_acc = cond_data.groupby(["block", "playerId"])["clickedCorrect"].mean().reset_index()
        jitter = np.random.default_rng(42 + i).uniform(-0.06, 0.06, len(player_acc))
        ax.scatter(player_acc["block"].values.astype(float) + offset + jitter,
                   player_acc["clickedCorrect"].values.astype(float),
                   color=color, alpha=0.12, s=10, zorder=1)

        ax.fill_between(x, means - sems, means + sems, color=color, alpha=0.12)
        ax.plot(x, means, marker="o", color=color, zorder=3,
                label=COND_LABELS[cond], markersize=5)

    add_chance_line(ax, 1/6, label="Chance (1/6)")
    ax.set_xlabel("Block")
    ax.set_ylabel("Listener accuracy")
    ax.set_title("Listener accuracy")
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=False, loc="lower right")
    add_phase_boundary(ax)
    save_fig(fig, f"{OUTPUT_DIR}/listener_accuracy_exp1_exp2.png")
    print("Saved listener_accuracy_exp1_exp2.png")


# ── Plot 3: Abstractness metrics ───────────────────────────

def plot_abstractness(exp1_utt, exp2_utt):
    all_utt = pd.concat([exp1_utt, exp2_utt], ignore_index=True).dropna(subset=["condition"]).copy()
    all_utt["geo_ratio"] = all_utt.utterance.apply(geometric_ratio)

    # Semantic drift from block 0
    print("Loading SBERT...")
    model = SentenceTransformer('paraphrase-MiniLM-L12-v2')
    embeddings = model.encode(all_utt.utterance.fillna("").tolist(), show_progress_bar=False)
    all_utt["emb_idx"] = range(len(all_utt))

    drift_vals = np.full(len(all_utt), np.nan)
    for (game, group, target), idx in all_utt.groupby(["gameId", "originalGroup", "target"]).groups.items():
        sub = all_utt.loc[idx]
        ref = sub[(sub.blockNum == 0) & (sub.phaseNum == 1)]
        if ref.empty:
            continue
        ref_emb = embeddings[ref.iloc[0].emb_idx].reshape(1, -1)
        for row_idx in idx:
            sim = cosine_similarity(ref_emb, embeddings[all_utt.loc[row_idx, "emb_idx"]].reshape(1, -1))[0, 0]
            drift_vals[all_utt.index.get_loc(row_idx)] = 1 - sim
    all_utt["drift"] = drift_vals

    all_utt["blockNum"] = all_utt["blockNum"].astype(float)
    all_utt["phaseNum"] = all_utt["phaseNum"].astype(float)
    all_utt = continuous_block(all_utt)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    panels = [
        (axes[0], "geo_ratio", "Geometric vocab ratio",
         "Geometric vocabulary fraction", (0, 0.85)),
        (axes[1], "drift", "Semantic drift\n(1 \u2212 cos sim to block 0)",
         "Semantic drift from initial description", (-0.02, 0.75)),
    ]

    for ax, metric, ylabel, title, ylim in panels:
        for i, cond in enumerate(CONDITIONS):
            cond_data = all_utt[all_utt.condition == cond]
            block_stats = cond_data.groupby("block")[metric].agg(["mean", "sem"])
            blocks = block_stats.index.values.astype(float)
            means = block_stats["mean"].values.astype(float)
            sems = block_stats["sem"].values.astype(float)

            offset = (i - (len(CONDITIONS) - 1) / 2) * DODGE
            x = blocks + offset
            color = CONDITION_COLORS.get(cond, "gray")

            group_means = cond_data.groupby(["block", "originalGroup"])[metric].mean().reset_index()
            jitter = np.random.default_rng(42 + i).uniform(-0.06, 0.06, len(group_means))
            ax.scatter(
                group_means["block"].values.astype(float) + offset + jitter,
                group_means[metric].values.astype(float),
                color=color, alpha=0.15, s=12, zorder=1,
            )

            ax.fill_between(x, means - sems, means + sems, color=color, alpha=0.12)
            ax.plot(x, means, marker="o", color=color, zorder=3,
                    label=COND_LABELS[cond], markersize=5)

        ax.set_xlabel("Block")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        if ylim:
            ax.set_ylim(*ylim)
        ax.legend(frameon=False, fontsize=10)
        add_phase_boundary(ax)

    save_fig(fig, f"{OUTPUT_DIR}/abstractness_metrics_exp1_exp2.png")
    print("Saved abstractness_metrics_exp1_exp2.png")


# ── Main ────────────────────────────────────────────────────

if __name__ == "__main__":
    apply_style()

    (exp1_trials, exp2_trials, exp1_utt, exp2_utt,
     exp1_pw, exp2_pw) = load_data()

    plot_specificity(exp1_pw, exp2_pw)
    plot_listener_accuracy(exp1_trials, exp2_trials)
    plot_abstractness(exp1_utt, exp2_utt)
