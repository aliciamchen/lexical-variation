"""
Combine raw CSVs from extracted runs into data/<dataset>/raw_anonymized/.

Stacks the raw Empirica CSVs, filters out failed games (lobby timeouts),
and writes a manifest.json with provenance info. The runs default to the
timestamps listed in data/<dataset>/runs.txt.

Usage:
    uv run python analysis/combine_runs.py                       # runs from data/pilots/runs.txt
    uv run python analysis/combine_runs.py --dataset full        # runs from data/full/runs.txt
    uv run python analysis/combine_runs.py 20260301_132907 20260301_214147
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from dataset_paths import RUNS_DIR, add_dataset_argument, dataset_dirs
from extract_run import SENSITIVE_COLUMNS

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


def deduplicate_ids(
    combined: dict[str, pd.DataFrame], run_ids: list[str]
) -> dict[str, dict[str, int]]:
    """Collapse records that appear in more than one export, keeping the newest.

    `empirica export` dumps the entire cumulative state of a server, so exports
    taken from the same server overlap: the later one contains everything the
    earlier one did. Stacking them naively would double-count every game,
    player, round and message.

    Because each export is a snapshot rather than an increment, the right way to
    combine a set of them is a union keyed on record id, keeping the version from
    the latest export. That is correct whether `runs.txt` lists one export or
    every export from a server, and it also repairs a subtler case: a mid-session
    backup captures rounds still in progress, while the final export has them
    completed, so the newest version is the one to keep.

    Separate deployments use ULIDs, so their ids never collide; a duplicate
    therefore always means overlapping snapshots of the same server. That is
    legitimate, but it is reported so an unintended overlap -- the wrong server,
    say -- is still visible.
    """
    # Runs are ordered oldest-first (timestamps sort lexically), so the last
    # occurrence of an id is the one from the newest export.
    order = {run_id: i for i, run_id in enumerate(run_ids)}
    collapsed: dict[str, dict[str, int]] = {}
    for csv_name, df in combined.items():
        if "id" not in df.columns or df["id"].duplicated().sum() == 0:
            continue
        dup_ids = df.loc[df["id"].duplicated(keep=False), "id"]
        runs_involved = sorted(
            df.loc[df["id"].isin(set(dup_ids)), "_sourceRun"].unique(),
            key=lambda r: order.get(r, 0),
        )
        before = len(df)
        ranked = df.assign(_runOrder=df["_sourceRun"].map(order)).sort_values(
            "_runOrder", kind="stable"
        )
        deduped = ranked.drop_duplicates(subset="id", keep="last").drop(columns="_runOrder")
        combined[csv_name] = deduped.reset_index(drop=True)
        collapsed[csv_name] = {
            "duplicate_ids": int(dup_ids.nunique()),
            "rows_dropped": before - len(deduped),
            "runs": runs_involved,
        }
    return collapsed


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

    The output directory (data/<dataset>/raw_anonymized/) is committed to the
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
    collapsed: dict[str, dict[str, int]] | None = None,
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
        # Records seen in more than one export, collapsed to the newest version.
        "collapsed_duplicates": collapsed or {},
    }
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  Manifest written to {manifest_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Combine raw CSVs from extracted runs into data/<dataset>/raw_anonymized/"
    )
    parser.add_argument(
        "runs", nargs="*",
        help="Run timestamps (default: the entries of data/<dataset>/runs.txt)"
    )
    add_dataset_argument(parser)
    args = parser.parse_args()

    dirs = dataset_dirs(args.dataset)
    if not args.runs:
        args.runs = dirs.read_runs()
        if not args.runs:
            print(f"Error: no runs given and {dirs.runs_file} is missing or empty.", file=sys.stderr)
            sys.exit(1)
        print(f"Runs from {dirs.runs_file}: {' '.join(args.runs)}")
    output_raw = dirs.raw
    print(f"Dataset: {dirs.name} -> {output_raw}")

    print("Validating runs...")
    if len(set(args.runs)) != len(args.runs):
        print("Error: the same run is listed more than once", file=sys.stderr)
        sys.exit(1)
    # Sorted oldest-first because deduplicate_ids keeps the record from the last
    # run it sees, and export timestamps (YYYYMMDD_HHMMSS) sort chronologically.
    if args.runs != sorted(args.runs):
        print("  Reordered runs oldest-first so the newest export wins on overlap")
        args.runs = sorted(args.runs)
    raw_dirs = validate_runs(args.runs)

    print("\nStacking raw CSVs...")
    combined, input_counts = stack_raw_csvs(raw_dirs, args.runs)
    for run_id in args.runs:
        total = sum(input_counts[run_id].values())
        print(f"  {run_id}: {total} input rows across {len(input_counts[run_id])} files")

    print("\nCollapsing records that appear in more than one export...")
    collapsed = deduplicate_ids(combined, args.runs)
    if not collapsed:
        print("  No overlap: every record id appears in exactly one export")
    else:
        for csv_name, info in collapsed.items():
            print(
                f"  {csv_name}: kept the newest of {info['duplicate_ids']} id(s) "
                f"seen in more than one export, dropping {info['rows_dropped']} row(s) "
                f"(runs: {', '.join(info['runs'])})"
            )
        print(
            "  This is expected when runs.txt lists several exports from the same server.\n"
            "  If those runs should not overlap, you may be combining the wrong exports."
        )

    print("\nFiltering failed games...")
    combined, failed_game_ids = filter_failed_games(combined)

    print("\nEnforcing anonymization...")
    combined = enforce_anonymization(combined)

    print("\nWriting combined raw CSVs...")
    write_combined_raw(combined, output_raw)

    write_manifest(dirs.data, args.runs, combined, input_counts, failed_game_ids, collapsed)

    game_df = combined["game.csv"]
    print(f"\nCombine complete: {len(game_df)} games from {len(args.runs)} runs")
    print(f"  Output: {output_raw}")


if __name__ == "__main__":
    main()
