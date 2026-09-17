"""
Extract an Empirica export zip into data/runs/{timestamp}/.

Unzips, extracts bonuses (with Prolific IDs), and saves anonymized raw CSVs.

Usage:
    uv run python analysis/extract_run.py <zip> --dataset full          # extract one export and register it
    uv run python analysis/extract_run.py --dataset full                # most recent zip under experiment/data/
    uv run python analysis/extract_run.py <zip> --dataset full --batch <batch_id>  # pay a specific batch, not the newest
    uv run python analysis/extract_run.py <zip> --dataset full --all-batches       # every batch in the export (rarely right)
    uv run python analysis/extract_run.py <zip> --dataset smoke --no-register      # extract without touching runs.txt
    uv run python analysis/extract_run.py list                          # list extracted runs
    uv run python analysis/extract_run.py bonuses [--run <timestamp>]   # print bonuses for a run (default: latest)
    uv run python analysis/extract_run.py early-ended [--run <timestamp>]  # print early-ended players

The options of the default (extract) form may come in any order around the zip
path. The pilot dataset is frozen: without --dataset (or DATASET) the script
refuses to extract, so a full-sample export is never registered into it.
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import pandas as pd

from dataset_paths import (
    FROZEN_DATASET,
    PROJECT_ROOT,
    RAW_CSV_FILES,
    RUNS_DIR,
    TIMESTAMP_DIR_PATTERN,
    add_dataset_argument,
    dataset_dirs,
)

# The inspection subcommands; anything else on the command line is an extract.
SUBCOMMANDS = {"list", "bonuses", "early-ended"}

EXPERIMENT_DATA_DIR = PROJECT_ROOT / "experiment" / "data"

ZIP_PATTERN = re.compile(r"empirica-export-(\d{8}_\d{6})\.zip")

# Columns to strip from player.csv for anonymization.
# `userAgent` is recorded so a live session can be debugged against the real
# browser, but it is a fingerprinting vector, so it is dropped here and never
# reaches the committed data. The coarse device fields the analysis actually
# uses are in `client_context`, which is kept.
SENSITIVE_COLUMNS = [
    "userAgent",
    "userAgentLastChangedAt",
    "participantIdentifier",
    "participantIdentifierLastChangedAt",
    "prolificPid",
    "prolificPidLastChangedAt",
    "studyId",
    "studyIdLastChangedAt",
    "sessionId",
    "sessionIdLastChangedAt",
    "urlParams",
    "urlParamsLastChangedAt",
]


def find_most_recent_zip() -> Path:
    """Find the most recent empirica-export zip under experiment/data/."""
    zips = []
    for z in EXPERIMENT_DATA_DIR.rglob("empirica-export-*.zip"):
        m = ZIP_PATTERN.search(z.name)
        if m:
            zips.append((m.group(1), z))
    if not zips:
        print("No empirica-export-*.zip found under experiment/data/", file=sys.stderr)
        sys.exit(1)
    zips.sort(key=lambda x: x[0])
    return zips[-1][1]


def extract_datetime(zip_path: Path) -> str:
    """Extract datetime string from zip filename."""
    m = ZIP_PATTERN.search(zip_path.name)
    if not m:
        print(
            f"Cannot parse datetime from zip filename: {zip_path.name}", file=sys.stderr
        )
        sys.exit(1)
    return m.group(1)


def unzip(zip_path: Path) -> Path:
    """Unzip to a temp directory and return the path."""
    print(f"Unzipping {zip_path.name}...")
    tmp_dir = Path(tempfile.mkdtemp(prefix="empirica_export_"))
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(tmp_dir)
    csv_count = len(list(tmp_dir.glob("*.csv")))
    print(f"  Extracted {csv_count} files")
    return tmp_dir


def resolve_batch(game_df: pd.DataFrame, batch_df: pd.DataFrame, explicit: str | None):
    """Pick the batch whose players this export should pay.

    `empirica export` dumps the whole server, so an export taken after several
    sessions contains every earlier session's games. Payments are per session,
    so the bonus files are scoped to one batch -- by default the newest one that
    actually ran a game. Batch ids are ULIDs, which sort lexicographically by
    creation time, and `configLastChangedAt` is used in preference when present.
    """
    played = game_df[game_df["condition"].notna()]
    batches = [b for b in played["batchID"].dropna().unique().tolist() if b]
    if not batches:
        return None, []

    if explicit:
        if explicit not in batches:
            listing = "\n".join(f"    {b}" for b in sorted(batches))
            print(
                f"No batch {explicit!r} with games in this export. Batches present:\n{listing}",
                file=sys.stderr,
            )
            sys.exit(1)
        return explicit, batches

    order = {}
    if "configLastChangedAt" in batch_df.columns:
        for _, row in batch_df.iterrows():
            stamp = row.get("configLastChangedAt")
            if isinstance(stamp, str) and stamp:
                order[row["id"]] = stamp
    newest = max(batches, key=lambda b: (order.get(b, ""), b))
    return newest, batches


def extract_bonuses(
    unzipped_dir: Path,
    output_dir: Path,
    batch: str | None = None,
    all_batches: bool = False,
) -> dict:
    """Write bonuses.csv and early_ended.csv for one batch (one session).

    Returns a small record of what was scoped, which the caller saves beside the
    CSVs so `operations/session.py pay` can show which session it is paying.
    """
    print("Extracting bonuses...")
    player_df = pd.read_csv(unzipped_dir / "player.csv")
    game_df = pd.read_csv(unzipped_dir / "game.csv")
    batch_df = pd.read_csv(unzipped_dir / "batch.csv")

    chosen, all_present = resolve_batch(game_df, batch_df, batch)
    played = game_df[game_df["condition"].notna()]
    if all_batches or chosen is None:
        if all_batches:
            print("  --all-batches: paying every batch in this export.")
        real_games = played["id"].tolist()
        scope = {"batch": None, "batches_present": all_present}
    else:
        in_batch = played[played["batchID"] == chosen]
        real_games = in_batch["id"].tolist()
        skipped = len(played) - len(in_batch)
        print(f"  Batch {chosen}: {len(in_batch)} game(s)")
        if skipped:
            print(
                f"  Ignoring {skipped} game(s) from {len(all_present) - 1} earlier batch(es) "
                "in this cumulative export -- they belong to earlier sessions and were paid then."
            )
            print("  Pass --batch <id> to pay a different one, or --all-batches to include them.")
        scope = {"batch": chosen, "batches_present": all_present}
    scope["games"] = real_games

    game_players = player_df[player_df["gameID"].isin(real_games)].copy()

    completed = game_players[game_players["is_active"] == True].copy()
    early = game_players[game_players["is_active"] == False].copy()

    bonus_df = completed[["participantIdentifier", "bonus"]].copy()
    bonus_df.columns = ["prolific_id", "bonus"]
    bonus_df["bonus"] = bonus_df["bonus"].fillna(0).round(2)

    output_dir.mkdir(parents=True, exist_ok=True)
    bonus_path = output_dir / "bonuses.csv"
    bonus_df.to_csv(bonus_path, index=False)
    print(f"  Wrote {bonus_path} ({len(bonus_df)} players)")
    print(bonus_df.to_string(index=False))

    if len(early) > 0:
        # exitReason travels with the Prolific ID here because it is stripped from
        # the anonymized raw CSVs, and operations/session.py needs the pairing to
        # word the return request and partial-payment note for each participant.
        early_cols = ["participantIdentifier", "partialPay"]
        if "exitReason" in early.columns:
            early_cols.append("exitReason")
        early_df = early[early_cols].copy()
        early_df.columns = ["prolific_id", "partial_pay", "exit_reason"][: len(early_cols)]
        early_df["partial_pay"] = early_df["partial_pay"].fillna(0).round(2)
        if "exit_reason" in early_df.columns:
            early_df["exit_reason"] = early_df["exit_reason"].fillna("")
        early_path = output_dir / "early_ended.csv"
        early_df.to_csv(early_path, index=False)
        print(f"\n  Wrote {early_path} ({len(early_df)} early-ended players)")
        print(early_df.to_string(index=False))
    else:
        print("  No early-ended players found.")

    scope["finishers"] = len(bonus_df)
    scope["early_ended"] = len(early)
    return scope


def anonymize_raw(unzipped_dir: Path, raw_dir: Path) -> None:
    """Copy raw CSVs, stripping sensitive columns from player.csv."""
    print("Anonymizing raw CSVs...")
    raw_dir.mkdir(parents=True, exist_ok=True)

    for csv_file in sorted(unzipped_dir.glob("*.csv")):
        if csv_file.name == "player.csv":
            df = pd.read_csv(csv_file)
            cols_to_drop = [c for c in SENSITIVE_COLUMNS if c in df.columns]
            if cols_to_drop:
                df = df.drop(columns=cols_to_drop)
                print(f"  {csv_file.name}: dropped {cols_to_drop}")
            df.to_csv(raw_dir / csv_file.name, index=False)
        else:
            shutil.copy2(csv_file, raw_dir / csv_file.name)
            print(f"  {csv_file.name}: copied")


def find_timestamped_dirs() -> list[Path]:
    """Find all timestamped run directories under data/runs/."""
    if not RUNS_DIR.is_dir():
        return []
    dirs = []
    for d in sorted(RUNS_DIR.iterdir(), reverse=True):
        if d.is_dir() and TIMESTAMP_DIR_PATTERN.match(d.name):
            dirs.append(d)
    return dirs


def cmd_list():
    """List all extracted runs."""
    dirs = find_timestamped_dirs()
    if not dirs:
        print(f"No runs found in {RUNS_DIR}.")
        return
    print(f"\nExtracted runs ({RUNS_DIR}):")
    print(f"{'─' * 90}")
    for d in dirs:
        has_bonuses = "yes" if (d / "bonuses.csv").exists() else "no"
        n_files = sum(1 for _ in d.rglob("*") if _.is_file())
        print(f"  {d.name}  bonuses: {has_bonuses}  {n_files} files")
    print()


def cmd_bonuses(run_name: str | None = None):
    """Print bonus CSV for a specific or latest run."""
    if run_name:
        bonus_dir = RUNS_DIR / run_name
    else:
        dirs = find_timestamped_dirs()
        if not dirs:
            print("No runs found.", file=sys.stderr)
            sys.exit(1)
        bonus_dir = dirs[0]
    bonus_path = bonus_dir / "bonuses.csv"
    if not bonus_path.exists():
        print(f"No bonuses.csv in {bonus_dir.name}", file=sys.stderr)
        sys.exit(1)
    df = pd.read_csv(bonus_path)
    print(f"\nBonuses for run {bonus_dir.name}:")
    print(f"{'─' * 50}")
    print(df.to_string(index=False))
    print(f"{'─' * 50}")
    print(f"  Total: ${df['bonus'].sum():.2f} across {len(df)} players")
    print(f"  Mean:  ${df['bonus'].mean():.2f}")
    print()


def cmd_early_ended(run_name: str | None = None):
    """Print early-ended players CSV for a specific or latest run."""
    if run_name:
        run_dir = RUNS_DIR / run_name
    else:
        dirs = find_timestamped_dirs()
        if not dirs:
            print("No runs found.", file=sys.stderr)
            sys.exit(1)
        run_dir = dirs[0]
    early_path = run_dir / "early_ended.csv"
    if not early_path.exists():
        print(f"No early_ended.csv in {run_dir.name}", file=sys.stderr)
        sys.exit(1)
    df = pd.read_csv(early_path)
    print(f"\nEarly-ended players for run {run_dir.name}:")
    print(f"{'─' * 80}")
    print(df.to_string(index=False))
    print(f"{'─' * 80}")
    print(f"  {len(df)} players, total partial pay: ${df['partial_pay'].sum():.2f}")
    print()


def cmd_extract(
    zip_path_arg: str | None,
    dataset: str | None = None,
    batch: str | None = None,
    all_batches: bool = False,
    register: bool = True,
):
    """Extract a single zip and, unless `register` is false, add it to the dataset's runs.txt."""
    # The pilot dataset is complete and committed. Registering a new export into
    # it by default -- which is what happens when neither --dataset nor DATASET is
    # given -- would fold full-sample games into the pilot on the next combine.
    if not dataset and not os.environ.get("DATASET"):
        print(
            "Refusing to extract into the default dataset 'pilots', which is frozen.\n"
            "Pass --dataset full (or export DATASET=full) for full-sample sessions.",
            file=sys.stderr,
        )
        sys.exit(1)
    if zip_path_arg:
        zip_path = Path(zip_path_arg).resolve()
        if not zip_path.exists():
            print(f"Zip file not found: {zip_path}", file=sys.stderr)
            sys.exit(1)
    else:
        zip_path = find_most_recent_zip()

    datetime_str = extract_datetime(zip_path)
    output_dir = RUNS_DIR / datetime_str
    raw_dir = output_dir / "raw"

    dirs = dataset_dirs(dataset)
    if dirs.name == FROZEN_DATASET and datetime_str not in dirs.read_runs():
        print(
            f"Refusing to add run {datetime_str} to the pilot dataset, which is frozen: "
            f"only the runs already in {dirs.runs_file} may be re-extracted.\n"
            "Pass --dataset full for a full-sample session.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Zip: {zip_path}")
    print(f"Output: {output_dir}")

    unzipped_dir = unzip(zip_path)

    try:
        scope = extract_bonuses(unzipped_dir, output_dir, batch=batch, all_batches=all_batches)
        anonymize_raw(unzipped_dir, raw_dir)
    finally:
        shutil.rmtree(unzipped_dir, ignore_errors=True)

    # Saved beside the CSVs so `session.py pay` can say which session it is
    # paying, and so a re-export of an older server is recognizable after the fact.
    scope["export"] = datetime_str
    (output_dir / "run_meta.json").write_text(json.dumps(scope, indent=2) + "\n")

    print(f"\nDone. Raw CSVs in {raw_dir}")
    print(f"Bonuses in {output_dir / 'bonuses.csv'}")

    if not register:
        print(f"Not registered in {dirs.runs_file} (--no-register)")
    elif dirs.register_run(datetime_str):
        print(f"Registered {datetime_str} in {dirs.runs_file}")
    else:
        print(f"Already registered in {dirs.runs_file}")
    print(f"Next: uv run python analysis/combine_runs.py --dataset {dirs.name}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extract an Empirica export zip into data/runs/<timestamp>/ (the default "
            "form), or inspect the runs already extracted."
        )
    )
    sub = parser.add_subparsers(dest="command")

    extract = sub.add_parser(
        "extract",
        help="Extract one export zip (implied when no subcommand is given)",
        description="Unzip an export, strip the sensitive participant columns, write bonuses.csv, "
        "and register the run in data/<dataset>/runs.txt.",
    )
    extract.add_argument(
        "zip", nargs="?", default=None,
        help="Path to empirica-export-<timestamp>.zip (default: the most recent zip under experiment/data/)",
    )
    add_dataset_argument(extract)
    extract.add_argument(
        "--batch", default=None,
        help="Pay this batch id rather than the newest batch in the export",
    )
    extract.add_argument(
        "--all-batches", action="store_true",
        help="Pay every batch in the export (rarely right: exports are cumulative)",
    )
    extract.add_argument(
        "--no-register", action="store_true",
        help="Do not add the run to data/<dataset>/runs.txt (used by make smoke)",
    )

    sub.add_parser("list", help="List the extracted runs in data/runs/")
    for name, help_text in (
        ("bonuses", "Print the bonuses of a run"),
        ("early-ended", "Print the early-ended players of a run"),
    ):
        p = sub.add_parser(name, help=f"{help_text} (default: the latest)")
        p.add_argument("--run", default=None, help="Run timestamp (default: the most recent extracted run)")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line, treating a call without a subcommand as `extract`.

    `extract_run.py <zip> --dataset full`, `extract_run.py --dataset full <zip>`,
    and a bare `extract_run.py --dataset full` (most recent zip) are all the
    extract form; `list`, `bonuses`, and `early-ended` are the subcommands.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or (argv[0] not in SUBCOMMANDS | {"extract"} and argv[0] not in ("-h", "--help")):
        argv.insert(0, "extract")
    return build_parser().parse_args(argv)


def main():
    args = parse_args()
    if args.command == "list":
        cmd_list()
    elif args.command == "bonuses":
        cmd_bonuses(args.run)
    elif args.command == "early-ended":
        cmd_early_ended(args.run)
    else:
        cmd_extract(
            args.zip,
            args.dataset,
            batch=args.batch,
            all_batches=args.all_batches,
            register=not args.no_register,
        )


if __name__ == "__main__":
    main()
