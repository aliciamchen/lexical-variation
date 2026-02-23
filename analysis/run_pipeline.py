"""
Unified analysis pipeline: from raw Empirica zip to figures.

Takes a zip from copy_tajriba.sh output, extracts bonuses, anonymizes data,
runs preprocessing, embeddings, visualizations, and optionally renders Quarto.

Usage:
    uv run python analysis/run_pipeline.py                                    # most recent zip
    uv run python analysis/run_pipeline.py path/to/empirica-export-*.zip      # specific zip
    uv run python analysis/run_pipeline.py --skip-embeddings                  # skip slow SBERT step
    uv run python analysis/run_pipeline.py --skip-render                      # skip Quarto render
    uv run python analysis/run_pipeline.py --skip-visualize                   # skip plots/animations
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_DIR = PROJECT_ROOT / "analysis"
EXPERIMENT_DATA_DIR = PROJECT_ROOT / "experiment" / "data"

ZIP_PATTERN = re.compile(r"empirica-export-(\d{8}_\d{6})\.zip")

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


def step_unzip(zip_path: Path) -> Path:
    """Step 1: Unzip to a temp directory and return the path."""
    print(f"\n{'=' * 60}")
    print(f"Step 1: Unzipping {zip_path.name}")
    print(f"{'=' * 60}")
    tmp_dir = Path(tempfile.mkdtemp(prefix="empirica_export_"))
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(tmp_dir)
    csv_count = len(list(tmp_dir.glob("*.csv")))
    print(f"  Extracted {csv_count} files to {tmp_dir}")
    return tmp_dir


def step_extract_bonuses(unzipped_dir: Path, output_dir: Path) -> None:
    """Step 2: Extract bonus CSV with Prolific IDs."""
    print(f"\n{'=' * 60}")
    print("Step 2: Extracting bonus CSV")
    print(f"{'=' * 60}")

    player_df = pd.read_csv(unzipped_dir / "player.csv")
    game_df = pd.read_csv(unzipped_dir / "game.csv")

    # Filter to real games (non-null condition)
    real_games = game_df[game_df["condition"].notna()]["id"].tolist()
    game_players = player_df[player_df["gameID"].isin(real_games)].copy()

    bonus_df = game_players[["participantIdentifier", "bonus"]].copy()
    bonus_df.columns = ["prolific_id", "bonus"]
    bonus_df["bonus"] = bonus_df["bonus"].fillna(0).round(2)

    output_dir.mkdir(parents=True, exist_ok=True)
    bonus_path = output_dir / "bonuses.csv"
    bonus_df.to_csv(bonus_path, index=False)
    print(f"  Wrote {bonus_path} ({len(bonus_df)} players)")
    print(bonus_df.to_string(index=False))


def step_anonymize_raw(unzipped_dir: Path, raw_dir: Path) -> None:
    """Step 3: Copy raw CSVs, stripping sensitive columns from player.csv."""
    print(f"\n{'=' * 60}")
    print("Step 3: Anonymizing raw export")
    print(f"{'=' * 60}")

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


def step_preprocess(raw_dir: Path, data_dir: Path) -> None:
    """Step 4: Run preprocessing.py."""
    print(f"\n{'=' * 60}")
    print("Step 4: Running preprocessing")
    print(f"{'=' * 60}")

    script = ANALYSIS_DIR / "preprocessing.py"
    cmd = [sys.executable, str(script), str(raw_dir), "--output", str(data_dir)]
    subprocess.run(cmd, check=True)


def step_embeddings(data_dir: Path) -> None:
    """Step 5: Run compute_embeddings.py."""
    print(f"\n{'=' * 60}")
    print("Step 5: Computing embeddings")
    print(f"{'=' * 60}")

    script = ANALYSIS_DIR / "compute_embeddings.py"
    cmd = [sys.executable, str(script), str(data_dir), "--output", str(data_dir)]
    subprocess.run(cmd, check=True)


def step_visualize(data_dir: Path, figures_dir: Path) -> None:
    """Step 6: Run pilot_analysis.py and animate_umap.py for all conditions."""
    print(f"\n{'=' * 60}")
    print("Step 6: Generating visualizations")
    print(f"{'=' * 60}")

    figures_dir.mkdir(parents=True, exist_ok=True)

    # pilot_analysis.py
    vis_script = ANALYSIS_DIR / "pilot_analysis.py"
    cmd = [
        sys.executable,
        str(vis_script),
        "--data-dir",
        str(data_dir),
        "--output-dir",
        str(figures_dir),
    ]
    print(f"\n  Running pilot_analysis.py ...")
    subprocess.run(cmd, check=True)

    # animate_umap.py
    anim_script = ANALYSIS_DIR / "animate_umap.py"
    cmd = [
        sys.executable,
        str(anim_script),
        "--data-dir",
        str(data_dir),
        "--output-dir",
        str(figures_dir),
    ]
    print(f"\n  Running animate_umap.py ...")
    subprocess.run(cmd, check=True)


def step_render_quarto() -> None:
    """Step 7: Render Quarto notebooks."""
    print(f"\n{'=' * 60}")
    print("Step 7: Rendering Quarto notebooks")
    print(f"{'=' * 60}")

    qmd_files = sorted(ANALYSIS_DIR.glob("[0-9][0-9]_*.qmd"))
    if not qmd_files:
        print("  No .qmd files found.")
        return

    for qmd in qmd_files:
        print(f"\n  Rendering {qmd.name} ...")
        subprocess.run(["quarto", "render", str(qmd)], check=True)


def update_data_symlink(datetime_str: str) -> None:
    """Create/update symlink: analysis/processed_data -> analysis/{datetime}/data/."""
    symlink_path = ANALYSIS_DIR / "processed_data"
    target = Path(datetime_str) / "data"  # relative to analysis/

    # If it's an existing symlink, remove it
    if symlink_path.is_symlink():
        symlink_path.unlink()
        symlink_path.symlink_to(target)
        print(f"\n  Updated symlink: analysis/processed_data -> {target}")
    elif symlink_path.is_dir():
        # First run: current analysis/processed_data is a real directory.
        # Rename it out of the way, then create the symlink.
        backup = ANALYSIS_DIR / "data.bak"
        if backup.exists():
            shutil.rmtree(backup)
        symlink_path.rename(backup)
        symlink_path.symlink_to(target)
        print(f"\n  Moved existing analysis/processed_data/ to analysis/processed_data.bak/")
        print(f"  Created symlink: analysis/processed_data -> {target}")
    else:
        symlink_path.symlink_to(target)
        print(f"\n  Created symlink: analysis/processed_data -> {target}")


def main():
    parser = argparse.ArgumentParser(
        description="Run the full analysis pipeline from an Empirica export zip",
    )
    parser.add_argument(
        "zip_path",
        nargs="?",
        default=None,
        help="Path to empirica-export-*.zip (default: most recent under experiment/data/)",
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip the SBERT embedding computation step",
    )
    parser.add_argument(
        "--skip-render",
        action="store_true",
        help="Skip Quarto notebook rendering",
    )
    parser.add_argument(
        "--skip-visualize",
        action="store_true",
        help="Skip visualization and animation generation",
    )
    args = parser.parse_args()

    # Step 1: Locate zip
    if args.zip_path:
        zip_path = Path(args.zip_path).resolve()
        if not zip_path.exists():
            print(f"Zip file not found: {zip_path}", file=sys.stderr)
            sys.exit(1)
    else:
        zip_path = find_most_recent_zip()

    datetime_str = extract_datetime(zip_path)
    output_dir = ANALYSIS_DIR / datetime_str
    raw_dir = output_dir / "raw"
    data_dir = output_dir / "data"
    figures_dir = output_dir / "outputs"

    print(f"Zip: {zip_path}")
    print(f"Output: {output_dir}")

    # Step 1: Unzip
    unzipped_dir = step_unzip(zip_path)

    try:
        # Step 2: Extract bonuses
        step_extract_bonuses(unzipped_dir, output_dir)

        # Step 3: Anonymize raw export
        step_anonymize_raw(unzipped_dir, raw_dir)

        # Step 4: Preprocess
        step_preprocess(raw_dir, data_dir)

        # Step 5: Embeddings
        if args.skip_embeddings:
            print(f"\n{'=' * 60}")
            print("Step 5: Skipping embeddings (--skip-embeddings)")
            print(f"{'=' * 60}")
        else:
            step_embeddings(data_dir)

        # Step 6: Visualizations
        if args.skip_visualize:
            print(f"\n{'=' * 60}")
            print("Step 6: Skipping visualizations (--skip-visualize)")
            print(f"{'=' * 60}")
        else:
            step_visualize(data_dir, figures_dir)

        # Update symlink
        update_data_symlink(datetime_str)

        # Step 7: Quarto
        if args.skip_render:
            print(f"\n{'=' * 60}")
            print("Step 7: Skipping Quarto render (--skip-render)")
            print(f"{'=' * 60}")
        else:
            step_render_quarto()

    finally:
        # Clean up temp directory
        shutil.rmtree(unzipped_dir, ignore_errors=True)

    print(f"\n{'=' * 60}")
    print("Pipeline complete!")
    print(f"{'=' * 60}")
    print(f"  Bonuses:  {output_dir / 'bonuses.csv'}")
    print(f"  Raw data: {raw_dir}")
    print(f"  Processed: {data_dir}")
    if not args.skip_visualize:
        print(f"  Figures:  {figures_dir}")
    print(f"  Symlink:  analysis/processed_data -> {datetime_str}/data/")


if __name__ == "__main__":
    main()
