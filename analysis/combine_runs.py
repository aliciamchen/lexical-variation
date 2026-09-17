"""
Combine raw CSVs from extracted runs into data/<dataset>/raw_anonymized/.

Stacks the raw Empirica CSVs, filters out failed games (lobby timeouts) and
any game listed in data/<dataset>/exclude_games.txt (test and rehearsal games
that ran on the production server), and writes a manifest.json with
provenance info. The runs default to the timestamps listed in
data/<dataset>/runs.txt.

Usage:
    uv run python analysis/combine_runs.py                       # runs from data/pilots/runs.txt
    uv run python analysis/combine_runs.py --dataset full        # runs from data/full/runs.txt
    uv run python analysis/combine_runs.py --dataset full 20260301_132907 20260301_214147

Positional runs for the frozen pilot dataset must be exactly the runs in
data/pilots/runs.txt; --allow-pilot overrides that guard deliberately.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from dataset_paths import (
    FROZEN_DATASET,
    RAW_CSV_FILES,
    RUNS_DIR,
    TIMESTAMP_DIR_PATTERN,
    add_dataset_argument,
    dataset_dirs,
)
from extract_run import SENSITIVE_COLUMNS


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


# Tables whose rows belong to a game through a gameID column.
GAME_DEPENDENT_TABLES = [
    "player.csv", "playerGame.csv", "playerRound.csv", "playerStage.csv",
    "round.csv", "stage.csv",
]


def drop_games(combined: dict[str, pd.DataFrame], game_ids: set[str]) -> dict[str, pd.DataFrame]:
    """Remove the given games from game.csv and every row that belongs to them.

    Rows of the dependent tables are kept only when their gameID is a game that
    survives, so a player, round, stage, or message of a dropped game never
    reaches the combined output.
    """
    game_df = combined["game.csv"]
    game_df = game_df[~game_df["id"].isin(game_ids)].copy()
    combined["game.csv"] = game_df

    valid_game_ids = set(game_df["id"])
    for csv_name in GAME_DEPENDENT_TABLES:
        if csv_name not in combined:
            continue
        df = combined[csv_name]
        if "gameID" in df.columns:
            combined[csv_name] = df[df["gameID"].isin(valid_game_ids)].copy()
    return combined


def filter_failed_games(
    combined: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Remove games with no condition (lobby timeouts) and cascade to related tables."""
    game_df = combined["game.csv"]
    failed_mask = game_df["condition"].isna() | (game_df["condition"] == "")
    failed_ids = set(game_df.loc[failed_mask, "id"])

    if failed_ids:
        print(f"  Filtering out {len(failed_ids)} failed game(s): {failed_ids}")

    return drop_games(combined, failed_ids), sorted(failed_ids)


EXCLUDE_GAMES_FILE = "exclude_games.txt"


def read_excluded_games(data_dir: Path) -> list[str]:
    """Empirica game ids listed in data/<dataset>/exclude_games.txt.

    One id per line; blank lines and `#` comments are ignored, so each entry
    can carry the reason it is excluded. The file is optional. It exists for
    games that ran on the production server but are not data: a rehearsal with
    lab members, a game started to check a deploy, a session the researcher
    stopped. Their rows would otherwise be indistinguishable from real games
    in every table.
    """
    path = data_dir / EXCLUDE_GAMES_FILE
    if not path.exists():
        return []
    ids = []
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            ids.append(line)
    return ids


def exclude_games(
    combined: dict[str, pd.DataFrame], excluded: list[str]
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Drop the games listed in exclude_games.txt and everything that belongs to them.

    Returns the ids that were actually present; an id that matches no game is
    reported, because it usually means a typo rather than an already-absent game.
    """
    if not excluded:
        return combined, []
    present = set(combined["game.csv"]["id"])
    found = [gid for gid in excluded if gid in present]
    missing = [gid for gid in excluded if gid not in present]
    if missing:
        print(
            f"  Warning: {len(missing)} id(s) in {EXCLUDE_GAMES_FILE} match no game in these "
            f"runs: {', '.join(missing)}"
        )
    if not found:
        return combined, []
    before = {name: len(df) for name, df in combined.items()}
    combined = drop_games(combined, set(found))
    dropped = {
        name: before[name] - len(df) for name, df in combined.items() if before[name] != len(df)
    }
    print(
        f"  Excluding {len(found)} game(s) listed in {EXCLUDE_GAMES_FILE}: {', '.join(found)}"
    )
    print("  Rows dropped: " + ", ".join(f"{name} {n}" for name, n in dropped.items()))
    return combined, found


DROPOUTS_FILE = "dropouts.csv"
DROPOUT_COLUMNS = ["playerId", "batchId", "ended", "exitReason", "quizAttempts"]


def split_dropouts(
    players_all: pd.DataFrame,
    games_all: pd.DataFrame,
    combined: dict[str, pd.DataFrame],
    excluded_game_ids: list[str],
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Separate the player records that never played a real game.

    Every participant who reached the experiment has a player record, whether
    they finished a game, failed the quiz, waited in a lobby that timed out, or
    arrived after the games were full. `raw_anonymized/player.csv` keeps only
    the players of real games, so those other records vanish at this step --
    and with them the attrition the manuscript has to report. They are written
    to `dropouts.csv` instead: one row per player record with no real game,
    with the batch it belonged to (through its game, when it had one), how
    Empirica ended it, the exit reason the server set, and how many quiz
    attempts it made. A record attached to a real game that was never started
    (no original group, so the game began without it) is a dropout too and is
    moved out of player.csv. Players of games listed in exclude_games.txt are
    neither data nor dropouts and are left out.

    `players_all` and `games_all` are the tables before any game was filtered.
    Returns the updated tables and the dropouts frame (empty with the header
    when there are none).
    """
    real_games = set(combined["game.csv"]["id"])
    game_batch = games_all.drop_duplicates("id").set_index("id")["batchID"] if "batchID" in games_all.columns else pd.Series(dtype=object)

    in_excluded = players_all["gameID"].isin(set(excluded_game_ids))
    no_real_game = players_all["gameID"].isna() | ~players_all["gameID"].isin(real_games)
    if "original_group" in players_all.columns:
        never_started = players_all["gameID"].isin(real_games) & players_all["original_group"].isna()
    else:
        never_started = pd.Series(False, index=players_all.index)
    is_dropout = (no_real_game | never_started) & ~in_excluded

    rows = players_all[is_dropout]
    dropouts = pd.DataFrame(
        {
            "playerId": rows["id"].values,
            "batchId": rows["gameID"].map(game_batch).values,
            "ended": rows["ended"].values if "ended" in rows.columns else pd.NA,
            "exitReason": rows["exitReason"].values if "exitReason" in rows.columns else pd.NA,
            "quizAttempts": pd.to_numeric(
                rows["quiz_attempts"] if "quiz_attempts" in rows.columns else pd.Series(pd.NA, index=rows.index),
                errors="coerce",
            ).astype("Int64").values,
        },
        columns=DROPOUT_COLUMNS,
    )

    if never_started.any():
        moved = set(players_all.loc[never_started & ~in_excluded, "id"])
        player_df = combined["player.csv"]
        combined["player.csv"] = player_df[~player_df["id"].isin(moved)].copy()
        print(
            f"  Moved {len(moved)} player record(s) of real games that never started "
            f"(no original group) to {DROPOUTS_FILE}"
        )
    return combined, dropouts.reset_index(drop=True)


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
    excluded_game_ids: list[str] | None = None,
    n_dropouts: int = 0,
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
        # Games listed in exclude_games.txt (test and rehearsal games) and dropped.
        "excluded_games": excluded_game_ids or [],
        # Player records with no real game, written to dropouts.csv.
        "dropouts": n_dropouts,
        # Records seen in more than one export, collapsed to the newest version.
        "collapsed_duplicates": collapsed or {},
    }
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  Manifest written to {manifest_path}")


def frozen_dataset_error(
    dataset: str, runs: list[str], registered: list[str], allow_pilot: bool
) -> str | None:
    """Why positional runs may not rebuild the frozen pilot dataset, or None.

    The pilot is complete and committed; `combine_runs.py --dataset pilots
    <runs>` with runs other than those in data/pilots/runs.txt would rewrite
    its raw_anonymized/ from different exports. The default (no positional
    runs) always reads runs.txt and is never blocked, and `--allow-pilot`
    states the intent when the pilot really is to be rebuilt.
    """
    if dataset != FROZEN_DATASET or not runs or allow_pilot:
        return None
    if sorted(runs) == sorted(registered):
        return None
    return (
        f"the '{FROZEN_DATASET}' dataset is frozen: the runs given "
        f"({' '.join(sorted(runs))}) are not the runs in its runs.txt "
        f"({' '.join(sorted(registered)) or 'none'}). Pass --allow-pilot to rebuild the "
        "pilot from these exports anyway, or --dataset <name> for another dataset."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Combine raw CSVs from extracted runs into data/<dataset>/raw_anonymized/"
    )
    parser.add_argument(
        "runs", nargs="*",
        help="Run timestamps (default: the entries of data/<dataset>/runs.txt)"
    )
    add_dataset_argument(parser)
    parser.add_argument(
        "--allow-pilot", action="store_true",
        help=(
            f"Allow positional runs that differ from data/{FROZEN_DATASET}/runs.txt for the "
            f"frozen '{FROZEN_DATASET}' dataset"
        ),
    )
    args = parser.parse_args()

    dirs = dataset_dirs(args.dataset)
    error = frozen_dataset_error(dirs.name, args.runs, dirs.read_runs(), args.allow_pilot)
    if error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
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

    # Kept before any game is filtered, for the dropout record below.
    players_all = combined["player.csv"].copy()
    games_all = combined["game.csv"].copy()

    print("\nFiltering failed games...")
    combined, failed_game_ids = filter_failed_games(combined)

    print(f"\nExcluding games listed in {dirs.data / EXCLUDE_GAMES_FILE}...")
    excluded = read_excluded_games(dirs.data)
    if not excluded:
        print("  No exclusions (the file is absent or empty)")
    combined, excluded_game_ids = exclude_games(combined, excluded)

    print("\nRecording player records with no real game...")
    combined, dropouts = split_dropouts(players_all, games_all, combined, excluded_game_ids)
    dropouts_path = dirs.data / DROPOUTS_FILE
    dirs.data.mkdir(parents=True, exist_ok=True)
    dropouts.to_csv(dropouts_path, index=False)
    if dropouts.empty:
        print(f"  None; wrote an empty {DROPOUTS_FILE} (header only)")
    else:
        reasons = dropouts["exitReason"].fillna(dropouts["ended"]).fillna("unknown").value_counts()
        summary = ", ".join(f"{reason}: {n}" for reason, n in reasons.items())
        print(f"  {len(dropouts)} dropout record(s) written to {dropouts_path} ({summary})")

    print("\nEnforcing anonymization...")
    combined = enforce_anonymization(combined)

    print("\nWriting combined raw CSVs...")
    write_combined_raw(combined, output_raw)

    write_manifest(
        dirs.data, args.runs, combined, input_counts, failed_game_ids, collapsed,
        excluded_game_ids, len(dropouts),
    )

    game_df = combined["game.csv"]
    print(f"\nCombine complete: {len(game_df)} games from {len(args.runs)} runs")
    print(f"  Output: {output_raw}")


if __name__ == "__main__":
    main()
