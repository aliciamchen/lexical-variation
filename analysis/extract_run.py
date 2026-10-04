"""
Extract an Empirica export zip into data/runs/{timestamp}/.

Unzips the export and saves anonymized raw CSVs. Who is owed what is worked out
from the export zips themselves by operations/payments.py (`make payments`),
not here.

Usage:
    uv run python analysis/extract_run.py <zip> --dataset full          # extract one export and register it
    uv run python analysis/extract_run.py --dataset full                # most recent zip under experiment/data/
    uv run python analysis/extract_run.py <zip> --dataset smoke --no-register      # extract without touching runs.txt
    uv run python analysis/extract_run.py list                          # list extracted runs

The options of the default (extract) form may come in any order around the zip
path. The pilot dataset is frozen: without --dataset (or DATASET) the script
refuses to extract, so a full-sample export is never registered into it.
"""

import argparse
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
SUBCOMMANDS = {"list"}

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


# A Prolific participant id is exactly 24 hexadecimal characters. Participants
# sometimes type theirs into a free-text survey answer or the chat, which the
# column stripping cannot catch, so every text cell is scrubbed as well. The
# pre-commit hook refuses any data file that still contains such a token.
PROLIFIC_ID_PATTERN = re.compile(r"(?<![0-9a-fA-F])[0-9a-f]{24}(?![0-9a-fA-F])")
PROLIFIC_ID_PLACEHOLDER = "[prolific id removed]"


def redact_prolific_ids(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Replace Prolific-id-shaped tokens inside text cells; returns the count replaced."""
    count = 0
    for col in df.columns:
        if not (pd.api.types.is_string_dtype(df[col]) or df[col].dtype == object):
            continue
        mask = df[col].notna() & df[col].astype(str).str.contains(PROLIFIC_ID_PATTERN, regex=True)
        if mask.any():
            count += int(mask.sum())
            df.loc[mask, col] = df.loc[mask, col].astype(str).str.replace(
                PROLIFIC_ID_PATTERN, PROLIFIC_ID_PLACEHOLDER, regex=True
            )
    return df, count


def anonymize_raw(unzipped_dir: Path, raw_dir: Path) -> None:
    """Copy raw CSVs, stripping sensitive columns from player.csv and
    redacting Prolific-id-shaped tokens from the text cells of every file."""
    print("Anonymizing raw CSVs...")
    raw_dir.mkdir(parents=True, exist_ok=True)

    for csv_file in sorted(unzipped_dir.glob("*.csv")):
        df = pd.read_csv(csv_file, low_memory=False)
        if csv_file.name == "player.csv":
            cols_to_drop = [c for c in SENSITIVE_COLUMNS if c in df.columns]
            if cols_to_drop:
                df = df.drop(columns=cols_to_drop)
                print(f"  {csv_file.name}: dropped {cols_to_drop}")
        df, redacted = redact_prolific_ids(df)
        note = f", redacted {redacted} id-shaped token(s) in text" if redacted else ""
        df.to_csv(raw_dir / csv_file.name, index=False)
        print(f"  {csv_file.name}: copied{note}")


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
        n_files = sum(1 for _ in d.rglob("*") if _.is_file())
        print(f"  {d.name}  {n_files} files")
    print()


def cmd_extract(
    zip_path_arg: str | None,
    dataset: str | None = None,
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
        anonymize_raw(unzipped_dir, raw_dir)
    finally:
        shutil.rmtree(unzipped_dir, ignore_errors=True)

    print(f"\nDone. Raw CSVs in {raw_dir}")

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
        description="Unzip an export, strip the sensitive participant columns, "
        "and register the run in data/<dataset>/runs.txt.",
    )
    extract.add_argument(
        "zip", nargs="?", default=None,
        help="Path to empirica-export-<timestamp>.zip (default: the most recent zip under experiment/data/)",
    )
    add_dataset_argument(extract)
    extract.add_argument(
        "--no-register", action="store_true",
        help="Do not add the run to data/<dataset>/runs.txt (used by make smoke)",
    )

    sub.add_parser("list", help="List the extracted runs in data/runs/")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line, treating a call without a subcommand as `extract`.

    `extract_run.py <zip> --dataset full`, `extract_run.py --dataset full <zip>`,
    and a bare `extract_run.py --dataset full` (most recent zip) are all the
    extract form; `list` is the only subcommand.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or (argv[0] not in SUBCOMMANDS | {"extract"} and argv[0] not in ("-h", "--help")):
        argv.insert(0, "extract")
    return build_parser().parse_args(argv)


def main():
    args = parse_args()
    if args.command == "list":
        cmd_list()
    else:
        cmd_extract(
            args.zip,
            args.dataset,
            register=not args.no_register,
        )


if __name__ == "__main__":
    main()
