"""
Extract an Empirica export zip into data/pilot_runs/{timestamp}/.

Unzips, extracts bonuses (with Prolific IDs), and saves anonymized raw CSVs.

Usage:
    uv run python analysis/extract_run.py experiment/data/20260301_132907/empirica-export-20260301_132907.zip
    uv run python analysis/extract_run.py                    # most recent zip under experiment/data/
"""

import argparse
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = PROJECT_ROOT / "data" / "pilot_runs"
EXPERIMENT_DATA_DIR = PROJECT_ROOT / "experiment" / "data"

ZIP_PATTERN = re.compile(r"empirica-export-(\d{8}_\d{6})\.zip")

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

# Columns to strip from player.csv for anonymization
SENSITIVE_COLUMNS = [
    "participantIdentifier",
    "participantIdentifierLastChangedAt",
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


def extract_bonuses(unzipped_dir: Path, output_dir: Path) -> None:
    """Extract bonus CSV with Prolific IDs."""
    print("Extracting bonuses...")
    player_df = pd.read_csv(unzipped_dir / "player.csv")
    game_df = pd.read_csv(unzipped_dir / "game.csv")

    real_games = game_df[game_df["condition"].notna()]["id"].tolist()
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
        early_df = early[["participantIdentifier", "partialPay"]].copy()
        early_df.columns = ["prolific_id", "partial_pay"]
        early_df["partial_pay"] = early_df["partial_pay"].fillna(0).round(2)
        early_path = output_dir / "early_ended.csv"
        early_df.to_csv(early_path, index=False)
        print(f"\n  Wrote {early_path} ({len(early_df)} early-ended players)")
        print(early_df.to_string(index=False))
    else:
        print("  No early-ended players found.")


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


def main():
    parser = argparse.ArgumentParser(
        description="Extract an Empirica export zip into data/pilot_runs/{timestamp}/",
    )
    parser.add_argument(
        "zip_path",
        nargs="?",
        default=None,
        help="Path to empirica-export-*.zip (default: most recent under experiment/data/)",
    )
    args = parser.parse_args()

    if args.zip_path:
        zip_path = Path(args.zip_path).resolve()
        if not zip_path.exists():
            print(f"Zip file not found: {zip_path}", file=sys.stderr)
            sys.exit(1)
    else:
        zip_path = find_most_recent_zip()

    datetime_str = extract_datetime(zip_path)
    output_dir = RUNS_DIR / datetime_str
    raw_dir = output_dir / "raw"

    print(f"Zip: {zip_path}")
    print(f"Output: {output_dir}")

    unzipped_dir = unzip(zip_path)

    try:
        extract_bonuses(unzipped_dir, output_dir)
        anonymize_raw(unzipped_dir, raw_dir)
    finally:
        shutil.rmtree(unzipped_dir, ignore_errors=True)

    print(f"\nDone. Raw CSVs in {raw_dir}")
    print(f"Bonuses in {output_dir / 'bonuses.csv'}")


if __name__ == "__main__":
    main()
