#!/usr/bin/env python3
"""
Process LLM simulation JSONs into analysis-ready CSVs.

Reads group JSON files from a results directory and produces:
  - llm_rounds.csv: one row per round (speaker description + listener results)
  - llm_listener_trials.csv: one row per listener per round
  - llm_exclusion.csv: per-player accuracy in last 3 blocks + group pass/fail
  - llm_similarity.csv: adjacent-description SBERT similarity per tangram
  - llm_config.json: run metadata (model, temperature, etc.)

Usage:
  uv run python analysis/llm_simulation/process_llm_results.py analysis/llm_simulation/llm_results_*/
  uv run python analysis/llm_simulation/process_llm_results.py  # auto-detects most recent
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


GROUP_SIZE = 3
ACCURACY_THRESHOLD = 2 / 3
PLAYER_THRESHOLD = 2
LAST_N_BLOCKS = 3


def find_results_dir() -> Path:
    """Find the most recent llm_results_* directory."""
    analysis_dir = Path(__file__).parent
    candidates = sorted(analysis_dir.glob("llm_results_*"), reverse=True)
    if not candidates:
        print("No llm_results_* directory found. Run the simulation first.",
              file=sys.stderr)
        sys.exit(1)
    return candidates[0]


def load_groups(results_dir: Path) -> list[dict]:
    """Load all group JSONs from results directory."""
    files = sorted(results_dir.glob("G*.json"))
    if not files:
        print(f"No G*.json files in {results_dir}", file=sys.stderr)
        sys.exit(1)
    groups = []
    for f in files:
        groups.append(json.loads(f.read_text()))
    return groups


def build_rounds_csv(groups: list[dict]) -> pd.DataFrame:
    """One row per round: speaker description + aggregate listener accuracy."""
    rows = []
    for g in groups:
        for r in g["rounds"]:
            n_correct = sum(1 for lr in r["listener_results"] if lr["correct"])
            rows.append({
                "group_id": g["group_id"],
                "round_num": r["round_num"],
                "block_num": r["block_num"],
                "target": r["target"],
                "speaker_id": r["speaker_id"],
                "description": r["description"],
                "word_count": r["word_count"],
                "accuracy": r["accuracy"],
                "n_listeners_correct": n_correct,
            })
    return pd.DataFrame(rows)


def build_listener_trials_csv(groups: list[dict]) -> pd.DataFrame:
    """One row per listener per round."""
    rows = []
    for g in groups:
        for r in g["rounds"]:
            for lr in r["listener_results"]:
                rows.append({
                    "group_id": g["group_id"],
                    "round_num": r["round_num"],
                    "block_num": r["block_num"],
                    "target": r["target"],
                    "speaker_id": r["speaker_id"],
                    "listener_id": lr["listener_id"],
                    "selection": lr["selection"],
                    "correct": lr["correct"],
                })
    return pd.DataFrame(rows)


def build_exclusion_csv(groups: list[dict], n_blocks: int) -> pd.DataFrame:
    """Per-player listener accuracy in last 3 blocks + group pass/fail."""
    last_blocks = list(range(n_blocks - LAST_N_BLOCKS, n_blocks))
    rows = []
    for g in groups:
        player_stats = {i: {"correct": 0, "total": 0} for i in range(GROUP_SIZE)}
        for r in g["rounds"]:
            if r["block_num"] not in last_blocks:
                continue
            for lr in r["listener_results"]:
                pid = lr["listener_id"]
                player_stats[pid]["total"] += 1
                if lr["correct"]:
                    player_stats[pid]["correct"] += 1

        player_accs = {}
        for pid, stats in player_stats.items():
            player_accs[pid] = stats["correct"] / stats["total"] if stats["total"] > 0 else 0.0

        n_passing = sum(1 for a in player_accs.values() if a >= ACCURACY_THRESHOLD)

        for pid, acc in player_accs.items():
            rows.append({
                "group_id": g["group_id"],
                "player_id": pid,
                "listener_accuracy": round(acc, 4),
                "passes_threshold": acc >= ACCURACY_THRESHOLD,
            })

    df = pd.DataFrame(rows)

    # Add group-level pass/fail
    group_pass = (
        df[df["passes_threshold"]]
        .groupby("group_id")
        .size()
        .reindex(df["group_id"].unique(), fill_value=0)
        .rename("n_players_passing")
        .reset_index()
    )
    group_pass["group_passes"] = group_pass["n_players_passing"] >= PLAYER_THRESHOLD
    df = df.merge(group_pass, on="group_id")
    return df


def build_similarity_csv(
    groups: list[dict], model: SentenceTransformer
) -> pd.DataFrame:
    """Adjacent-description SBERT similarity per tangram per group."""
    rows = []
    for g in groups:
        # Organize descriptions by tangram
        tangram_descs: dict[str, list[tuple[int, str]]] = {}
        for r in g["rounds"]:
            tangram_descs.setdefault(r["target"], []).append(
                (r["block_num"], r["description"])
            )

        for target, descs in tangram_descs.items():
            descs_sorted = sorted(descs, key=lambda x: x[0])
            if len(descs_sorted) < 2:
                continue

            texts = [d[1] for d in descs_sorted]
            embeddings = model.encode(texts)

            for i in range(1, len(descs_sorted)):
                sim = cosine_similarity([embeddings[i - 1]], [embeddings[i]])[0][0]
                rows.append({
                    "group_id": g["group_id"],
                    "target": target,
                    "block_num": descs_sorted[i][0],
                    "prev_block_num": descs_sorted[i - 1][0],
                    "similarity": round(float(sim), 4),
                })

    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Process LLM simulation JSONs into CSVs",
    )
    parser.add_argument(
        "results_dir", nargs="?", default=None,
        help="Path to llm_results_* directory (default: most recent)",
    )
    parser.add_argument(
        "--skip-similarity", action="store_true",
        help="Skip SBERT similarity computation (faster)",
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir) if args.results_dir else find_results_dir()
    print(f"Processing: {results_dir}")

    groups = load_groups(results_dir)
    n_groups = len(groups)
    n_blocks = groups[0].get("config", {}).get("num_blocks", 6)
    model_name = groups[0]["model"]
    temperature = groups[0].get("config", {}).get("temperature")

    print(f"  {n_groups} groups, {n_blocks} blocks, model={model_name}, temp={temperature}")

    # Rounds
    rounds_df = build_rounds_csv(groups)
    rounds_df.to_csv(results_dir / "llm_rounds.csv", index=False)
    print(f"  llm_rounds.csv: {len(rounds_df)} rows")

    # Listener trials
    listener_df = build_listener_trials_csv(groups)
    listener_df.to_csv(results_dir / "llm_listener_trials.csv", index=False)
    print(f"  llm_listener_trials.csv: {len(listener_df)} rows")

    # Exclusion criterion
    exclusion_df = build_exclusion_csv(groups, n_blocks)
    exclusion_df.to_csv(results_dir / "llm_exclusion.csv", index=False)
    n_pass = exclusion_df.drop_duplicates("group_id")["group_passes"].sum()
    print(f"  llm_exclusion.csv: {n_pass}/{n_groups} groups pass criterion")

    # Similarity
    if not args.skip_similarity:
        print("  Computing SBERT similarities...")
        sbert = SentenceTransformer("sentence-transformers/paraphrase-MiniLM-L12-v2")
        sim_df = build_similarity_csv(groups, sbert)
        sim_df.to_csv(results_dir / "llm_similarity.csv", index=False)
        print(f"  llm_similarity.csv: {len(sim_df)} rows")
    else:
        print("  Skipping similarity (--skip-similarity)")

    # Config summary
    config = {
        "results_dir": str(results_dir),
        "n_groups": n_groups,
        "n_blocks": n_blocks,
        "model": model_name,
        "temperature": temperature,
        "n_groups_passing": int(n_pass),
    }
    (results_dir / "llm_config.json").write_text(json.dumps(config, indent=2))
    print(f"  llm_config.json written")

    print("Done.")


if __name__ == "__main__":
    main()
