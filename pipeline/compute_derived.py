"""
Compute derived metrics from speaker utterances.

Produces the SBERT embeddings; the adjacent, final-window pairwise, block-by-
block and phase-change similarity tables, with the pairwise and block tables
also scored by content-word Jaccard overlap in the same row order; and the
per-description properties (concreteness, word frequency, lexical uniqueness).

Usage:
    uv run python -m pipeline.compute_derived --dataset full
"""

import argparse
import re
import sys
from itertools import combinations
from pathlib import Path

import nltk
import numpy as np
import pandas as pd

# The analysis columns the processed tables carry (preprocessing.ANALYSIS_COLUMNS),
# carried through to the per-description derived tables when present so that
# no consumer joins the condition or re-indexes blocks.
ANALYSIS_COLUMNS = ["condition", "block", "gameBlock"]
from sentence_transformers import SentenceTransformer

from pipeline.dataset_paths import (
    FILTERED_UTTERANCES_FILE,
    add_dataset_argument,
    dataset_dirs,
    filtered_utterances_status,
    stale_filtered_message,
)

# NLTK English stopwords for content-word extraction
nltk.download("stopwords", quiet=True)
from nltk.corpus import stopwords  # noqa: E402

STOPWORDS = frozenset(stopwords.words("english"))


def compute_embeddings(utterances: pd.DataFrame, model: SentenceTransformer) -> np.ndarray:
    """Compute SBERT embeddings for all utterances."""
    texts = utterances["utterance"].fillna("").tolist()
    embeddings = model.encode(texts, show_progress_bar=True)
    return embeddings


def compute_adjacent_similarities(
    utterances: pd.DataFrame, embeddings: np.ndarray, model: SentenceTransformer
) -> pd.DataFrame:
    """
    For each ORIGINAL group x tangram, compute cosine similarity between
    successive descriptions across blocks, regardless of which member spoke:
    `sim_adjacent` in the preregistration, "the cosine similarity between each
    description and the one that most recently preceded it for the same
    original group and the same tangram". In Phase 1 (and refer_separated)
    this is cross-speaker convention convergence within the conversing group.
    In Phase 2 of the mixed conditions original-group members no longer
    converse with one another, so there it measures retention of the original
    group's convention, not adjacency within a conversation.

    The sequence runs across the phase boundary, as the preregistration
    defines it: a group's first Phase 2 description of a tangram is compared
    with its last Phase 1 description, which is exactly the retention the
    Phase 2 measure is for. Only the first description of each group and
    tangram has no predecessor.

    Ordering within a group is by phase, then block, then trial, then player
    id, so ties (two original-group members describing the same tangram in the
    same block, possible after a speaker reassignment) are resolved
    deterministically.
    """
    df = utterances.copy()
    df["embedding_idx"] = range(len(df))
    order_cols = [c for c in ["gameId", "originalGroup", "target", "phaseNum", "blockNum", "trialNum", "playerId"] if c in df.columns]
    df = df.sort_values(order_cols, kind="stable").copy()

    # The previous description's embedding within each (game, group, target),
    # across both phases
    df["prev_embedding_idx"] = df.groupby(
        ["gameId", "originalGroup", "target"]
    )["embedding_idx"].shift(1)

    def get_similarity(row):
        if pd.isna(row["prev_embedding_idx"]):
            return np.nan
        curr_idx = int(row["embedding_idx"])
        prev_idx = int(row["prev_embedding_idx"])
        return model.similarity(embeddings[curr_idx], embeddings[prev_idx]).item()

    df["simAdjacent"] = df.apply(get_similarity, axis=1)

    columns = ["gameId", "playerId", "originalGroup", "target",
               "blockNum", "phase", "phaseNum", "repNum", "simAdjacent"]
    columns += [c for c in ANALYSIS_COLUMNS if c in df.columns]
    return df[columns].copy()


def _word_count(row) -> int:
    """Word count of an utterance row: uttLength when present, else counted."""
    n = row.get("uttLength") if hasattr(row, "get") else None
    if n is not None and not pd.isna(n):
        return int(n)
    return len(str(row.get("utterance", "") or "").split())


# ── Pair construction shared by the SBERT and Jaccard similarity tables ─────
#
# The preregistration's content-word overlap check repeats the SBERT analyses
# with Jaccard similarity on the *same* pairs, so the two tables must have the
# same rows in the same order and differ only in `similarity`. Building the
# pairs once, with the similarity function passed in, is what guarantees that;
# the two `compute_*` entry points below are thin wrappers.
#
# A similarity function takes the two chosen utterance rows (pandas Series
# with the utterance's columns plus `_row`, its position in the input frame)
# and returns a float, or NaN when the measure is undefined for that pair.


def embedding_similarity(embeddings: np.ndarray, model) -> callable:
    """Cosine similarity of two rows' SBERT embeddings (indexed by `_row`)."""

    def similarity(row1, row2) -> float:
        emb1 = embeddings[int(row1["_row"])]
        emb2 = embeddings[int(row2["_row"])]
        return model.similarity(emb1, emb2).item()

    return similarity


def content_word_set(text) -> set[str]:
    """The distinct content words of a description, as the preregistration
    defines them for H3c and the overlap check: lowercased alphabetic
    sequences, NLTK English stopwords removed, one-character words dropped,
    no stemming, repeated tokens counted once."""
    if not isinstance(text, str):
        return set()
    return extract_content_words(text)


def jaccard_similarity(row1, row2) -> float:
    """Jaccard overlap of two descriptions' content-word sets.

    |A ∩ B| / |A ∪ B|. When either description has no content words the
    preregistration omits the pair from the overlap check; the pair keeps its
    row here (so the table lines up with the SBERT one) with NaN similarity,
    and the analysis drops those rows and reports the coverage.
    """
    words1 = content_word_set(row1.get("utterance"))
    words2 = content_word_set(row2.get("utterance"))
    if not words1 or not words2:
        return float("nan")
    return len(words1 & words2) / len(words1 | words2)


def build_pairwise_table(
    utterances: pd.DataFrame, window_name: str, similarity
) -> pd.DataFrame:
    """For each game and tangram in one time window, every pair of speakers'
    most recent descriptions, scored with `similarity`."""
    df = utterances.copy()
    df["_row"] = range(len(df))

    rows = []
    for (game, target), group_data in df.groupby(["gameId", "target"]):
        # Each speaker's most recent description in the window. Sort by block
        # explicitly: the filtered utterance file is not in block order, so
        # taking the last row by file position picked an earlier block.
        group_data = group_data.sort_values("blockNum", kind="stable")
        speakers = group_data["playerId"].unique()

        if len(speakers) < 2:
            continue

        for s1, s2 in combinations(speakers, 2):
            s1_data = group_data[group_data["playerId"] == s1].iloc[-1]
            s2_data = group_data[group_data["playerId"] == s2].iloc[-1]

            group1 = s1_data.get("originalGroup", "")
            group2 = s2_data.get("originalGroup", "")
            same_group = 1 if group1 == group2 else 0

            pair = tuple(sorted([s1, s2]))
            participant_pair = f"{pair[0]}_{pair[1]}"

            rows.append({
                "gameId": game,
                "target": target,
                "speaker1": s1,
                "speaker2": s2,
                "group1": group1,
                "group2": group2,
                "sameGroup": same_group,
                "similarity": similarity(s1_data, s2_data),
                "participantPair": participant_pair,
                "window": window_name,
                # Word counts of the two descriptions, for the preregistered
                # robustness check that adds description length to the
                # group-specificity models
                "length1": _word_count(s1_data),
                "length2": _word_count(s2_data),
            })

    return pd.DataFrame(rows)


def compute_pairwise_similarities(
    utterances: pd.DataFrame,
    embeddings: np.ndarray,
    model: SentenceTransformer,
    window_name: str,
) -> pd.DataFrame:
    """
    For each game and tangram in the given time window, compute pairwise cosine
    similarity between all speaker pairs. `embeddings` is aligned with the rows
    of `utterances`.
    """
    return build_pairwise_table(
        utterances, window_name, embedding_similarity(embeddings, model)
    )


def compute_pairwise_similarities_jaccard(
    utterances: pd.DataFrame, window_name: str
) -> pd.DataFrame:
    """The same pairs as `compute_pairwise_similarities`, scored by Jaccard
    overlap of content words (the preregistered robustness check)."""
    return build_pairwise_table(utterances, window_name, jaccard_similarity)


def compute_phase_change_similarities(
    utterances: pd.DataFrame,
    embeddings: np.ndarray,
    model: SentenceTransformer,
    games: pd.DataFrame,
) -> pd.DataFrame:
    """
    For each participant x tangram, compute cosine similarity between their
    final Phase 1 description and (a) final Phase 2 description, and
    (b) first Phase 2 description.
    """
    df = utterances.copy()
    df["embedding_idx"] = range(len(df))

    # Get phase1Blocks per game to determine final block of each phase
    game_blocks = games.set_index("gameId")["phase1Blocks"].to_dict()

    rows = []
    for (game, player, target), group_data in df.groupby(
        ["gameId", "playerId", "target"]
    ):
        p1_blocks = game_blocks.get(game, 6)

        phase1_data = group_data[group_data["phaseNum"] == 1]
        phase2_data = group_data[group_data["phaseNum"] == 2]

        if phase1_data.empty or phase2_data.empty:
            continue

        # Final description in Phase 1, first and final in Phase 2
        final_p1 = phase1_data.loc[phase1_data["blockNum"].idxmax()]
        first_p2 = phase2_data.loc[phase2_data["blockNum"].idxmin()]
        final_p2 = phase2_data.loc[phase2_data["blockNum"].idxmax()]

        emb_p1 = embeddings[int(final_p1["embedding_idx"])]
        emb_p2_first = embeddings[int(first_p2["embedding_idx"])]
        emb_p2_final = embeddings[int(final_p2["embedding_idx"])]
        sim_final = model.similarity(emb_p1, emb_p2_final).item()
        sim_early = model.similarity(emb_p1, emb_p2_first).item()

        # Get condition from games df
        condition = games.loc[games["gameId"] == game, "condition"].values
        condition = condition[0] if len(condition) > 0 else None

        rows.append({
            "gameId": game,
            "playerId": player,
            "originalGroup": final_p1.get("originalGroup", ""),
            "target": target,
            "simPhase1Phase2": sim_final,
            "simP1FinalP2Early": sim_early,
            "condition": condition,
        })

    return pd.DataFrame(rows)


def build_block_pairwise_table(utterances: pd.DataFrame, similarity) -> pd.DataFrame:
    """For each block and tangram (both phases), every pair of speakers' most
    recent descriptions up to that block within the phase, scored with
    `similarity`. Shared by the SBERT and Jaccard block tables so that they
    have the same rows in the same order.

    `allGroupsPaired` marks the cells where every original group has at least
    two participants with a description of this tangram, which is the
    preregistered start rule for group specificity: only there does every
    group contribute a within-group pair, so only there is within-minus-between
    a comparison between groups rather than between whichever groups happened
    to be describable. It is 0 for the first block of each phase, where each
    group has exactly one description and the cell holds between-group pairs
    alone, and for later cells where a removed or reassigned speaker has left
    a group with one describer of that tangram. A cell also needs at least two
    original groups with a description, or there is no between-group pair to
    compare against: a group that has described a tangram twice before any
    other group has is not eligible. Consumers that need the contrast filter on the flag
    (`specificity_eligible()` in analysis/R/prepare.R); the descriptive
    within-vs-between panel plots every pair."""
    df = utterances.copy()
    if df.empty:
        return pd.DataFrame()
    df["_row"] = range(len(df))

    rows = []
    for game, game_data in df.groupby("gameId"):
        targets = game_data["target"].unique()

        for phase_num in sorted(game_data["phaseNum"].unique()):
            phase_data = game_data[game_data["phaseNum"] == phase_num]
            blocks = sorted(phase_data["blockNum"].unique())

            for target in targets:
                target_data = phase_data[phase_data["target"] == target]
                if target_data.empty:
                    continue

                for block in blocks:
                    # For each player, find their most recent description of
                    # this tangram up to and including the current block
                    up_to_block = target_data[target_data["blockNum"] <= block]
                    latest = up_to_block.sort_values("blockNum").groupby("playerId").last()

                    # A pair needs two descriptions; below that there is
                    # nothing to score.
                    if len(latest) < 2:
                        continue
                    # The preregistered start rule for group specificity,
                    # carried as a flag rather than applied here, so the
                    # descriptive panel can still show the first block of each
                    # phase (between-group pairs only). See the docstring.
                    all_groups_paired = True
                    if "originalGroup" in latest.columns:
                        per_group = latest.groupby("originalGroup").size()
                        all_groups_paired = len(per_group) >= 2 and not bool((per_group < 2).any())

                    players = latest.index.tolist()
                    for s1, s2 in combinations(players, 2):
                        s1_data = latest.loc[s1]
                        s2_data = latest.loc[s2]

                        group1 = s1_data.get("originalGroup", "")
                        group2 = s2_data.get("originalGroup", "")

                        rows.append({
                            "gameId": game,
                            "target": target,
                            "speaker1": s1,
                            "speaker2": s2,
                            "group1": group1,
                            "group2": group2,
                            "sameGroup": 1 if group1 == group2 else 0,
                            "similarity": similarity(s1_data, s2_data),
                            "blockNum": block,
                            "phaseNum": phase_num,
                            "allGroupsPaired": int(all_groups_paired),
                        })

    return pd.DataFrame(rows)


def compute_block_pairwise(
    utterances: pd.DataFrame,
    model: SentenceTransformer,
    games: pd.DataFrame,
) -> pd.DataFrame:
    """
    For each block and tangram (both phases), compute pairwise cosine
    similarity between all speakers using their most recent description
    (from that block or any earlier block within the same phase). This
    produces both within-group and between-group pairs, enabling
    group-specificity trajectory analysis.
    """
    if utterances.empty:
        return pd.DataFrame()
    embeddings = model.encode(
        utterances["utterance"].fillna("").tolist(), show_progress_bar=False
    )
    return build_block_pairwise_table(utterances, embedding_similarity(embeddings, model))


def compute_block_pairwise_jaccard(utterances: pd.DataFrame) -> pd.DataFrame:
    """The same block-by-block pairs as `compute_block_pairwise`, scored by
    Jaccard overlap of content words."""
    return build_block_pairwise_table(utterances, jaccard_similarity)


def extract_content_words(text: str) -> set[str]:
    """Extract non-stopword content words (lowercase, len>1) from text."""
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def extract_content_word_tokens(text: str) -> list[str]:
    """Extract content words as a list (preserving duplicates), unlike the set version."""
    if not isinstance(text, str):
        return []
    words = re.findall(r"[a-z]+", text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


# Concrete term stems from Boyce et al. 2024 (PNAS), Table S2.
# Exact keyword list; only adaptation is prefix matching (e.g., "squar"
# matches "square", "squares"), which is how the preregistration states the
# measure. Prefix matching also admits words that merely begin with a stem
# ("butterfly" and "button" for "butt", "handle" for "hand", "earlier" for
# "ear"). In the full sample about 3% of the tokens counted as concrete are
# neither a stem nor an inflection of one, most of them compounds of a
# concrete word ("sideways", "backwards", "headless"), so the preregistered
# rule is kept and the over-inclusion is reported beside the measure. Four
# categories: geometric, body parts, positional, posture.
CONCRETE_STEMS_GEOMETRIC = [
    "squar", "triangle", "triangular", "diamond", "shape", "trapez",
    "angle", "degree", "parallel", "rhomb", "box", "cube", "line",
    "white", "black",
]
CONCRETE_STEMS_BODY = [
    "face", "head", "back", "shoulder", "arm", "leg", "foot", "feet",
    "body", "knee", "toe", "hand", "butt", "heel", "ear", "nose",
    "neck", "chest", "hair",
]
CONCRETE_STEMS_POSITION = [
    "right", "left", "above", "below", "under", "over", "top",
    "bottom", "behind", "side", "beneath",
]
CONCRETE_STEMS_POSTURE = [
    "kick", "crouch", "squat", "kneel", "knelt", "stood", "stand",
    "sit", "sat", "lying", "walk", "facing", "fall", "lean", "seat",
    "laying", "looking",
]
ALL_CONCRETE_STEMS = (
    CONCRETE_STEMS_GEOMETRIC + CONCRETE_STEMS_BODY
    + CONCRETE_STEMS_POSITION + CONCRETE_STEMS_POSTURE
)


def _is_concrete(word: str) -> bool:
    """Check if a word matches any concrete term stem (prefix match)."""
    return any(word.startswith(stem) for stem in ALL_CONCRETE_STEMS)


def compute_description_properties(
    utterances: pd.DataFrame,
    games: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute H3c description properties per utterance using consistent tokenization.

    Measures:
    - concreteness: proportion of content words matching concrete term stems
      (derived from Boyce et al. 2024)
    - mean_zipf_freq: mean Zipf frequency of content words (via wordfreq package)

    The counts behind the concreteness proportion are kept beside it:
    `n_content_words` and `n_concrete`. The preregistered model fits the two
    proportion measures as binomial outcomes, `cbind(k, n - k)`, rather than
    as Gaussian proportions, because the denominator varies from one word to
    several dozen and is itself expected to differ by condition. A ratio alone
    cannot be fit that way, so the numerator and denominator have to survive
    into the CSV. `mean_zipf_freq` stays a mean of a continuous quantity and
    needs no such counts.

    Lexical uniqueness is computed separately via compute_lexical_uniqueness()
    because it requires cross-group comparison within each game × tangram.
    """
    from wordfreq import zipf_frequency

    def _compute_row(text):
        tokens = extract_content_word_tokens(text)
        if not tokens:
            return pd.Series(
                {
                    "n_content_words": 0,
                    "n_concrete": 0,
                    "concreteness": float("nan"),
                    "mean_zipf_freq": float("nan"),
                }
            )

        n_concrete = sum(1 for w in tokens if _is_concrete(w))
        mean_freq = sum(zipf_frequency(w, "en") for w in tokens) / len(tokens)

        return pd.Series(
            {
                "n_content_words": len(tokens),
                "n_concrete": n_concrete,
                "concreteness": n_concrete / len(tokens),
                "mean_zipf_freq": mean_freq,
            }
        )

    result = utterances.copy()
    props = result["utterance"].apply(_compute_row)
    result = pd.concat([result, props], axis=1)
    for col in ("n_content_words", "n_concrete"):
        result[col] = result[col].astype(int)

    return result[
        [
            "gameId",
            "playerId",
            "originalGroup",
            "target",
            "blockNum",
            "phaseNum",
            "utterance",
            "n_content_words",
            "n_concrete",
            "concreteness",
            "mean_zipf_freq",
        ]
        + [c for c in ANALYSIS_COLUMNS if c in result.columns]
    ]


def compute_lexical_uniqueness(
    utterances: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute lexical uniqueness per utterance: proportion of content words
    NOT appearing in any other group's descriptions for the same tangram
    across all games, within the same phase.

    The reference vocabulary is restricted to the utterance's own phase so
    that labels other groups borrow in Phase 2 (mixed conditions) cannot
    retroactively make a Phase 1 word non-unique: Phase 1 utterances are
    compared against other groups' Phase 1 descriptions, Phase 2 against
    Phase 2.

    Uses the same tokenization as compute_description_properties(), and like
    it keeps the counts behind the proportion (`n_content_words`,
    `n_unique_words`) so the preregistered binomial model can be fit on
    `cbind(k, n - k)` rather than on the ratio.
    """
    # Build word sets per (gameId, originalGroup, target, phaseNum) across all games
    group_words: dict[tuple[str, str, str, int], set[str]] = {}
    for (game_id, grp, target, phase), grp_df in utterances.groupby(
        ["gameId", "originalGroup", "target", "phaseNum"]
    ):
        all_words: set[str] = set()
        for text in grp_df["utterance"]:
            all_words.update(extract_content_word_tokens(text))
        group_words[(game_id, grp, target, int(phase))] = all_words

    rows = []
    for _, row in utterances.iterrows():
        tokens = extract_content_word_tokens(row["utterance"])
        if not tokens:
            rows.append(
                {
                    **row,
                    "n_content_words": 0,
                    "n_unique_words": 0,
                    "uniqueness": float("nan"),
                }
            )
            continue

        # Words from all other groups (across all games) for the same tangram
        # in the same phase
        other_words: set[str] = set()
        for (g_id, grp, tgt, phase), words in group_words.items():
            if (
                tgt == row["target"]
                and phase == int(row["phaseNum"])
                and not (g_id == row["gameId"] and grp == row["originalGroup"])
            ):
                other_words.update(words)

        n_unique = sum(1 for w in tokens if w not in other_words)
        rows.append(
            {
                **row,
                "n_content_words": len(tokens),
                "n_unique_words": n_unique,
                "uniqueness": n_unique / len(tokens),
            }
        )

    out = pd.DataFrame(rows)
    for col in ("n_content_words", "n_unique_words"):
        if col in out.columns:
            out[col] = out[col].astype(int)
    return out


def get_window_utterances(
    utterances: pd.DataFrame,
    games: pd.DataFrame,
    window: str,
) -> pd.DataFrame:
    """
    Filter utterances to a specific time window.
    - "phase1_final": last 3 blocks of Phase 1
    - "phase2_final": last 3 blocks of Phase 2
    """
    game_blocks = games.set_index("gameId")[["phase1Blocks", "phase2Blocks"]].to_dict("index")

    rows = []
    for game_id, game_data in utterances.groupby("gameId"):
        blocks_info = game_blocks.get(game_id, {"phase1Blocks": 6, "phase2Blocks": 6})
        p1_blocks = int(blocks_info["phase1Blocks"])
        p2_blocks = int(blocks_info["phase2Blocks"])

        if window == "phase1_final":
            # Last 3 blocks of Phase 1
            # blockNum is 0-indexed within phase: 0 to p1_blocks-1
            min_block = max(0, p1_blocks - 3)
            filtered = game_data[
                (game_data["phaseNum"] == 1) &
                (game_data["blockNum"] >= min_block)
            ]
        elif window == "phase2_early":
            # First 3 blocks of Phase 2
            filtered = game_data[
                (game_data["phaseNum"] == 2) &
                (game_data["blockNum"] < 3)
            ]
        elif window == "phase2_final":
            # Last 3 blocks of Phase 2
            # blockNum is 0-indexed within phase: 0 to p2_blocks-1
            min_block = max(0, p2_blocks - 3)
            filtered = game_data[
                (game_data["phaseNum"] == 2) &
                (game_data["blockNum"] >= min_block)
            ]
        else:
            raise ValueError(f"Unknown window: {window}")

        rows.append(filtered)

    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def drop_empty_utterances(utterances: pd.DataFrame) -> pd.DataFrame:
    """Remove utterance rows with no text.

    A speaker whose messages were all classified as non-referential has no
    description on that trial; the preregistration excludes such trials from
    the utterance-based analyses, as with trials in which the speaker sent
    nothing. The filter step emits no such rows; this guards hand-built inputs.
    """
    text = utterances["utterance"].fillna("").astype(str).str.strip()
    empty = text == ""
    if empty.any():
        print(f"  Dropping {int(empty.sum())} utterances with no referential text")
    return utterances.loc[~empty].copy()


def main():
    parser = argparse.ArgumentParser(
        description="Compute SBERT embeddings and similarity metrics"
    )
    add_dataset_argument(parser)
    parser.add_argument(
        "tables_dir",
        nargs="?",
        default=None,
        help="Directory of the processed tables (default: the dataset's tables/)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory (default: the dataset's derived/)",
    )
    parser.add_argument(
        "--utterances-file",
        default=None,
        help="Utterances CSV filename (default: speaker_utterances_filtered.csv if present, else speaker_utterances.csv)",
    )
    args = parser.parse_args()

    dirs = dataset_dirs(args.dataset)
    tables_dir = Path(args.tables_dir) if args.tables_dir else dirs.tables
    output_dir = Path(args.output) if args.output else dirs.derived

    # Default to the filtered utterances when they exist and were built from the
    # current messages.csv. A filtered file whose sidecar is missing or names a
    # different messages.csv is refused, even when asked for by name: using it
    # would silently analyze descriptions from a previous version of the data.
    status, detail = filtered_utterances_status(tables_dir)
    if args.utterances_file is None:
        args.utterances_file = (
            FILTERED_UTTERANCES_FILE if status != "absent" else "speaker_utterances.csv"
        )
    if args.utterances_file == FILTERED_UTTERANCES_FILE and status in ("stale", "unverified"):
        print(f"Error: {stale_filtered_message(status, detail)}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Loading preprocessed data ({args.utterances_file})...")
    utterances = pd.read_csv(tables_dir / args.utterances_file)
    games = pd.read_csv(tables_dir / "games.csv")
    print(f"  {len(utterances)} utterances across {len(games)} games")
    utterances = drop_empty_utterances(utterances)

    print("Loading SBERT model (paraphrase-MiniLM-L12-v2)...")
    model = SentenceTransformer("sentence-transformers/paraphrase-MiniLM-L12-v2")

    print("Computing embeddings...")
    embeddings = compute_embeddings(utterances, model)
    np.save(output_dir / "embeddings.npy", embeddings)
    print(f"  Saved embeddings: shape {embeddings.shape}")

    print("Computing adjacent similarities...")
    adjacent = compute_adjacent_similarities(utterances, embeddings, model)
    adjacent.to_csv(output_dir / "adjacent_similarities.csv", index=False)
    print(f"  {adjacent['simAdjacent'].notna().sum()} adjacent similarity values")

    print("Computing pairwise similarities for Phase 1 final window...")
    p1_utts = get_window_utterances(utterances, games, "phase1_final")
    if not p1_utts.empty:
        # Re-compute embeddings for just this window subset
        p1_embeddings = model.encode(p1_utts["utterance"].fillna("").tolist())
        pairwise_p1 = compute_pairwise_similarities(
            p1_utts, p1_embeddings, model, "phase1_final"
        )
        print(f"  Phase 1 final: {len(pairwise_p1)} pairs")
    else:
        pairwise_p1 = pd.DataFrame()
        print("  Phase 1 final: no data")

    print("Computing pairwise similarities for Phase 2 early window...")
    p2e_utts = get_window_utterances(utterances, games, "phase2_early")
    if not p2e_utts.empty:
        p2e_embeddings = model.encode(p2e_utts["utterance"].fillna("").tolist())
        pairwise_p2e = compute_pairwise_similarities(
            p2e_utts, p2e_embeddings, model, "phase2_early"
        )
        print(f"  Phase 2 early: {len(pairwise_p2e)} pairs")
    else:
        pairwise_p2e = pd.DataFrame()
        print("  Phase 2 early: no data")

    print("Computing pairwise similarities for Phase 2 final window...")
    p2_utts = get_window_utterances(utterances, games, "phase2_final")
    if not p2_utts.empty:
        p2_embeddings = model.encode(p2_utts["utterance"].fillna("").tolist())
        pairwise_p2 = compute_pairwise_similarities(
            p2_utts, p2_embeddings, model, "phase2_final"
        )
        print(f"  Phase 2 final: {len(pairwise_p2)} pairs")
    else:
        pairwise_p2 = pd.DataFrame()
        print("  Phase 2 final: no data")

    pairwise = pd.concat([pairwise_p1, pairwise_p2e, pairwise_p2], ignore_index=True)
    pairwise.to_csv(output_dir / "pairwise_similarities.csv", index=False)
    print(f"  Total pairwise: {len(pairwise)} rows")

    # --- Preregistered robustness check: the same pairs by content-word overlap ---
    # Built from the same windows in the same order as the SBERT table, so the
    # two files line up row for row; only `similarity` differs. Pairs where
    # either description has no content words carry NaN (the analysis omits
    # them and reports the coverage).
    print("Computing Jaccard (content-word overlap) pairwise similarities...")
    pairwise_jaccard = pd.concat(
        [
            compute_pairwise_similarities_jaccard(utts, window)
            for utts, window in (
                (p1_utts, "phase1_final"),
                (p2e_utts, "phase2_early"),
                (p2_utts, "phase2_final"),
            )
            if not utts.empty
        ],
        ignore_index=True,
    ) if not pairwise.empty else pd.DataFrame(columns=pairwise.columns)
    assert len(pairwise_jaccard) == len(pairwise), "Jaccard and SBERT pair tables differ in rows"
    pairwise_jaccard.to_csv(output_dir / "pairwise_similarities_jaccard.csv", index=False)
    print(
        f"  Total pairwise (Jaccard): {len(pairwise_jaccard)} rows, "
        f"{int(pairwise_jaccard['similarity'].isna().sum()) if not pairwise_jaccard.empty else 0} "
        "without content words on one side"
    )

    # --- Block-by-block pairwise convergence ---
    print("Computing block-by-block pairwise similarities...")
    block_pw = compute_block_pairwise(utterances, model, games)
    block_pw.to_csv(output_dir / "block_pairwise_similarities.csv", index=False)
    print(f"  Block pairwise: {len(block_pw)} rows")

    print("Computing block-by-block Jaccard (content-word overlap) similarities...")
    block_pw_jaccard = compute_block_pairwise_jaccard(utterances)
    assert len(block_pw_jaccard) == len(block_pw), "Jaccard and SBERT block tables differ in rows"
    block_pw_jaccard.to_csv(output_dir / "block_pairwise_similarities_jaccard.csv", index=False)
    print(f"  Block pairwise (Jaccard): {len(block_pw_jaccard)} rows")

    print("Computing phase change similarities...")
    phase_change = compute_phase_change_similarities(
        utterances, embeddings, model, games
    )
    phase_change.to_csv(output_dir / "phase_change_similarities.csv", index=False)
    print(f"  {len(phase_change)} phase change similarity values")

    # --- H3c description properties ---
    print("Computing description properties (abstractness, word frequency)...")
    desc_props = compute_description_properties(utterances, games)
    desc_props.to_csv(output_dir / "description_properties.csv", index=False)
    print(f"  Description properties: {len(desc_props)} rows")

    print("Computing lexical uniqueness...")
    lex_unique = compute_lexical_uniqueness(utterances)
    lex_unique.to_csv(output_dir / "lexical_uniqueness.csv", index=False)
    print(f"  Lexical uniqueness: {len(lex_unique)} rows")

    print(f"\nAll outputs written to {output_dir}")


if __name__ == "__main__":
    main()
