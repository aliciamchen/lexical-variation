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

from extract_run import SENSITIVE_COLUMNS

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


def stack_raw_csvs(
    raw_dirs: list[Path], run_ids: list[str]
) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, int]]]:
    """Concatenate each raw CSV across runs, adding _sourceRun column.

    Returns the combined tables and per-run input row counts so the output
    can be reconciled against the inputs.
    """
    combined = {}
    input_counts: dict[str, dict[str, int]] = {run_id: {} for run_id in run_ids}
    for csv_name in RAW_CSV_FILES:
        frames = []
        present_in = []
        for raw_dir, run_id in zip(raw_dirs, run_ids):
            csv_path = raw_dir / csv_name
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                df["_sourceRun"] = run_id
                frames.append(df)
                present_in.append(run_id)
                input_counts[run_id][csv_name] = len(df)
        if frames:
            if len(present_in) < len(run_ids):
                missing = sorted(set(run_ids) - set(present_in))
                print(f"  Warning: {csv_name} missing from run(s): {', '.join(missing)}")
            stacked = pd.concat(frames, ignore_index=True, join="outer")
            if len(stacked) != sum(len(f) for f in frames):
                print(
                    f"Error: {csv_name}: stacked row count {len(stacked)} != "
                    f"sum of per-run inputs {sum(len(f) for f in frames)}",
                    file=sys.stderr,
                )
                sys.exit(1)
            combined[csv_name] = stacked
        else:
            print(f"  Warning: {csv_name} not found in any run")
    return combined, input_counts


def check_duplicate_ids(combined: dict[str, pd.DataFrame]):
    """Hard-fail if any record id appears more than once in the stacked tables.

    `empirica export` dumps the entire cumulative state of a server, so two
    exports taken from the same server overlap, and combining them would
    silently double-count every game, player, round, and message. Separate
    deployments use ULIDs, so their ids never collide; any duplicate therefore
    means the same records were passed in twice (overlapping exports, or a run
    listed twice).
    """
    errors = []
    for csv_name, df in combined.items():
        if "id" not in df.columns:
            continue
        dups = df.loc[df["id"].duplicated(keep=False), ["id", "_sourceRun"]]
        if dups.empty:
            continue
        n_ids = dups["id"].nunique()
        runs = sorted(dups["_sourceRun"].unique())
        examples = ", ".join(dups["id"].astype(str).unique()[:3])
        errors.append(
            f"  {csv_name}: {n_ids} duplicated id(s) "
            f"(runs involved: {', '.join(runs)}; e.g. {examples})"
        )
    if errors:
        print(
            "Error: duplicate record ids detected — the same data appears more "
            "than once (overlapping cumulative exports, or a run listed twice):",
            file=sys.stderr,
        )
        for err in errors:
            print(err, file=sys.stderr)
        sys.exit(1)


def filter_failed_games(
    combined: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], list[str]]:
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

    return combined, sorted(failed_ids)


def enforce_anonymization(combined: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Strip sensitive Prolific columns if any slipped through extraction.

    The output directory (data/pilots/raw_anonymized/) is committed to the
    repo, so anonymization must be guaranteed here regardless of how the
    per-run raw/ files were produced -- runs extracted before anonymization
    was added to extract_run.py still carry these columns.
    """
    player_df = combined.get("player.csv")
    if player_df is None:
        return combined
    present = [c for c in SENSITIVE_COLUMNS if c in player_df.columns]
    if present:
        print(
            f"  WARNING: sensitive column(s) found in player.csv and stripped: {present}\n"
            "  Re-extract the affected runs with the current extract_run.py "
            "to fix them at the source."
        )
        combined["player.csv"] = player_df.drop(columns=present)
    return combined


def write_combined_raw(combined: dict[str, pd.DataFrame], output_raw: Path):
    """Write combined raw CSVs to output directory."""
    output_raw.mkdir(parents=True, exist_ok=True)
    for csv_name, df in combined.items():
        df.to_csv(output_raw / csv_name, index=False)
        print(f"  {csv_name}: {len(df)} rows")


def write_manifest(
    output_dir: Path,
    run_ids: list[str],
    combined: dict[str, pd.DataFrame],
    input_counts: dict[str, dict[str, int]],
    failed_game_ids: list[str],
):
    """Write manifest.json with provenance info."""
    game_df = combined["game.csv"]
    manifest = {
        "source_runs": run_ids,
        "created": datetime.now().isoformat(),
        "games": len(game_df),
        "conditions": game_df["condition"].value_counts().to_dict(),
        "row_counts": {name: len(df) for name, df in combined.items()},
        "input_row_counts": input_counts,
        "filtered_failed_games": failed_game_ids,
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
    if len(set(args.runs)) != len(args.runs):
        print("Error: the same run is listed more than once", file=sys.stderr)
        sys.exit(1)
    raw_dirs = validate_runs(args.runs)

    print("\nStacking raw CSVs...")
    combined, input_counts = stack_raw_csvs(raw_dirs, args.runs)
    for run_id in args.runs:
        total = sum(input_counts[run_id].values())
        print(f"  {run_id}: {total} input rows across {len(input_counts[run_id])} files")

    print("\nChecking for duplicate records across runs...")
    check_duplicate_ids(combined)
    print("  OK: all record ids unique")

    print("\nFiltering failed games...")
    combined, failed_game_ids = filter_failed_games(combined)

    print("\nEnforcing anonymization...")
    combined = enforce_anonymization(combined)

    print("\nWriting combined raw CSVs...")
    write_combined_raw(combined, output_raw)

    write_manifest(PILOTS_DIR, args.runs, combined, input_counts, failed_game_ids)

    game_df = combined["game.csv"]
    print(f"\nCombine complete: {len(game_df)} games from {len(args.runs)} runs")
    print(f"  Output: {output_raw}")


if __name__ == "__main__":
    main()
