"""
Unified analysis pipeline: from raw Empirica zip to figures.

Usage:
    uv run python analysis/run_pipeline.py                                    # most recent zip
    uv run python analysis/run_pipeline.py path/to/empirica-export-*.zip      # specific zip
    uv run python analysis/run_pipeline.py --skip-embeddings                  # skip slow SBERT step
    uv run python analysis/run_pipeline.py --skip-render                      # skip Quarto render
    uv run python analysis/run_pipeline.py --skip-visualize                   # skip plots/animations

Subcommands:
    uv run python analysis/run_pipeline.py list                               # list all runs
    uv run python analysis/run_pipeline.py bonuses                            # print latest bonuses
    uv run python analysis/run_pipeline.py bonuses --run 20260225_210047      # specific run
    uv run python analysis/run_pipeline.py early-ended                       # print early-ended players
    uv run python analysis/run_pipeline.py early-ended --run 20260225_210047  # specific run
    uv run python analysis/run_pipeline.py status                             # show symlink target
    uv run python analysis/run_pipeline.py combine 20260301_132907 20260301_214147
    uv run python analysis/run_pipeline.py combine 20260301_132907 20260301_214147 --skip-embeddings
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_DIR = PROJECT_ROOT / "analysis"
DATA_DIR = PROJECT_ROOT / "data"
EXPERIMENT_DATA_DIR = PROJECT_ROOT / "experiment" / "data"

ZIP_PATTERN = re.compile(r"empirica-export-(\d{8}_\d{6})\.zip")
TIMESTAMP_DIR_PATTERN = re.compile(r"^\d{8}_\d{6}$")

SUBCOMMANDS = {"list", "bonuses", "early-ended", "status", "run", "combine"}

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

    # Split into completed vs early-ended players
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
        print("\n  No early-ended players found.")


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


def step_filter_messages(data_dir: Path) -> None:
    """Step 4b: Filter non-referential messages (optional, requires Vertex AI)."""
    print(f"\n{'=' * 60}")
    print("Step 4b: Filtering non-referential messages")
    print(f"{'=' * 60}")

    script = ANALYSIS_DIR / "filter_nonreferential.py"
    cmd = [sys.executable, str(script), "classify", "--data-dir", str(data_dir)]
    subprocess.run(cmd, check=True)

    cmd = [sys.executable, str(script), "apply", "--data-dir", str(data_dir)]
    subprocess.run(cmd, check=True)


def step_embeddings(data_dir: Path, utterances_file: str = "speaker_utterances.csv") -> None:
    """Step 5: Run compute_embeddings.py."""
    print(f"\n{'=' * 60}")
    print("Step 5: Computing embeddings")
    print(f"{'=' * 60}")

    script = ANALYSIS_DIR / "compute_embeddings.py"
    cmd = [sys.executable, str(script), str(data_dir), "--output", str(data_dir),
           "--utterances-file", utterances_file]
    subprocess.run(cmd, check=True)


def step_visualize(data_dir: Path, figures_dir: Path) -> None:
    """Step 6: Run animate_umap.py for all conditions."""
    print(f"\n{'=' * 60}")
    print("Step 6: Generating visualizations")
    print(f"{'=' * 60}")

    figures_dir.mkdir(parents=True, exist_ok=True)

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


def update_data_symlink(data_dir: Path) -> None:
    """Create/update symlink: analysis/processed_data -> data_dir.

    Args:
        data_dir: Absolute or relative path to the data directory.
                  Will be stored as a relative symlink from analysis/.
    """
    symlink_path = ANALYSIS_DIR / "processed_data"
    # Make target relative to analysis/ for a clean symlink
    target = Path(os.path.relpath(data_dir.resolve(), ANALYSIS_DIR.resolve()))

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


def find_timestamped_dirs() -> list[Path]:
    """Find all timestamped output directories under analysis/."""
    dirs = []
    for d in sorted(ANALYSIS_DIR.iterdir(), reverse=True):
        if d.is_dir() and TIMESTAMP_DIR_PATTERN.match(d.name):
            dirs.append(d)
    return dirs


def get_active_run() -> str | None:
    """Return the datetime string the processed_data symlink points to, or None."""
    symlink = ANALYSIS_DIR / "processed_data"
    if symlink.is_symlink():
        target = symlink.resolve()
        # target is .../analysis/<datetime>/data
        if target.name == "data" and TIMESTAMP_DIR_PATTERN.match(target.parent.name):
            return target.parent.name
    return None


def cmd_list():
    """List all analysis runs with metadata."""
    dirs = find_timestamped_dirs()
    if not dirs:
        print("No analysis runs found.")
        return

    active = get_active_run()

    print(f"\n{'Analysis Runs':}")
    print(f"{'─' * 90}")

    for d in dirs:
        dt = d.name
        active_tag = "  *active*" if dt == active else ""

        # Read metadata from games.csv if available
        games_path = d / "data" / "games.csv"
        game_info = ""
        player_info = ""
        if games_path.exists():
            try:
                games = pd.read_csv(games_path)
                n_games = len(games)
                conditions = ", ".join(sorted(games["condition"].dropna().unique()))
                game_info = f"{n_games} game{'s' if n_games != 1 else ''} ({conditions})"

                players_path = d / "data" / "players.csv"
                if players_path.exists():
                    players = pd.read_csv(players_path)
                    player_info = f"{len(players)} players"
            except Exception:
                game_info = "(error reading metadata)"

        # Check for bonuses
        has_bonuses = "yes" if (d / "bonuses.csv").exists() else "no"

        # Count output files
        n_outputs = sum(1 for _ in d.rglob("*") if _.is_file())

        parts = [f"  {dt}{active_tag:<10}"]
        if game_info:
            parts.append(game_info)
        if player_info:
            parts.append(player_info)
        parts.append(f"bonuses: {has_bonuses}")
        parts.append(f"{n_outputs} outputs")

        print("  ".join(parts))

    print()


def cmd_bonuses(run_name: str | None = None):
    """Print bonus CSV for a specific or latest run."""
    if run_name:
        bonus_dir = ANALYSIS_DIR / run_name
    else:
        dirs = find_timestamped_dirs()
        if not dirs:
            print("No analysis runs found.", file=sys.stderr)
            sys.exit(1)
        bonus_dir = dirs[0]  # most recent

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
        run_dir = ANALYSIS_DIR / run_name
    else:
        dirs = find_timestamped_dirs()
        if not dirs:
            print("No analysis runs found.", file=sys.stderr)
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


def cmd_status():
    """Show what the processed_data symlink points to."""
    symlink = ANALYSIS_DIR / "processed_data"

    if symlink.is_symlink():
        target = symlink.readlink()
        active = get_active_run()
        print(f"\n  processed_data -> {target}")
        if active:
            games_path = ANALYSIS_DIR / active / "data" / "games.csv"
            if games_path.exists():
                try:
                    games = pd.read_csv(games_path)
                    conditions = ", ".join(sorted(games["condition"].dropna().unique()))
                    print(f"  Run: {active}")
                    print(f"  Games: {len(games)} ({conditions})")
                except Exception:
                    pass
    elif symlink.is_dir():
        print(f"\n  processed_data is a real directory (not a symlink)")
    elif not symlink.exists():
        print(f"\n  processed_data does not exist. Run the pipeline first.")
    print()


def validate_runs(run_ids: list[str]) -> list[Path]:
    """Check that each run's raw/ directory exists, return paths."""
    raw_dirs = []
    for run_id in run_ids:
        raw_dir = ANALYSIS_DIR / run_id / "raw"
        if not raw_dir.is_dir():
            print(f"Error: {raw_dir} does not exist", file=sys.stderr)
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
    print(f"\nManifest written to {manifest_path}")


def cmd_combine(argv: list[str]):
    """Combine raw CSVs from multiple pipeline runs into a single dataset."""
    parser = argparse.ArgumentParser(
        description="Combine raw CSVs from multiple pipeline runs"
    )
    parser.add_argument(
        "runs", nargs="+",
        help="Run timestamps (e.g. 20260301_132907 20260301_214147)"
    )
    parser.add_argument(
        "--output", "-o", default=str(ANALYSIS_DIR / "pilots"),
        help="Output directory (default: analysis/pilots)"
    )
    parser.add_argument(
        "--skip-embeddings", action="store_true",
        help="Skip the SBERT embedding computation step"
    )
    parser.add_argument(
        "--skip-visualize", action="store_true",
        help="Skip visualization and animation generation"
    )
    args = parser.parse_args(argv)

    output_dir = Path(args.output)
    data_base = DATA_DIR / "pilots"
    output_raw = data_base / "raw"
    output_data = data_base
    output_figures = output_dir / "figures"

    print("Validating runs...")
    raw_dirs = validate_runs(args.runs)

    print("\nStacking raw CSVs...")
    combined = stack_raw_csvs(raw_dirs, args.runs)

    print("\nFiltering failed games...")
    combined = filter_failed_games(combined)

    print("\nWriting combined raw CSVs...")
    write_combined_raw(combined, output_raw)

    step_preprocess(output_raw, output_data)

    if not args.skip_embeddings:
        step_embeddings(output_data)

    if not args.skip_visualize:
        step_visualize(output_data, output_figures)

    write_manifest(output_dir, args.runs, combined)

    # Update symlink
    update_data_symlink(output_data)

    # Summary
    game_df = combined["game.csv"]
    player_df = combined.get("player.csv", pd.DataFrame())
    print(f"\n{'=' * 60}")
    print("Combine complete!")
    print(f"{'=' * 60}")
    print(f"  Games: {len(game_df)}, Players: {len(player_df)}")
    print(f"  Conditions: {dict(game_df['condition'].value_counts())}")
    print(f"  Source runs: {game_df['_sourceRun'].unique().tolist()}")
    print(f"  Output: {output_dir}")


def main():
    # Check if first arg is a subcommand
    if len(sys.argv) > 1 and sys.argv[1] in SUBCOMMANDS:
        subcmd = sys.argv[1]
        if subcmd == "list":
            cmd_list()
            return
        elif subcmd == "status":
            cmd_status()
            return
        elif subcmd == "bonuses":
            run_name = None
            if "--run" in sys.argv:
                idx = sys.argv.index("--run")
                if idx + 1 < len(sys.argv):
                    run_name = sys.argv[idx + 1]
                else:
                    print("--run requires a value", file=sys.stderr)
                    sys.exit(1)
            cmd_bonuses(run_name)
            return
        elif subcmd == "early-ended":
            run_name = None
            if "--run" in sys.argv:
                idx = sys.argv.index("--run")
                if idx + 1 < len(sys.argv):
                    run_name = sys.argv[idx + 1]
                else:
                    print("--run requires a value", file=sys.stderr)
                    sys.exit(1)
            cmd_early_ended(run_name)
            return
        elif subcmd == "combine":
            cmd_combine(sys.argv[2:])
            return
        elif subcmd == "run":
            # Strip "run" from argv so argparse sees the rest
            sys.argv = [sys.argv[0]] + sys.argv[2:]

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
    parser.add_argument(
        "--filter-messages",
        action="store_true",
        help="Filter non-referential messages before embeddings (requires Vertex AI)",
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

        # Step 4b: Filter messages (optional)
        utterances_file = "speaker_utterances.csv"
        if args.filter_messages:
            step_filter_messages(data_dir)
            utterances_file = "speaker_utterances_filtered.csv"

        # Step 5: Embeddings
        if args.skip_embeddings:
            print(f"\n{'=' * 60}")
            print("Step 5: Skipping embeddings (--skip-embeddings)")
            print(f"{'=' * 60}")
        else:
            step_embeddings(data_dir, utterances_file)

        # Step 6: Visualizations
        if args.skip_visualize:
            print(f"\n{'=' * 60}")
            print("Step 6: Skipping visualizations (--skip-visualize)")
            print(f"{'=' * 60}")
        else:
            step_visualize(data_dir, figures_dir)

        # Update symlink
        update_data_symlink(data_dir)

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
    print(f"  Bonuses:       {output_dir / 'bonuses.csv'}")
    early_path = output_dir / "early_ended.csv"
    if early_path.exists():
        print(f"  Early-ended:   {early_path}")
    print(f"  Raw data: {raw_dir}")
    print(f"  Processed: {data_dir}")
    if not args.skip_visualize:
        print(f"  Figures:  {figures_dir}")
    print(f"  Symlink:  analysis/processed_data -> {datetime_str}/data/")


if __name__ == "__main__":
    main()
