"""
Compute SBERT embeddings and similarity metrics for speaker utterances.

Loads speaker_utterances.csv, computes sentence embeddings using
paraphrase-MiniLM-L12-v2, and produces similarity CSVs.

Usage:
    uv run python analysis/compute_embeddings.py analysis/processed_data/ --output analysis/processed_data/
"""

import argparse
import re
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

# Basic English stopwords for term retention metric
STOPWORDS = frozenset(
    "i me my myself we our ours ourselves you your yours yourself yourselves "
    "he him his himself she her hers herself it its itself they them their "
    "theirs themselves what which who whom this that these those am is are was "
    "were be been being have has had having do does did doing a an the and but "
    "if or because as until while of at by for with about against between "
    "through during before after above below to from up down in out on off "
    "over under again further then once here there when where why how all both "
    "each few more most other some such no nor not only own same so than too "
    "very s t can will just don should now d ll m o re ve y ain aren couldn "
    "didn doesn hadn hasn haven isn ma mightn mustn needn shan shouldn wasn "
    "weren won wouldn like one also would could".split()
)


def compute_embeddings(utterances: pd.DataFrame, model: SentenceTransformer) -> np.ndarray:
    """Compute SBERT embeddings for all utterances."""
    texts = utterances["utterance"].fillna("").tolist()
    embeddings = model.encode(texts, show_progress_bar=True)
    return embeddings


def compute_adjacent_similarities(
    utterances: pd.DataFrame, embeddings: np.ndarray, model: SentenceTransformer
) -> pd.DataFrame:
    """
    For each speaker x tangram, compute cosine similarity between successive descriptions.
    """
    df = utterances.copy()
    df["embedding_idx"] = range(len(df))
    df = df.sort_values(["gameId", "playerId", "target", "blockNum"]).copy()

    # Shift to get previous embedding index within each (gameId, playerId, target) group
    df["prev_embedding_idx"] = df.groupby(
        ["gameId", "playerId", "target"]
    )["embedding_idx"].shift(1)

    def get_similarity(row):
        if pd.isna(row["prev_embedding_idx"]):
            return np.nan
        curr_idx = int(row["embedding_idx"])
        prev_idx = int(row["prev_embedding_idx"])
        return model.similarity(embeddings[curr_idx], embeddings[prev_idx]).item()

    df["simAdjacent"] = df.apply(get_similarity, axis=1)

    result = df[["gameId", "playerId", "originalGroup", "target",
                  "blockNum", "phase", "phaseNum", "repNum", "simAdjacent"]].copy()
    return result


def compute_pairwise_similarities(
    utterances: pd.DataFrame,
    embeddings: np.ndarray,
    model: SentenceTransformer,
    window_name: str,
) -> pd.DataFrame:
    """
    For each game and tangram in the given time window, compute pairwise cosine
    similarity between all speaker pairs.
    """
    df = utterances.copy()
    df["embedding_idx"] = range(len(df))

    rows = []
    for (game, target), group_data in df.groupby(["gameId", "target"]):
        speakers = group_data["playerId"].unique()

        if len(speakers) < 2:
            continue

        for s1, s2 in combinations(speakers, 2):
            s1_data = group_data[group_data["playerId"] == s1].iloc[-1]
            s2_data = group_data[group_data["playerId"] == s2].iloc[-1]

            emb1 = embeddings[int(s1_data["embedding_idx"])]
            emb2 = embeddings[int(s2_data["embedding_idx"])]
            sim = model.similarity(emb1, emb2).item()

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
                "similarity": sim,
                "participantPair": participant_pair,
                "window": window_name,
            })

    return pd.DataFrame(rows)


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


def compute_first_phrase_pairwise(
    utterances: pd.DataFrame,
    model: SentenceTransformer,
    window_name: str,
) -> pd.DataFrame:
    """
    Extract the first clause/phrase of each utterance (before the first comma
    or period), embed it, and compute pairwise similarity between speaker pairs.

    Returns a DataFrame with the same columns as compute_pairwise_similarities
    plus metric="first_phrase".
    """
    df = utterances.copy()
    # Extract first phrase: text before first comma or period
    df["first_phrase"] = df["utterance"].fillna("").apply(
        lambda u: re.split(r"[,.]", u)[0].strip()
    )
    # Replace empty first phrases with full utterance (single-word descriptions)
    mask = df["first_phrase"] == ""
    df.loc[mask, "first_phrase"] = df.loc[mask, "utterance"].fillna("")

    fp_embeddings = model.encode(df["first_phrase"].tolist(), show_progress_bar=False)
    df["embedding_idx"] = range(len(df))

    rows = []
    for (game, target), group_data in df.groupby(["gameId", "target"]):
        speakers = group_data["playerId"].unique()
        if len(speakers) < 2:
            continue
        for s1, s2 in combinations(speakers, 2):
            s1_data = group_data[group_data["playerId"] == s1].iloc[-1]
            s2_data = group_data[group_data["playerId"] == s2].iloc[-1]
            emb1 = fp_embeddings[int(s1_data["embedding_idx"])]
            emb2 = fp_embeddings[int(s2_data["embedding_idx"])]
            sim = model.similarity(emb1, emb2).item()

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
                "similarity": sim,
                "window": window_name,
                "metric": "first_phrase",
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
    df = utterances.copy()
    if df.empty:
        return pd.DataFrame()

    # Embed all utterances
    embeddings = model.encode(df["utterance"].fillna("").tolist(), show_progress_bar=False)
    df["embedding_idx"] = range(len(df))

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

                    if len(latest) < 2:
                        continue

                    players = latest.index.tolist()
                    for s1, s2 in combinations(players, 2):
                        s1_data = latest.loc[s1]
                        s2_data = latest.loc[s2]
                        emb1 = embeddings[int(s1_data["embedding_idx"])]
                        emb2 = embeddings[int(s2_data["embedding_idx"])]
                        sim = model.similarity(emb1, emb2).item()

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
                            "similarity": sim,
                            "blockNum": block,
                            "phaseNum": phase_num,
                        })

    return pd.DataFrame(rows)


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


# Concrete term stems derived from Boyce et al. 2024 (PNAS).
# Uses prefix matching: "squar" matches "square", "squares", etc.
# Four categories: geometric, body parts, positional, posture.
CONCRETE_STEMS_GEOMETRIC = [
    "squar", "triangle", "triangular", "diamond", "shape", "trapez",
    "angle", "degree", "parallel", "rhomb", "box", "cube", "line",
    "rectangle", "rectangular",
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

    Lexical uniqueness is computed separately via compute_lexical_uniqueness()
    because it requires cross-group comparison within each game × tangram.
    """
    from wordfreq import zipf_frequency

    def _compute_row(text):
        tokens = extract_content_word_tokens(text)
        if not tokens:
            return pd.Series({"concreteness": float("nan"), "mean_zipf_freq": float("nan")})

        concreteness = sum(1 for w in tokens if _is_concrete(w)) / len(tokens)
        mean_freq = sum(zipf_frequency(w, "en") for w in tokens) / len(tokens)

        return pd.Series({"concreteness": concreteness, "mean_zipf_freq": mean_freq})

    result = utterances.copy()
    props = result["utterance"].apply(_compute_row)
    result = pd.concat([result, props], axis=1)

    return result[
        [
            "gameId",
            "playerId",
            "originalGroup",
            "target",
            "blockNum",
            "phaseNum",
            "utterance",
            "concreteness",
            "mean_zipf_freq",
        ]
    ]


def compute_lexical_uniqueness(
    utterances: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute lexical uniqueness per utterance: proportion of content words
    NOT appearing in any other group's descriptions for the same tangram
    in the same game.

    Uses the same tokenization as compute_description_properties().
    """
    rows = []
    for (game_id, target), group_df in utterances.groupby(["gameId", "target"]):
        # Build word sets per group
        group_words: dict[str, set[str]] = {}
        for grp, grp_df in group_df.groupby("originalGroup"):
            all_words: set[str] = set()
            for text in grp_df["utterance"]:
                all_words.update(extract_content_word_tokens(text))
            group_words[grp] = all_words

        for _, row in group_df.iterrows():
            tokens = extract_content_word_tokens(row["utterance"])
            if not tokens:
                rows.append({**row, "uniqueness": float("nan")})
                continue

            other_words: set[str] = set()
            for grp, words in group_words.items():
                if grp != row["originalGroup"]:
                    other_words.update(words)

            uniqueness = sum(1 for w in tokens if w not in other_words) / len(tokens)
            rows.append({**row, "uniqueness": uniqueness})

    return pd.DataFrame(rows)


def compute_term_retention(
    utterances: pd.DataFrame,
    games: pd.DataFrame,
) -> pd.DataFrame:
    """
    For each speaker × tangram, check what proportion of content words from
    their final Phase 1 description appear in each Phase 2 description.
    """

    game_conditions = games.set_index("gameId")["condition"].to_dict()
    df = utterances.copy()

    rows = []
    for (game, player, target), group_data in df.groupby(["gameId", "playerId", "target"]):
        p1 = group_data[group_data["phaseNum"] == 1]
        p2 = group_data[group_data["phaseNum"] == 2]
        if p1.empty or p2.empty:
            continue

        # Final Phase 1 utterance
        final_p1 = p1.loc[p1["blockNum"].idxmax()]
        p1_terms = extract_content_words(str(final_p1["utterance"]))
        if not p1_terms:
            continue

        original_group = final_p1.get("originalGroup", "")

        for _, row in p2.iterrows():
            p2_terms = extract_content_words(str(row["utterance"]))
            retained = p1_terms & p2_terms
            retention = len(retained) / len(p1_terms)

            rows.append({
                "gameId": game,
                "playerId": player,
                "originalGroup": original_group,
                "target": target,
                "blockNum": int(row["blockNum"]),
                "phaseNum": 2,
                "retention": retention,
                "p1Terms": " ".join(sorted(p1_terms)),
                "condition": game_conditions.get(game, ""),
            })

    return pd.DataFrame(rows)


def compute_alternative_structures(
    utterances: pd.DataFrame,
    games: pd.DataFrame,
) -> pd.DataFrame:
    """
    Detect 'X or Y' and 'X / Y' alternative-structure patterns in Phase 2
    speaker utterances.  Filters false positives where words adjacent to 'or'
    are stopwords (e.g. 'sort or kind of').
    """
    game_conditions = games.set_index("gameId")["condition"].to_dict()
    p2 = utterances[utterances["phaseNum"] == 2].copy()
    if p2.empty:
        return pd.DataFrame()

    or_pattern = re.compile(r"\b(\w+)\s+or\s+(\w+)\b", re.IGNORECASE)
    slash_pattern = re.compile(r"\w+\s*/\s*\w+")

    rows = []
    for _, row in p2.iterrows():
        text = str(row.get("utterance", ""))
        # "or" patterns — filter when either adjacent word is a stopword
        or_matches = or_pattern.findall(text)
        n_or = sum(
            1 for w1, w2 in or_matches
            if w1.lower() not in STOPWORDS and w2.lower() not in STOPWORDS
        )
        n_slash = len(slash_pattern.findall(text))
        n_alt = n_or + n_slash

        rows.append({
            "gameId": row["gameId"],
            "playerId": row["playerId"],
            "originalGroup": row.get("originalGroup", ""),
            "target": row["target"],
            "blockNum": int(row["blockNum"]),
            "phaseNum": 2,
            "nOrPatterns": n_or,
            "nSlashPatterns": n_slash,
            "nAlternatives": n_alt,
            "hasAlternatives": int(n_alt > 0),
            "condition": game_conditions.get(row["gameId"], ""),
        })

    return pd.DataFrame(rows)


def compute_length_retention(
    utterances: pd.DataFrame,
    term_retention: pd.DataFrame,
    games: pd.DataFrame,
) -> pd.DataFrame:
    """
    Join Phase 2 speaker utterances to term retention on
    (gameId, playerId, target, blockNum).
    """
    if term_retention.empty:
        return pd.DataFrame()

    game_conditions = games.set_index("gameId")["condition"].to_dict()

    p2 = utterances[utterances["phaseNum"] == 2].copy()
    p2["blockNum"] = p2["blockNum"].astype(int)
    tr = term_retention.copy()
    tr["blockNum"] = tr["blockNum"].astype(int)

    merged = p2.merge(
        tr[["gameId", "playerId", "target", "blockNum", "retention"]],
        on=["gameId", "playerId", "target", "blockNum"],
        how="inner",
    )

    result = merged[["gameId", "playerId", "originalGroup", "target",
                      "blockNum", "uttLength", "retention"]].copy()
    result["condition"] = result["gameId"].map(game_conditions)
    return result


def compute_social_guess_retention(
    social_guesses: pd.DataFrame,
    trials: pd.DataFrame,
    term_retention: pd.DataFrame,
    games: pd.DataFrame,
) -> pd.DataFrame:
    """
    Join social guesses to speaker term retention via trials to test whether
    higher speaker retention predicts better social guessing accuracy.
    Only social_mixed games have social guess data.
    """
    if social_guesses.empty or term_retention.empty or trials.empty:
        return pd.DataFrame()

    game_conditions = games.set_index("gameId")["condition"].to_dict()

    sg = social_guesses.copy()
    tr = trials.copy()

    # Listener trials (the guesser is a listener) — get roundId, currentGroup
    listener_trials = tr[tr["role"] == "listener"][
        ["gameId", "playerId", "blockNum", "target", "roundId", "currentGroup"]
    ].copy()
    listener_trials["blockNum"] = listener_trials["blockNum"].astype(int)
    sg["blockNum"] = sg["blockNum"].astype(int)

    # Step 1: link guesser to their listener trial → roundId, currentGroup
    merged = sg.merge(
        listener_trials,
        on=["gameId", "playerId", "blockNum", "target"],
        how="inner",
    )

    # Step 2: find the speaker for that (gameId, roundId, currentGroup)
    speaker_trials = tr[tr["role"] == "speaker"][
        ["gameId", "roundId", "currentGroup", "playerId", "originalGroup"]
    ].rename(columns={"playerId": "speakerId", "originalGroup": "speakerOriginalGroup"})

    merged = merged.merge(
        speaker_trials,
        on=["gameId", "roundId", "currentGroup"],
        how="inner",
    )

    # Step 3: join speaker's term retention
    tr_data = term_retention.copy()
    tr_data["blockNum"] = tr_data["blockNum"].astype(int)
    speaker_ret = tr_data[["gameId", "playerId", "target", "blockNum", "retention"]].rename(
        columns={"playerId": "speakerId", "retention": "speakerRetention"}
    )
    merged = merged.merge(
        speaker_ret,
        on=["gameId", "speakerId", "target", "blockNum"],
        how="left",
    )

    # speakerWasSameGroup: was the speaker from the same original group as the guesser?
    merged["speakerWasSameGroup"] = (
        merged["originalGroup"] == merged["speakerOriginalGroup"]
    ).astype(int)

    result = merged[[
        "gameId", "playerId", "originalGroup", "blockNum", "target",
        "socialGuess", "socialGuessCorrect", "speakerId",
        "speakerOriginalGroup", "speakerRetention", "speakerWasSameGroup",
    ]].copy()
    result["condition"] = result["gameId"].map(game_conditions)
    return result


def _get_group_specific_terms(
    utterances: pd.DataFrame,
) -> dict[tuple, dict[str, tuple[set[str], set[str]]]]:
    """For each (gameId, target), return {groupLabel: (all_terms, specific_terms)}.

    Uses each group's final Phase 1 utterance to extract content words.
    Specific terms = group's words minus all other groups' words.
    """
    p1 = utterances[utterances["phaseNum"] == 1]
    result = {}

    for (game_id, target), tgt_p1 in p1.groupby(["gameId", "target"]):
        group_terms: dict[str, set[str]] = {}
        for grp, grp_data in tgt_p1.groupby("originalGroup"):
            final = grp_data.loc[grp_data["blockNum"].idxmax()]
            group_terms[grp] = extract_content_words(str(final["utterance"]))

        groups = list(group_terms.keys())
        if len(groups) < 2:
            continue

        group_info: dict[str, tuple[set[str], set[str]]] = {}
        for grp in groups:
            others = set()
            for other_grp in groups:
                if other_grp != grp:
                    others |= group_terms[other_grp]
            group_info[grp] = (group_terms[grp], group_terms[grp] - others)

        result[(game_id, target)] = group_info

    return result


def compute_cross_group_borrowing(
    utterances: pd.DataFrame,
    games: pd.DataFrame,
) -> pd.DataFrame:
    """
    For each Phase 2 utterance, measure what proportion of another group's
    unique Phase 1 terms the speaker has adopted (cross-group borrowing).
    """
    game_conditions = games.set_index("gameId")["condition"].to_dict()
    group_specific = _get_group_specific_terms(utterances)

    p2 = utterances[utterances["phaseNum"] == 2]
    rows = []
    for _, utt_row in p2.iterrows():
        game_id = utt_row["gameId"]
        target = utt_row["target"]
        key = (game_id, target)
        if key not in group_specific:
            continue

        speaker_group = utt_row.get("originalGroup", "")
        utt_words = extract_content_words(str(utt_row["utterance"]))

        for source_grp, (_, specific_terms) in group_specific[key].items():
            if source_grp == speaker_group:
                continue  # skip own group
            if not specific_terms:
                continue  # no unique terms to borrow

            borrowed = utt_words & specific_terms
            rows.append({
                "gameId": game_id,
                "playerId": utt_row["playerId"],
                "originalGroup": speaker_group,
                "target": target,
                "blockNum": int(utt_row["blockNum"]),
                "sourceGroup": source_grp,
                "nSourceTerms": len(specific_terms),
                "nBorrowed": len(borrowed),
                "borrowingRate": len(borrowed) / len(specific_terms),
                "condition": game_conditions.get(game_id, ""),
            })

    return pd.DataFrame(rows)


def compute_term_dominance(
    utterances: pd.DataFrame,
    games: pd.DataFrame,
) -> pd.DataFrame:
    """
    For each Phase 2 utterance, classify which group's specific Phase 1 terms
    dominate (highest overlap count).

    Returns per-utterance rows with dominantTermSource (group label, "tied",
    or "none"), counts per group, and a usesOwnGroupTerms flag.
    """
    game_conditions = games.set_index("gameId")["condition"].to_dict()
    group_specific = _get_group_specific_terms(utterances)

    p2 = utterances[utterances["phaseNum"] == 2]
    rows = []
    for _, utt_row in p2.iterrows():
        game_id = utt_row["gameId"]
        target = utt_row["target"]
        key = (game_id, target)
        if key not in group_specific:
            continue

        speaker_group = utt_row.get("originalGroup", "")
        utt_words = extract_content_words(str(utt_row["utterance"]))

        counts: dict[str, int] = {}
        for grp, (_, specific_terms) in group_specific[key].items():
            counts[grp] = len(utt_words & specific_terms)

        total = sum(counts.values())
        if total == 0:
            dominant = "none"
        else:
            max_count = max(counts.values())
            winners = [g for g, c in counts.items() if c == max_count]
            dominant = winners[0] if len(winners) == 1 else "tied"

        row = {
            "gameId": game_id,
            "target": target,
            "blockNum": int(utt_row["blockNum"]),
            "playerId": utt_row["playerId"],
            "originalGroup": speaker_group,
            "dominantTermSource": dominant,
            "totalSpecificTermsUsed": total,
            "usesOwnGroupTerms": int(counts.get(speaker_group, 0) > 0),
            "condition": game_conditions.get(game_id, ""),
        }
        # Per-group counts (A/B/C)
        for grp in sorted(group_specific[key].keys()):
            row[f"nTermsFrom{grp}"] = counts.get(grp, 0)

        rows.append(row)

    return pd.DataFrame(rows)


def compute_hedging_trajectory(
    alt_structures: pd.DataFrame,
    games: pd.DataFrame,
) -> pd.DataFrame:
    """
    Aggregate alternative_structures.csv to per-speaker-per-block level,
    tracking hedging rate and a cumulative hasEverHedged flag.
    """
    if alt_structures.empty:
        return pd.DataFrame()

    game_conditions = games.set_index("gameId")["condition"].to_dict()
    df = alt_structures.copy()

    rows = []
    for (game_id, player_id), player_data in df.groupby(["gameId", "playerId"]):
        original_group = player_data["originalGroup"].iloc[0]
        ever_hedged = False

        for block_num in sorted(player_data["blockNum"].unique()):
            block_data = player_data[player_data["blockNum"] == block_num]
            n_utt = len(block_data)
            n_with_alt = int(block_data["hasAlternatives"].sum())
            rate = n_with_alt / n_utt if n_utt > 0 else 0.0
            if n_with_alt > 0:
                ever_hedged = True

            rows.append({
                "gameId": game_id,
                "playerId": player_id,
                "originalGroup": original_group,
                "blockNum": int(block_num),
                "nUtterances": n_utt,
                "nWithAlternatives": n_with_alt,
                "hedgingRate": rate,
                "hasEverHedged": int(ever_hedged),
                "condition": game_conditions.get(game_id, ""),
            })

    return pd.DataFrame(rows)


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


def main():
    parser = argparse.ArgumentParser(
        description="Compute SBERT embeddings and similarity metrics"
    )
    parser.add_argument(
        "data_dir",
        help="Path to analysis/processed_data/ directory with preprocessed CSVs"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory (defaults to data_dir)"
    )
    parser.add_argument(
        "--utterances-file",
        default=None,
        help="Utterances CSV filename (default: speaker_utterances_filtered.csv if present, else speaker_utterances.csv)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output) if args.output else data_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Default to filtered utterances if available
    if args.utterances_file is None:
        if (data_dir / "speaker_utterances_filtered.csv").exists():
            args.utterances_file = "speaker_utterances_filtered.csv"
        else:
            args.utterances_file = "speaker_utterances.csv"

    print(f"Loading preprocessed data ({args.utterances_file})...")
    utterances = pd.read_csv(data_dir / args.utterances_file)
    games = pd.read_csv(data_dir / "games.csv")
    print(f"  {len(utterances)} utterances across {len(games)} games")

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

    # --- New metric 1: First-phrase pairwise similarity ---
    print("Computing first-phrase pairwise similarities...")
    fp_frames = []
    if not p1_utts.empty:
        fp_p1 = compute_first_phrase_pairwise(p1_utts, model, "phase1_final")
        fp_frames.append(fp_p1)
        print(f"  Phase 1 final: {len(fp_p1)} pairs")
    if not p2e_utts.empty:
        fp_p2e = compute_first_phrase_pairwise(p2e_utts, model, "phase2_early")
        fp_frames.append(fp_p2e)
        print(f"  Phase 2 early: {len(fp_p2e)} pairs")
    if not p2_utts.empty:
        fp_p2 = compute_first_phrase_pairwise(p2_utts, model, "phase2_final")
        fp_frames.append(fp_p2)
        print(f"  Phase 2 final: {len(fp_p2)} pairs")
    first_phrase_pw = pd.concat(fp_frames, ignore_index=True) if fp_frames else pd.DataFrame()
    first_phrase_pw.to_csv(output_dir / "first_phrase_similarities.csv", index=False)
    print(f"  Total first-phrase pairwise: {len(first_phrase_pw)} rows")

    # --- New metric 2: Block-by-block pairwise convergence ---
    print("Computing block-by-block pairwise similarities...")
    block_pw = compute_block_pairwise(utterances, model, games)
    block_pw.to_csv(output_dir / "block_pairwise_similarities.csv", index=False)
    print(f"  Block pairwise: {len(block_pw)} rows")

    # --- New metric 3: Phase 1 term retention ---
    print("Computing Phase 1 term retention...")
    term_retention = compute_term_retention(utterances, games)
    term_retention.to_csv(output_dir / "term_retention.csv", index=False)
    print(f"  Term retention: {len(term_retention)} rows")

    # Load additional data for follow-up analyses
    trials = pd.read_csv(data_dir / "trials.csv")
    social_path = data_dir / "social_guesses.csv"
    social_guesses = pd.read_csv(social_path) if social_path.exists() else pd.DataFrame()

    # --- Follow-up analysis 1: Alternative structures ---
    print("Computing alternative structures...")
    alt_structures = compute_alternative_structures(utterances, games)
    alt_structures.to_csv(output_dir / "alternative_structures.csv", index=False)
    n_with = alt_structures["hasAlternatives"].sum() if not alt_structures.empty else 0
    print(f"  Alternative structures: {len(alt_structures)} rows, {n_with} with alternatives")

    # --- Follow-up analysis 2: Length × retention ---
    print("Computing length × retention...")
    length_retention = compute_length_retention(utterances, term_retention, games)
    length_retention.to_csv(output_dir / "length_retention.csv", index=False)
    print(f"  Length-retention: {len(length_retention)} rows")

    # --- Follow-up analysis 3: Social guess × retention ---
    if not social_guesses.empty:
        print("Computing social guess × retention...")
        social_guess_retention = compute_social_guess_retention(
            social_guesses, trials, term_retention, games
        )
        social_guess_retention.to_csv(output_dir / "social_guess_retention.csv", index=False)
        print(f"  Social guess-retention: {len(social_guess_retention)} rows")
    else:
        print("No social guesses data — skipping social guess × retention")

    # --- Follow-up analysis 4: Cross-group borrowing ---
    print("Computing cross-group borrowing...")
    borrowing = compute_cross_group_borrowing(utterances, games)
    borrowing.to_csv(output_dir / "cross_group_borrowing.csv", index=False)
    print(f"  Cross-group borrowing: {len(borrowing)} rows")

    # --- Follow-up analysis 5: Term dominance ---
    print("Computing term dominance...")
    term_dominance = compute_term_dominance(utterances, games)
    term_dominance.to_csv(output_dir / "term_dominance.csv", index=False)
    print(f"  Term dominance: {len(term_dominance)} rows")

    # --- Follow-up analysis 7: Hedging trajectory ---
    print("Computing hedging trajectory...")
    hedging_trajectory = compute_hedging_trajectory(alt_structures, games)
    hedging_trajectory.to_csv(output_dir / "hedging_trajectory.csv", index=False)
    print(f"  Hedging trajectory: {len(hedging_trajectory)} rows")

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

    print("Computing UMAP projections...")
    try:
        from umap import UMAP
        reducer = UMAP(n_components=2, random_state=42, n_neighbors=15, min_dist=0.1)
        umap_coords = reducer.fit_transform(embeddings)
        utterances["umap_x"] = umap_coords[:, 0]
        utterances["umap_y"] = umap_coords[:, 1]
        utterances.to_csv(output_dir / "umap_projections.csv", index=False)
        print(f"  UMAP projections saved: {len(utterances)} points")
    except ImportError:
        print("  umap-learn not installed; skipping UMAP projections")

    print(f"\nAll outputs written to {output_dir}")


if __name__ == "__main__":
    main()
