"""
Compute SBERT embeddings and similarity metrics for speaker utterances.

Loads speaker_utterances.csv, computes sentence embeddings using
paraphrase-MiniLM-L12-v2, and produces similarity CSVs.

Usage:
    uv run python analysis/compute_embeddings.py analysis/data/ --output analysis/data/
"""

import argparse
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer


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
            s1_data = group_data[group_data["playerId"] == s1].iloc[0]
            s2_data = group_data[group_data["playerId"] == s2].iloc[0]

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
    final Phase 1 description and final Phase 2 description.
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

        # Final description in each phase (highest blockNum)
        final_p1 = phase1_data.loc[phase1_data["blockNum"].idxmax()]
        final_p2 = phase2_data.loc[phase2_data["blockNum"].idxmax()]

        emb1 = embeddings[int(final_p1["embedding_idx"])]
        emb2 = embeddings[int(final_p2["embedding_idx"])]
        sim = model.similarity(emb1, emb2).item()

        # Get condition from games df
        condition = games.loc[games["gameId"] == game, "condition"].values
        condition = condition[0] if len(condition) > 0 else None

        rows.append({
            "gameId": game,
            "playerId": player,
            "originalGroup": final_p1.get("originalGroup", ""),
            "target": target,
            "simPhase1Phase2": sim,
            "condition": condition,
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
        help="Path to analysis/data/ directory with preprocessed CSVs"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory (defaults to data_dir)"
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output) if args.output else data_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading preprocessed data...")
    utterances = pd.read_csv(data_dir / "speaker_utterances.csv")
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

    pairwise = pd.concat([pairwise_p1, pairwise_p2], ignore_index=True)
    pairwise.to_csv(output_dir / "pairwise_similarities.csv", index=False)
    print(f"  Total pairwise: {len(pairwise)} rows")

    print("Computing phase change similarities...")
    phase_change = compute_phase_change_similarities(
        utterances, embeddings, model, games
    )
    phase_change.to_csv(output_dir / "phase_change_similarities.csv", index=False)
    print(f"  {len(phase_change)} phase change similarity values")

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
