"""
Combine raw CSVs from multiple extracted runs into data/pilots/raw_anonymized/.

Stacks the raw Empirica CSVs, filters out failed games (lobby timeouts),
and writes a manifest.json with provenance info.

Usage:
    uv run python analysis/combine_runs.py 20260301_132907 20260301_214147
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RUNS_DIR = DATA_DIR / "pilot_runs"
PILOTS_DIR = DATA_DIR / "pilots"

TIMESTAMP_DIR_PATTERN = re.compile(r"^\d{8}_\d{6}$")

RAW_CSV_FILES = [
    "batch.csv",
    "game.csv",
    "global.csv",
    "player.csv",
    "playerGame.csv",
    "playerRound.csv",
    "playerStage.csv",
    "round.csv",
    "stage.csv",
]


def validate_runs(run_ids: list[str]) -> list[Path]:
    """Check that each run's raw/ directory exists, return paths."""
    raw_dirs = []
    for run_id in run_ids:
        raw_dir = RUNS_DIR / run_id / "raw"
        if not raw_dir.is_dir():
            print(f"Error: {raw_dir} does not exist", file=sys.stderr)
            print("Run extract_run.py first to process the zip.", file=sys.stderr)
            sys.exit(1)
        raw_dirs.append(raw_dir)
    return raw_dirs


def stack_raw_csvs(raw_dirs: list[Path], run_ids: list[str]) -> dict[str, pd.DataFrame]:
    """Concatenate each raw CSV across runs, adding _sourceRun column."""
    combined = {}
    for csv_name in RAW_CSV_FILES:
        frames = []
        for raw_dir, run_id in zip(raw_dirs, run_ids):
            csv_path = raw_dir / csv_name
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                df["_sourceRun"] = run_id
                frames.append(df)
        if frames:
            combined[csv_name] = pd.concat(frames, ignore_index=True, join="outer")
        else:
            print(f"  Warning: {csv_name} not found in any run")
    return combined


def filter_failed_games(combined: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Remove games with no condition (lobby timeouts) and cascade to related tables."""
    game_df = combined["game.csv"]
    failed_mask = game_df["condition"].isna() | (game_df["condition"] == "")
    failed_ids = set(game_df.loc[failed_mask, "id"])

    if failed_ids:
        print(f"  Filtering out {len(failed_ids)} failed game(s): {failed_ids}")

    game_df = game_df[~game_df["id"].isin(failed_ids)].copy()
    combined["game.csv"] = game_df

    valid_game_ids = set(game_df["id"])
    for csv_name in ["player.csv", "playerGame.csv", "playerRound.csv",
                     "playerStage.csv", "round.csv", "stage.csv"]:
        if csv_name not in combined:
            continue
        df = combined[csv_name]
        if "gameID" in df.columns:
            combined[csv_name] = df[df["gameID"].isin(valid_game_ids)].copy()

    return combined


def write_combined_raw(combined: dict[str, pd.DataFrame], output_raw: Path):
    """Write combined raw CSVs to output directory."""
    output_raw.mkdir(parents=True, exist_ok=True)
    for csv_name, df in combined.items():
        df.to_csv(output_raw / csv_name, index=False)
        print(f"  {csv_name}: {len(df)} rows")


def write_manifest(output_dir: Path, run_ids: list[str], combined: dict[str, pd.DataFrame]):
    """Write manifest.json with provenance info."""
    game_df = combined["game.csv"]
    manifest = {
        "source_runs": run_ids,
        "created": datetime.now().isoformat(),
        "games": len(game_df),
        "conditions": game_df["condition"].value_counts().to_dict(),
        "row_counts": {name: len(df) for name, df in combined.items()},
    }
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  Manifest written to {manifest_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Combine raw CSVs from multiple extracted runs into data/pilots/raw_anonymized/"
    )
    parser.add_argument(
        "runs", nargs="+",
        help="Run timestamps (e.g. 20260301_132907 20260301_214147)"
    )
    args = parser.parse_args()

    output_raw = PILOTS_DIR / "raw_anonymized"

    print("Validating runs...")
    raw_dirs = validate_runs(args.runs)

    print("\nStacking raw CSVs...")
    combined = stack_raw_csvs(raw_dirs, args.runs)

    print("\nFiltering failed games...")
    combined = filter_failed_games(combined)

    print("\nWriting combined raw CSVs...")
    write_combined_raw(combined, output_raw)

    write_manifest(PILOTS_DIR, args.runs, combined)

    game_df = combined["game.csv"]
    print(f"\nCombine complete: {len(game_df)} games from {len(args.runs)} runs")
    print(f"  Output: {output_raw}")


if __name__ == "__main__":
    main()
